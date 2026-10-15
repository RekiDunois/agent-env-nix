#!/usr/bin/env python3
"""Explicit, project-local Codex activation. No global files are written.

The journal recovers individual publications; it is not a multi-file transaction.
The lock serializes agent-env processes, not editors. Config publication uses a
whole-file optimistic snapshot check immediately before replacing the file.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

import tomlkit

SCHEMA = 1
MARKER = ".agent-skills-managed.json"
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
AGENT_CONTROLS = {"enabled", "max_concurrent_threads_per_session", "max_threads",
                  "max_depth", "default_subagent_model", "default_subagent_reasoning_effort",
                  "job_max_runtime_seconds", "interrupt_message"}


class ActivationError(Exception):
    """An actionable conflict, without including configuration values/secrets."""


class SnapshotChanged(ActivationError):
    """No content should be published from this stale whole-file snapshot."""


_UNSET = object()


def fail(message):
    raise ActivationError(message)


def safe_name(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or name in (".", ".."):
        fail(f"unsafe export name: {name!r}")
    return name


def digest(data):
    return hashlib.sha256(data).hexdigest()


def exists(path):
    return os.path.lexists(path)


def safe_path(path):
    """Reject links and non-directory ancestors, including dangling links."""
    path = Path(path)
    if not path.is_absolute():
        fail(f"expected an absolute path: {path}")
    for part in reversed([path, *path.parents]):
        try:
            mode = part.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            fail(f"symlink is not an allowed activation path: {part}")
        if part != path and not stat.S_ISDIR(mode):
            fail(f"non-directory activation path component: {part}")
    return path


def read_bytes(path):
    safe_path(path)
    try:
        if not exists(path):
            return None
        if not stat.S_ISREG(path.lstat().st_mode):
            fail(f"expected a regular file: {path}")
        return path.read_bytes()
    except OSError as exc:
        fail(f"cannot read {path}: {exc.strerror}")


def parse_toml(path, raw=_UNSET):
    if raw is _UNSET:
        raw = read_bytes(path)
    try:
        return tomlkit.parse((raw or b"").decode("utf-8"))
    except (ValueError, UnicodeError, tomlkit.exceptions.TOMLKitError):
        fail(f"invalid TOML source: {path}")


def plain(value):
    return value.unwrap() if hasattr(value, "unwrap") else value


def signature(path):
    """Complete ordinary-tree identity, including hidden files and exec bits."""
    safe_path(path)
    if not exists(path):
        return None
    mode = path.lstat().st_mode
    if stat.S_ISREG(mode):
        return {"kind": "file", "sha256": digest(path.read_bytes()), "exec": mode & 0o111}
    if stat.S_ISDIR(mode):
        children = {p.name: signature(p) for p in sorted(path.iterdir())}
        return {"kind": "tree", "exec": mode & 0o111, "children": children}
    fail(f"special filesystem object is not allowed: {path}")


def byte_identity(path):
    raw = read_bytes(path)
    return None if raw is None else {"kind": "bytes", "sha256": digest(raw)}


def identity(path, kind):
    return byte_identity(path) if kind == "config" else signature(path)


def atomic_json(path, value):
    safe_path(path)
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if exists(temporary):
            os.unlink(temporary)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def writable_copy(source, destination):
    signature(source)
    if source.is_dir():
        shutil.copytree(source, destination)
        for directory, _, files in os.walk(destination):
            os.chmod(directory, stat.S_IMODE(os.stat(directory).st_mode) | 0o700)
            for name in files:
                file = Path(directory) / name
                os.chmod(file, stat.S_IMODE(file.stat().st_mode) | 0o600)
    else:
        shutil.copy2(source, destination)
        os.chmod(destination, stat.S_IMODE(destination.stat().st_mode) | 0o600)


def erase(path):
    safe_path(path)
    if not exists(path):
        return
    if path.is_dir():
        # Owned generated trees may have inherited read-only store permissions.
        for directory, _, _ in os.walk(path):
            os.chmod(directory, stat.S_IMODE(os.stat(directory).st_mode) | 0o700)
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()
    else:
        fail(f"cannot remove unsafe object: {path}")


def empty_state():
    return {"schemaVersion": SCHEMA, "skills": {}, "agents": {}, "mcp": {},
            "reused": [], "roots": [], "createdDirectories": [],
            "environment": None, "packages": []}


def validate_state(state):
    if not isinstance(state, dict) or state.get("schemaVersion") != SCHEMA:
        fail("unsupported ownership state schema; no changes were made")
    for kind in ("skills", "agents", "mcp"):
        if not isinstance(state.get(kind), dict):
            fail(f"invalid ownership state section: {kind}")
        for name, item in state[kind].items():
            safe_name(name)
            if not isinstance(item, dict) or not isinstance(item.get("owner"), str):
                fail(f"invalid ownership record: {kind}/{name}")
    for root in state.get("roots", []):
        if not isinstance(root, dict) or not re.fullmatch(r"[a-f0-9]{32}", root.get("name", "")):
            fail("invalid GC root record")
        if root.get("name") != digest(root.get("environment", "").encode())[:32]:
            fail("GC root identity does not match its environment")
    allowed_dirs = {".agents", ".agents/skills", ".codex", ".codex/agents"}
    if any(item not in allowed_dirs for item in state.get("createdDirectories", [])):
        fail("invalid created-directory ownership record")
    return state


# Isolated writer boundary: lifecycle, checks, and CAS do not depend on rendering.
def render_config(document, changes):
    result = copy.deepcopy(document)
    if not changes:
        return tomlkit.dumps(result).encode("utf-8")
    if "mcp_servers" not in result and any(value is not None for value in changes.values()):
        result["mcp_servers"] = tomlkit.table()
    table = result.get("mcp_servers")
    if table is not None and not isinstance(table, dict):
        fail("mcp_servers must be a TOML table")
    for name, value in changes.items():
        if value is None:
            if table is not None and name in table:
                del table[name]
        else:
            table[name] = value
    return tomlkit.dumps(result).encode("utf-8")


class Activator:
    def __init__(self, manifest, project, extra_configs=(), *, system_config=None):
        self.manifest = manifest
        if manifest.get("schemaVersion") != SCHEMA:
            fail("unsupported project manifest schema")
        project = Path(project).expanduser()
        if not project.is_dir():
            fail(f"project directory does not exist: {project}")
        self.project = project.resolve(strict=True)
        self.state_dir = self.project / ".agent-env-nix"
        self.state_file = self.state_dir / "state.json"
        self.pending_file = self.state_dir / "pending.json"
        self.extra_configs = [Path(p).expanduser().absolute() for p in extra_configs]
        self.source_identities = {}
        self.system_config = (Path("/etc").resolve() / "codex/config.toml"
                              if system_config is None else Path(system_config))
        self.messages = []
        self.stage = None
        self.operations = []
        self.new_directories = set()
        self.completed_objects = 0
        self.before_publish = None  # Test injection: never exposed as a CLI override.
        for kind in ("skills", "agents", "mcpOwners"):
            if not isinstance(manifest.get(kind, {}), dict):
                fail(f"invalid manifest section: {kind}")
            for name in manifest.get(kind, {}):
                safe_name(name)
        for name in ("environment", "nixStore", "skillsInstaller", "mcpConfig"):
            if not isinstance(manifest.get(name), str) or not Path(manifest[name]).is_absolute():
                fail(f"manifest {name} must be an absolute fixed path")

    @contextlib.contextmanager
    def locked(self):
        safe_path(self.state_dir)
        self.state_dir.mkdir(mode=0o700, exist_ok=True)
        if not self.state_dir.is_dir():
            fail(f"state path is not a directory: {self.state_dir}")
        if self.state_dir.stat().st_mode & 0o077:
            fail(f"state directory must be private (mode 0700): {self.state_dir}")
        lock = self.state_dir / "lock"
        safe_path(lock)
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                fail(f"lock is not a regular file: {lock}")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def load_state(self):
        raw = read_bytes(self.state_file)
        if raw is None:
            return empty_state()
        try:
            return validate_state(json.loads(raw))
        except (ValueError, TypeError, KeyError):
            fail(f"invalid ownership state: {self.state_file}")

    def sources(self):
        candidates = [self.project / ".codex/config.toml"]
        candidates += [parent / ".codex/config.toml" for parent in self.project.parents]
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
        # Resolve the home base, but do not silently dereference its .codex path.
        if "CODEX_HOME" not in os.environ:
            home = Path.home().resolve() / ".codex"
        candidates += [home.absolute() / "config.toml", self.system_config]
        candidates += self.extra_configs
        result = []
        seen = set()
        for path in candidates:
            path = Path(os.path.abspath(path))
            if str(path) not in seen:
                seen.add(str(path))
                raw = read_bytes(path)
                self.source_identities[path] = (None if raw is None else
                                                {"kind": "bytes", "sha256": digest(raw)})
                result.append((path, parse_toml(path, raw)))
        return result

    def stage_desired(self, removing):
        staging = self.state_dir / "staging"
        safe_path(staging)
        staging.mkdir(mode=0o700, exist_ok=True)
        self.stage = Path(tempfile.mkdtemp(prefix="generation-", dir=staging))
        (self.stage / "objects").mkdir()
        if removing:
            return {}, {}, {}
        root = self.stage / "upstream"
        root.mkdir(mode=0o700)
        env = os.environ.copy()
        env["AGENT_SKILLS_ROOT"] = str(root)
        env["AGENT_SKILLS_QUIET"] = "1"
        env.pop("AGENT_SKILLS_FORCE", None)
        try:
            subprocess.run([self.manifest["skillsInstaller"]], env=env, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (OSError, subprocess.CalledProcessError):
            fail("upstream skill staging failed; project resources were not changed")
        skills_root = root / "skills"
        if exists(skills_root / MARKER):
            read_bytes(skills_root / MARKER)
            (skills_root / MARKER).unlink()
        desired_skills = {}
        for name, item in self.manifest.get("skills", {}).items():
            staged = skills_root / name
            if not staged.is_dir() or signature(staged) is None or not (staged / "SKILL.md").is_file():
                fail(f"package {item['owner']}, skill {name}: upstream staging did not produce a complete skill")
            source = Path(item["source"])
            if signature(staged) != signature(source):
                fail(f"package {item['owner']}, skill {name}: staged tree differs from declared source")
            desired_skills[name] = {**item, "path": staged}
        if exists(skills_root):
            unexpected = set(p.name for p in skills_root.iterdir()) - set(desired_skills)
            if unexpected:
                fail("upstream staging produced undeclared skill exports")
        desired_agents = {}
        for name, item in self.manifest.get("agents", {}).items():
            source = Path(item["source"])
            value = plain(parse_toml(source))
            if value.get("name") != name or not all(isinstance(value.get(key), str) and value[key].strip()
                                                   for key in ("description", "developer_instructions")):
                fail(f"package {item['owner']}, agent {name}: invalid native agent definition at {source}")
            value["description"] = value["description"].strip()
            desired_agents[name] = {**item, "path": source, "value": value}
        mcp = plain(parse_toml(Path(self.manifest["mcpConfig"])))
        if set(mcp) - {"mcp_servers"}:
            fail("generated MCP configuration contains unrelated top-level settings")
        desired_mcp = mcp.get("mcp_servers", {})
        if not isinstance(desired_mcp, dict) or set(desired_mcp) != set(self.manifest.get("mcpOwners", {})):
            fail("generated MCP keys differ from manifest ownership keys")
        return desired_skills, desired_agents, desired_mcp

    def check_unsupported(self, sources, selected_mcp, selected_agents):
        for path, document in sources:
            profiles = document.get("profiles", {})
            if not isinstance(profiles, dict):
                continue
            for name, profile in profiles.items():
                if not isinstance(profile, dict):
                    continue
                for key, selected in (("mcp_servers", selected_mcp), ("agents", selected_agents)):
                    values = profile.get(key, {})
                    if isinstance(values, dict) and set(values) & selected:
                        fail(f"unsupported selected {key} source: profile {name} in {path}")
        # Legacy managed files cannot be treated as ordinary editable precedence.
        managed = self.system_config.parent / "managed_config.toml"
        if (selected_mcp or selected_agents) and exists(managed):
            document = parse_toml(managed)
            for key, selected in (("mcp_servers", selected_mcp), ("agents", selected_agents)):
                values = document.get(key, {})
                if isinstance(values, dict) and set(values) & selected:
                    fail(f"unsupported selected managed source: {managed} ({key})")

    def agent_definitions(self, sources, selected):
        definitions = {name: [] for name in selected}
        seen_directories = set()

        def effective(file_value, declaration, hint, source):
            # Codex resolves identity from the native file before considering
            # the declaration key, and gives native metadata precedence.
            raw_name = file_value.get("name")
            if raw_name is not None and not isinstance(raw_name, str):
                fail(f"invalid native agent name in {source}")
            name = raw_name.strip() if raw_name else ""
            name = name or hint
            if name not in selected:
                return None
            value = {key: val for key, val in declaration.items() if key != "config_file"}
            value.update(file_value)
            value["name"] = name
            if "description" in value:
                description = value["description"]
                if not isinstance(description, str) or not description.strip():
                    fail(f"agent {name}: invalid description in {source}")
                value["description"] = description.strip()
            if "developer_instructions" in value:
                instructions = value["developer_instructions"]
                if not isinstance(instructions, str) or not instructions.strip():
                    fail(f"agent {name}: invalid developer_instructions in {source}")
            return name, value

        for config_path, document in sources:
            declarations = document.get("agents", {})
            if not isinstance(declarations, dict):
                fail(f"agents must be a table in {config_path}")
            declared_files = set()
            # All declarations must resolve identity before selected filtering:
            # an alias can point to a differently named native role file.
            for declared_name, raw_record in declarations.items():
                if declared_name in AGENT_CONTROLS:
                    continue
                record = plain(raw_record)
                if not isinstance(record, dict):
                    if declared_name in selected:
                        fail(f"agent {declared_name}: invalid declaration in {config_path}")
                    continue  # Non-role settings such as agents.max_threads.
                reference = record.get("config_file")
                role = None
                file_value = {}
                if reference is not None:
                    if not isinstance(reference, str):
                        fail(f"agent {declared_name}: invalid config_file in {config_path}")
                    role = Path(reference)
                    if not role.is_absolute():
                        role = config_path.parent / role
                    role = Path(os.path.abspath(role))
                    raw = read_bytes(role)
                    if raw is None:
                        fail(f"agent {declared_name}: missing referenced role file {role} from {config_path}")
                    declared_files.add(role)
                    file_value = plain(parse_toml(role, raw))
                resolved = effective(file_value, record, declared_name, config_path)
                if resolved is not None:
                    name, value = resolved
                    definitions[name].append((config_path, value))
                    if role is not None:
                        # Keep both origins: declaration metadata participates
                        # in conflicts, while an equal destination referenced by
                        # it remains a verified, unowned reusable role file.
                        definitions[name].append((role, value))
            directory = config_path.parent / "agents"
            if directory in seen_directories or not selected:
                continue
            seen_directories.add(directory)
            safe_path(directory)
            if not exists(directory):
                continue
            if not directory.is_dir():
                fail(f"native agent directory is not a directory: {directory}")
            paths = []
            def unreadable(error):
                fail(f"cannot inspect native agent directory: {error.filename}")
            for root, directories, files in os.walk(directory, onerror=unreadable, followlinks=False):
                for child in directories:
                    safe_path(Path(root) / child)
                paths.extend(Path(root) / child for child in files if child.endswith(".toml"))
            for path in sorted(paths):
                # Legacy files referenced by a declaration need its name hint
                # and are not loaded a second time as standalone definitions.
                if path in declared_files:
                    continue
                value = plain(parse_toml(path))
                resolved = effective(value, {}, None, path)
                if resolved is not None:
                    name, value = resolved
                    if "developer_instructions" not in value:
                        fail(f"agent {name}: standalone native file lacks developer_instructions: {path}")
                    definitions[name].append((path, value))
        return definitions

    def queue(self, kind, target, source=None, *, data=None, expected=_UNSET):
        target = safe_path(target)
        if target != self.project / ".codex/config.toml" and target.parent not in (
                self.project / ".agents/skills", self.project / ".codex/agents"):
            fail(f"publication target is outside the managed export paths: {target}")
        old = identity(target, kind)
        if expected is not _UNSET and old != expected:
            fail(f"{kind} changed during preflight; retry: {target}")
        staged = None
        if source is not None or data is not None:
            staged = self.stage / "objects" / str(len(self.operations))
            if data is not None:
                staged.write_bytes(data)
                if exists(target):
                    os.chmod(staged, stat.S_IMODE(target.stat().st_mode))
            else:
                writable_copy(Path(source), staged)
        new = identity(staged, kind) if staged else None
        if old == new:
            if staged is not None:
                erase(staged)
            return
        self.operations.append({"kind": kind, "target": str(target.relative_to(self.project)),
                                "old": old, "new": new,
                                "staged": str(staged.relative_to(self.stage)) if staged else None,
                                "backup": f"backup-{len(self.operations)}"})
        if new is not None:
            current = target.parent
            while current != self.project and not exists(current):
                self.new_directories.add(str(current.relative_to(self.project)))
                current = current.parent

    def preflight(self, old, removing):
        desired_skills, desired_agents, desired_mcp = self.stage_desired(removing)
        new = empty_state()
        new["packages"] = [] if removing else self.manifest.get("packages", [])
        selected_agents = set(desired_agents) | set(old["agents"])
        selected_mcp = set(desired_mcp) | set(old["mcp"])
        target_config = self.project / ".codex/config.toml"
        sources = (self.sources() if selected_agents or selected_mcp
                   else [(target_config, tomlkit.document())])
        self.check_unsupported(sources, selected_mcp, selected_agents)
        agent_definitions = self.agent_definitions(sources, selected_agents)
        target_config = self.project / ".codex/config.toml"
        target_document = sources[0][1]
        config_snapshot = self.source_identities.get(target_config) if selected_mcp else None
        changes = {}

        for name in sorted(set(desired_skills) | set(old["skills"])):
            target = self.project / ".agents/skills" / name
            current = signature(target)
            desired = desired_skills.get(name)
            owned = old["skills"].get(name)
            if desired is None:
                if current is not None:
                    self.queue("skill", target, expected=current)
            elif owned or current is None:
                self.queue("skill", target, desired["path"], expected=current)
                new["skills"][name] = {"owner": desired["owner"]}
            elif current == signature(desired["path"]):
                new["reused"].append({"kind": "skill", "name": name, "source": str(target)})
            else:
                fail(f"package {desired['owner']}, skill {name}: conflicting unowned tree at {target}")

        for name in sorted(selected_agents):
            target = self.project / ".codex/agents" / f"{name}.toml"
            current = signature(target)
            owned = old["agents"].get(name)
            desired = desired_agents.get(name)
            if owned and current is not None and current != owned.get("fingerprint"):
                fail(f"package {owned['owner']}, agent {name}: owned file was edited: {target}; GC roots retained")
            if desired is None:
                if current is not None:
                    self.queue("agent", target, expected=current)
                continue
            others = [(path, value) for path, value in agent_definitions[name]
                      if not (owned and path == target)]
            for path, value in others:
                if value != desired["value"]:
                    fail(f"package {desired['owner']}, agent {name}: conflicting declared name in {path}")
            if owned:
                self.queue("agent", target, desired["path"], expected=current)
                new["agents"][name] = {"owner": desired["owner"], "fingerprint": signature(desired["path"])}
            elif others:
                if current is not None and not any(path == target for path, _ in others):
                    fail(f"package {desired['owner']}, agent {name}: destination contains a different declared name: {target}")
                new["reused"] += [{"kind": "agent", "name": name, "source": str(path)} for path, _ in others]
            elif current is None:
                self.queue("agent", target, desired["path"], expected=current)
                new["agents"][name] = {"owner": desired["owner"], "fingerprint": signature(desired["path"])}
            else:
                fail(f"package {desired['owner']}, agent {name}: conflicting unowned file at {target}")

        for name in sorted(selected_mcp):
            desired = desired_mcp.get(name)
            owned = old["mcp"].get(name)
            table = target_document.get("mcp_servers", {})
            if not isinstance(table, dict):
                fail(f"mcp_servers must be a table in {target_config}")
            present = name in table
            current = plain(table.get(name))
            if owned and present and current != owned.get("value"):
                fail(f"package {owned['owner']}, MCP key {name}: owned value was edited in {target_config}; GC roots retained")
            if desired is None:
                if present:
                    changes[name] = None
                continue
            other_sources = []
            for path, document in sources:
                values = document.get("mcp_servers", {})
                if not isinstance(values, dict):
                    fail(f"mcp_servers must be a table in {path}")
                if name not in values or (owned and path == target_config):
                    continue
                if plain(values[name]) != desired:
                    fail(f"package {self.manifest['mcpOwners'][name]}, MCP key {name}: conflicting selected definition in {path}")
                other_sources.append(path)
            if owned or not other_sources:
                if not present or current != desired:
                    changes[name] = desired
                new["mcp"][name] = {"owner": self.manifest["mcpOwners"][name], "value": desired}
            else:
                new["reused"] += [{"kind": "mcp", "name": name, "source": str(path)} for path in other_sources]
        if changes:
            rendered = render_config(target_document, changes)
            # A change during planning must not become the old snapshot for CAS.
            if byte_identity(target_config) != config_snapshot:
                fail(f"config changed during preflight; retry: {target_config}")
            self.queue("config", target_config, data=rendered)
            if self.operations and self.operations[-1]["kind"] == "config":
                self.operations[-1]["old"] = config_snapshot
        new["createdDirectories"] = sorted(set(old.get("createdDirectories", [])) | self.new_directories)
        return new

    def register_root(self):
        environment = self.manifest["environment"]
        roots = safe_path(self.state_dir / "roots")
        roots.mkdir(mode=0o700, exist_ok=True)
        name = digest(environment.encode())[:32]
        path = roots / name
        # Registered roots are symlinks by design and never renamed.
        if exists(path):
            if not path.is_symlink() or os.readlink(path) != environment:
                fail(f"unexpected object at fixed GC root path: {path}")
        try:
            subprocess.run([self.manifest["nixStore"], "--realise", environment,
                            "--add-root", str(path), "--indirect"], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (OSError, subprocess.CalledProcessError):
            fail("Nix GC root registration failed; project resources were not changed")
        if not path.is_symlink() or os.readlink(path) != environment:
            fail(f"Nix did not create the expected fixed GC root: {path}")
        return {"name": name, "environment": environment}

    def verify_operation(self, operation, stage):
        target = self.project / operation["target"]
        allowed = target == self.project / ".codex/config.toml"
        allowed |= target.parent in (self.project / ".agents/skills", self.project / ".codex/agents")
        if not allowed or ".." in Path(operation["target"]).parts or Path(operation["target"]).is_absolute():
            fail("pending journal contains an unsafe publication target")
        kind = operation.get("kind")
        if kind not in ("config", "skill", "agent"):
            fail("pending journal contains an invalid publication kind")
        if kind == "config" and target != self.project / ".codex/config.toml":
            fail("pending config publication has an invalid target")
        if kind == "skill":
            if target.parent != self.project / ".agents/skills":
                fail("pending skill publication has an invalid target")
            safe_name(target.name)
        if kind == "agent":
            if target.parent != self.project / ".codex/agents" or not target.name.endswith(".toml"):
                fail("pending agent publication has an invalid target")
            safe_name(target.name[:-5])
        for field in ("backup", "staged"):
            value = operation.get(field)
            if value is not None and (Path(value).is_absolute() or ".." in Path(value).parts):
                fail("pending journal contains an unsafe staging path")
        return safe_path(target)

    def publish(self, journal, *, fresh=False):
        stage = self.state_dir / "staging" / journal["stage"]
        if not re.fullmatch(r"generation-[A-Za-z0-9_-]+", journal["stage"]):
            fail("invalid pending staging directory")
        safe_path(stage)
        completed = 0
        self.completed_objects = 0
        for operation in journal["operations"]:
            target = self.verify_operation(operation, stage)
            kind = operation["kind"]
            current = identity(target, kind)
            backup = stage / operation["backup"]
            if current == operation["new"]:
                completed += 1
                self.completed_objects = completed
                continue
            backed_up = exists(backup) and identity(backup, kind) == operation["old"]
            if current != operation["old"] and not (current is None and backed_up):
                if fresh and completed == 0:
                    raise SnapshotChanged(f"{kind} changed before publication; retry: {target}; GC roots retained")
                fail(f"pending {kind} publication conflicts with newer content at {target}; {completed} object(s) completed; GC roots retained")
            staged = stage / operation["staged"] if operation["staged"] else None
            if staged is not None and identity(staged, kind) != operation["new"]:
                fail(f"pending staged {kind} content changed; refusing publication at {target}")
            if self.before_publish:
                self.before_publish(operation, target)
            # Recheck all bytes immediately before rename, including unrelated
            # config edits. There is still an unavoidable editor race after CAS.
            if identity(target, kind) != current:
                raise SnapshotChanged(f"{kind} changed immediately before publication; retry: {target}; GC roots retained")
            if operation["new"] is not None:
                self.ensure_parents(target.parent, journal)
            if kind == "skill" and current is not None:
                if exists(backup):
                    fail(f"unexpected backup while replacing skill: {target}")
                os.replace(target, backup)
                sync_directory(target.parent)
            if operation["new"] is None:
                if current is not None and kind != "skill":
                    target.unlink()
            else:
                os.replace(staged, target)
            sync_directory(target.parent)
            completed += 1
            self.completed_objects = completed
        old_state = byte_identity(self.state_file)
        new_raw = (json.dumps(journal["newState"], indent=2, sort_keys=True) + "\n").encode()
        new_identity = {"kind": "bytes", "sha256": digest(new_raw)}
        if old_state not in (journal["oldStateIdentity"], new_identity):
            fail("ownership state changed during publication; GC roots retained")
        atomic_json(self.state_file, journal["newState"])
        self.finish(journal, stage)

    def ensure_parents(self, directory, journal):
        if directory == self.project:
            return
        safe_path(directory)
        if exists(directory):
            if not directory.is_dir():
                fail(f"publication parent is not a directory: {directory}")
            return
        if str(directory.relative_to(self.project)) not in journal["newState"]["createdDirectories"]:
            fail(f"pending publication lacks directory ownership: {directory}")
        self.ensure_parents(directory.parent, journal)
        directory.mkdir()

    def finish(self, journal, stage):
        retained = {root["name"] for root in journal["newState"]["roots"]}
        for root in journal.get("oldRoots", []):
            if root["name"] in retained:
                continue
            path = self.state_dir / "roots" / root["name"]
            if exists(path):
                if not path.is_symlink() or os.readlink(path) != root["environment"]:
                    fail(f"old GC root changed; preserving it: {path}")
                path.unlink()
        for relative in sorted(journal["newState"]["createdDirectories"], key=lambda p: len(p), reverse=True):
            directory = safe_path(self.project / relative)
            if exists(directory):
                try:
                    directory.rmdir()
                except OSError:
                    pass  # Never remove a nonempty parent or unowned sibling.
        self.pending_file.unlink(missing_ok=True)
        sync_directory(self.state_dir)
        erase(stage)

    def recover(self):
        raw = read_bytes(self.pending_file)
        if raw is None:
            return
        try:
            journal = json.loads(raw)
            if journal.get("schemaVersion") != SCHEMA:
                fail("unsupported pending journal schema")
            validate_state(journal["newState"])
            validate_state({**empty_state(), "roots": journal.get("oldRoots", [])})
            self.publish(journal)
            self.messages.append("Recovered the pending generation before processing this request.")
        except (ValueError, KeyError, TypeError):
            fail("invalid pending publication journal; preserving resources and GC roots")

    def run(self, removing=False):
        with self.locked():
            self.recover()
            old_snapshot = byte_identity(self.state_file)
            old = self.load_state()
            try:
                new = self.preflight(old, removing)
                if byte_identity(self.state_file) != old_snapshot:
                    fail("ownership state changed during preflight; retry")
                # Config first: a CAS refusal before the first publication can
                # abandon this untouched attempt, so a retry parses fresh TOML.
                self.operations.sort(key=lambda item: item["kind"] != "config")
                roots = list(old["roots"])
                if not removing:
                    root = self.register_root()
                    if root not in roots:
                        roots.append(root)
                    new["environment"] = self.manifest["environment"]
                    new["roots"] = [root]
                # Unowned reused skills, native agents, or config may still
                # reference an earlier fixed closure. Retain conservatively.
                remnants = [record for record in old.get("reused", [])
                            if record["kind"] in ("skill", "agent", "mcp") and exists(record["source"])]
                if remnants:
                    new["roots"] = roots
                    new["reused"] += [record for record in remnants if record not in new["reused"]]
                    self.messages.append(f"Retained {len(roots)} GC root(s) for preserved unowned sources.")
                journal = {"schemaVersion": SCHEMA, "stage": self.stage.name,
                           "operations": self.operations, "newState": new,
                           "oldStateIdentity": old_snapshot, "oldRoots": old["roots"]}
                atomic_json(self.pending_file, journal)
                self.publish(journal, fresh=True)
            except SnapshotChanged:
                if self.completed_objects == 0:
                    # Nothing was published. Cancel the stale operation journal
                    # durably, retaining the registered roots for the next try.
                    cancelled = copy.deepcopy(journal)
                    cancelled["operations"] = []
                    cancelled["newState"] = copy.deepcopy(old)
                    cancelled["newState"]["roots"] = roots
                    atomic_json(self.pending_file, cancelled)
                    self.publish(cancelled)
                raise
            except Exception:
                if self.stage is not None and not exists(self.pending_file):
                    erase(self.stage)
                raise
        self.messages.append("Removed clean owned project resources." if removing else "Applied project agent environment.")
        return self.messages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("action", choices=("apply", "remove"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--extra-config", action="append", default=[])
    arguments = parser.parse_args(argv)
    try:
        manifest = json.loads(Path(arguments.manifest).read_text())
        runner = Activator(manifest, arguments.project, arguments.extra_config)
        for message in runner.run(removing=arguments.action == "remove"):
            print(f"agent-env: {message}")
        return 0
    except (ActivationError, OSError, ValueError) as exc:
        print(f"agent-env: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
