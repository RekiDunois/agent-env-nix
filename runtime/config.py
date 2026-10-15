#!/usr/bin/env python3
"""Project-local MCP configuration only; the caller holds the project lock.

Config and MCP bookkeeping are separate atomic replacements. Generated-value
alternatives allow a retry after interruption without accepting user edits.
Whole-file comparison protects observed edits, not the final compare/replace race.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

import tomlkit

SCHEMA = 2
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


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


def empty_state():
    return {"schemaVersion": SCHEMA, "mcp": {}, "reused": [], "retainRoots": False}


def validate_state(state):
    if not isinstance(state, dict) or state.get("schemaVersion") != SCHEMA:
        fail("unsupported ownership state schema; no changes were made")
    if (set(state) != {"schemaVersion", "mcp", "reused", "retainRoots"}
            or not isinstance(state.get("mcp"), dict)
            or not isinstance(state.get("reused"), list)
            or not isinstance(state.get("retainRoots"), bool)):
        fail("invalid MCP ownership state")
    for name, record in state["mcp"].items():
        safe_name(name)
        if (not isinstance(record, dict) or not isinstance(record.get("owner"), str)
                or "value" not in record
                or record["value"] is not None and not isinstance(record["value"], dict)):
            fail(f"invalid MCP ownership record: {name}")
        alternatives = record.get("previousValues", [])
        if (not isinstance(alternatives, list)
                or any(value is not None and not isinstance(value, dict) for value in alternatives)):
            fail(f"invalid MCP generated alternatives: {name}")
    for item in state["reused"]:
        if (not isinstance(item, dict) or item.get("kind") != "mcp"
                or not isinstance(item.get("source"), str)
                or not Path(item["source"]).is_absolute()):
            fail("invalid reused MCP source")
        safe_name(item.get("name"))
    return state


def encoded(raw):
    return None if raw is None else base64.b64encode(raw).decode("ascii")


def decoded(raw):
    return None if raw is None else base64.b64decode(raw, validate=True)


class ConfigEditor:
    def __init__(self, manifest, project, extra_configs=(), *, state_file=None, system_config=None):
        self.manifest = manifest
        if manifest.get("schemaVersion") != 1:
            fail("unsupported project manifest schema")
        if not isinstance(manifest.get("mcpOwners", {}), dict):
            fail("invalid manifest MCP owners")
        for name, owner in manifest.get("mcpOwners", {}).items():
            safe_name(name)
            if not isinstance(owner, str):
                fail("invalid manifest MCP owner")
        if not isinstance(manifest.get("mcpConfig"), str) or not Path(manifest["mcpConfig"]).is_absolute():
            fail("manifest mcpConfig must be an absolute fixed path")
        project = Path(project).expanduser()
        if not project.is_dir():
            fail(f"project directory does not exist: {project}")
        self.project = project.resolve(strict=True)
        self.target = self.project / ".codex/config.toml"
        self.state_file = self.project / ".agent-env-nix/mcp-state.json"
        if state_file is not None and Path(state_file).absolute() != self.state_file:
            fail("MCP state must be the project's .agent-env-nix/mcp-state.json")
        self.extra_configs = [Path(p).expanduser().absolute() for p in extra_configs]
        self.system_config = (Path("/etc").resolve() / "codex/config.toml"
                              if system_config is None else Path(system_config))
        self.snapshots = {}

    def snapshot(self, path):
        path = Path(os.path.abspath(path))
        if str(path) not in self.snapshots:
            self.snapshots[str(path)] = encoded(read_bytes(path))
        return parse_toml(path, decoded(self.snapshots[str(path)]))

    def sources(self):
        candidates = [self.target]
        candidates += [parent / ".codex/config.toml" for parent in self.project.parents]
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
        if "CODEX_HOME" not in os.environ:
            home = Path.home().resolve() / ".codex"
        candidates += [home.absolute() / "config.toml", self.system_config]
        candidates += self.extra_configs
        result = []
        seen = set()
        for path in candidates:
            path = Path(os.path.abspath(path))
            if path not in seen:
                seen.add(path)
                result.append((path, self.snapshot(path)))
        return result

    def check_unsupported(self, sources, selected):
        for path, document in sources:
            profiles = document.get("profiles", {})
            if not isinstance(profiles, dict):
                continue
            for name, profile in profiles.items():
                values = profile.get("mcp_servers", {}) if isinstance(profile, dict) else {}
                if isinstance(values, dict) and set(values) & selected:
                    fail(f"unsupported selected mcp_servers source: profile {name} in {path}")
        managed = self.system_config.parent / "managed_config.toml"
        document = self.snapshot(managed)
        values = document.get("mcp_servers", {})
        if isinstance(values, dict) and set(values) & selected:
            fail(f"unsupported selected managed source: {managed} (mcp_servers)")

    def check_snapshots(self, snapshots, when):
        for path, expected in snapshots.items():
            if read_bytes(Path(path)) != decoded(expected):
                raise SnapshotChanged(f"config changed {when}; retry: {path}")

    def prepare(self, removing=False):
        raw_state = read_bytes(self.state_file)
        old = empty_state() if raw_state is None else validate_state(json.loads(raw_state))
        desired = {}
        self.snapshots = {}
        if not removing and self.manifest.get("mcpOwners"):
            generated = plain(self.snapshot(Path(self.manifest["mcpConfig"])))
            desired = generated.get("mcp_servers", {})
            if (set(generated) - {"mcp_servers"} or not isinstance(desired, dict)
                    or set(desired) != set(self.manifest["mcpOwners"])
                    or any(not isinstance(value, dict) for value in desired.values())):
                fail("generated MCP keys differ from manifest ownership keys")
        selected = set(desired) | set(old["mcp"])
        new = empty_state()
        # Once equal unowned config (or legacy reuse) needed roots, there is no
        # safe proof that its unchanged strings stopped referring to old stores.
        new["retainRoots"] = old["retainRoots"] or bool(old["reused"])
        changes = {}
        document = None
        if selected:
            sources = self.sources()
            self.check_unsupported(sources, selected)
            document = sources[0][1]
            table = document.get("mcp_servers", {})
            if not isinstance(table, dict):
                fail(f"mcp_servers must be a table in {self.target}")
            for name in sorted(selected):
                wanted, owned = desired.get(name), old["mcp"].get(name)
                current = plain(table.get(name))
                if owned and name in table and current not in [owned["value"], *owned.get("previousValues", [])]:
                    fail(f"package {owned['owner']}, MCP key {name}: owned value was edited in {self.target}; GC roots retained")
                if wanted is None:
                    if name in table:
                        changes[name] = None
                    continue
                others = []
                for path, source in sources:
                    values = source.get("mcp_servers", {})
                    if not isinstance(values, dict):
                        fail(f"mcp_servers must be a table in {path}")
                    if name not in values or (owned and path == self.target):
                        continue
                    if plain(values[name]) != wanted:
                        fail(f"package {self.manifest['mcpOwners'][name]}, MCP key {name}: conflicting selected definition in {path}")
                    others.append(path)
                if owned or not others:
                    if name not in table or current != wanted:
                        changes[name] = wanted
                    new["mcp"][name] = {"owner": self.manifest["mcpOwners"][name], "value": wanted}
                else:
                    new["reused"] += [{"kind": "mcp", "name": name, "source": str(path)} for path in others]
        new["retainRoots"] |= bool(new["reused"])
        pending = copy.deepcopy(old)
        pending["retainRoots"] = new["retainRoots"]
        for name, wanted in changes.items():
            previous = old["mcp"].get(name)
            # Only the observed generated alternative can survive this write;
            # earlier alternatives no longer need to confer ownership.
            alternatives = [plain(document.get("mcp_servers", {}).get(name))]
            pending["mcp"][name] = {
                "owner": (new["mcp"].get(name) or previous)["owner"],
                "value": wanted,
                "previousValues": alternatives,
            }
        self.check_snapshots(self.snapshots, "during preflight")
        return {"schemaVersion": SCHEMA, "project": str(self.project),
                "action": "remove" if removing else "apply",
                "stateSnapshot": encoded(raw_state), "sources": self.snapshots,
                "rendered": encoded(render_config(document, changes)) if changes else None,
                "pendingState": pending, "state": new}

    def commit(self, prepared, removing=False):
        if (prepared.get("schemaVersion") != SCHEMA
                or prepared.get("project") != str(self.project)
                or prepared.get("action") != ("remove" if removing else "apply")):
            fail("prepared MCP configuration does not match this invocation")
        new = validate_state(prepared["state"])
        pending = validate_state(prepared["pendingState"])
        if read_bytes(self.state_file) != decoded(prepared["stateSnapshot"]):
            raise SnapshotChanged("MCP ownership state changed; prepare again")
        self.check_snapshots(prepared["sources"], "before publication")
        safe_path(self.state_file.parent)
        if not self.state_file.parent.is_dir() or self.state_file.parent.stat().st_mode & 0o077:
            fail("MCP state directory must exist and be private (mode 0700)")
        rendered = decoded(prepared["rendered"])
        if rendered is not None:
            # Save only MCP generated alternatives before the config write. No
            # files, roots, progress counters, backups or replay operations.
            atomic_json(self.state_file, pending)
            safe_path(self.target)
            self.target.parent.mkdir(mode=0o755, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".mcp-", dir=self.target.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(rendered)
                    handle.flush()
                    os.fsync(handle.fileno())
                    if exists(self.target):
                        os.fchmod(handle.fileno(), stat.S_IMODE(self.target.stat().st_mode))
                self.check_snapshots(prepared["sources"], "immediately before publication")
                os.replace(temporary, self.target)
                sync_directory(self.target.parent)
            finally:
                if exists(temporary):
                    os.unlink(temporary)
        atomic_json(self.state_file, new)
        return new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "commit"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--action", choices=("apply", "remove"), required=True)
    parser.add_argument("--extra-config", action="append", default=[])
    args = parser.parse_args()
    try:
        manifest = json.loads(read_bytes(Path(args.manifest)))
        editor = ConfigEditor(manifest, args.project, args.extra_config, state_file=args.state)
        prepared = safe_path(Path(args.prepared).absolute())
        if not prepared.parent.is_dir() or prepared.parent.stat().st_mode & 0o077:
            fail("prepared MCP plan directory must be private (mode 0700)")
        if args.phase == "prepare":
            atomic_json(prepared, editor.prepare(args.action == "remove"))
        else:
            result = editor.commit(json.loads(read_bytes(prepared)), args.action == "remove")
            print("retain-roots" if result["retainRoots"] else "release-roots")
    except (ActivationError, OSError, ValueError, TypeError, KeyError) as exc:
        # JSON/TOML parser values can contain secrets; report only safe errors.
        message = str(exc) if isinstance(exc, ActivationError) else "cannot read or publish MCP configuration/state"
        print(f"agent-env: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
