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
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit

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
    """Allow directory-link ancestors, but never replace a linked config/state file."""
    path = Path(path)
    if not path.is_absolute():
        fail(f"expected an absolute path: {path}")
    for part in reversed([path, *path.parents]):
        try:
            mode = part.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            if part == path or not part.is_dir():
                fail(f"symlink is not an allowed activation path: {part}")
            continue
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


def desired_mcp(manifest, snapshot=parse_toml):
    """Resolve producer port metadata before ownership checks or cache comparison."""
    owners = manifest.get("mcpOwners", {})
    generated = plain(snapshot(Path(manifest["mcpConfig"]))) if owners else {}
    desired = generated.get("mcp_servers", {})
    if (set(generated) - {"mcp_servers"} or not isinstance(desired, dict)
            or set(desired) != set(owners)
            or any(not isinstance(value, dict) for value in desired.values())):
        fail("generated MCP keys differ from manifest ownership keys")
    ports = manifest.get("mcpPortEnv", {})
    if not isinstance(ports, dict):
        fail("invalid manifest MCP port environment mapping")
    for name, variable in ports.items():
        if (name not in desired or not isinstance(variable, str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable)):
            fail("invalid manifest MCP port environment mapping")
        url = desired[name].get("url")
        try:
            if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url):
                raise ValueError
            parsed = urlsplit(url)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or not re.fullmatch(r"(?:\[[^\[\]]+\]|[^:\[\]\\]+)(?::[0-9]+)?", parsed.netloc)
                    or parsed.port is not None and not 1 <= parsed.port <= 65535
                    or "command" in desired[name]):
                raise ValueError
        except ValueError:
            fail(f"MCP key {name}: invalid default HTTP URL for port environment mapping")
        value = os.environ.get(variable)
        if value is None:
            continue
        # Bound length before int conversion; avoid enormous/untrusted integers.
        if not re.fullmatch(r"[0-9]{1,5}", value) or not 1 <= int(value) <= 65535:
            fail(f"MCP key {name}: {variable} must be a decimal port in 1..65535")
        host = parsed.netloc.rsplit(":", 1)[0] if parsed.port is not None else parsed.netloc
        authority_start = url.index(":") + 3  # Preserve all original non-port bytes.
        authority_end = authority_start + len(parsed.netloc)
        desired[name]["url"] = url[:authority_start] + f"{host}:{int(value)}" + url[authority_end:]
    return desired


def dsh_mcp(desired, project):
    """Project existing declarations; never expand secret-bearing environment values."""
    result = {}
    variable = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def reference(name):
        if not isinstance(name, str) or not variable.fullmatch(name):
            fail("DSH MCP environment reference must name an environment variable")
        return "${" + name + "}"

    def literal(value):
        if isinstance(value, str) and "${" in value:
            fail("DSH MCP literal contains plugin interpolation syntax; use a named environment field")
        if isinstance(value, list):
            return [literal(item) for item in value]
        if isinstance(value, dict):
            return {key: literal(item) for key, item in value.items()}
        return value

    for name, source in desired.items():
        if source.get("enabled") is False:
            result[name] = {"disabled": True}
            continue
        if "enabled_tools" in source or source.get("disabled_tools"):
            fail(f"MCP key {name}: DSH plugin cannot preserve tool allow/deny filters")
        value = {}
        timeout = source.get("tool_timeout_sec")
        if timeout is not None:
            milliseconds = timeout * 1000
            if (not isinstance(milliseconds, (int, float)) or isinstance(milliseconds, bool)
                    or not 0 < milliseconds <= 9007199254740991
                    or milliseconds != int(milliseconds)):
                fail(f"MCP key {name}: DSH tool timeout must be positive whole milliseconds")
            value["toolCallTimeoutMs"] = int(milliseconds)
        if "url" in source:
            value.update(type="http", url=literal(source["url"]))
            headers = literal(dict(source.get("http_headers", {})))
            seen = {key.lower() for key in headers}
            if len(seen) != len(headers):
                fail(f"MCP key {name}: ambiguous HTTP header names")
            for key, env_name in source.get("env_http_headers", {}).items():
                if key.lower() in seen:
                    fail(f"MCP key {name}: ambiguous HTTP header sources")
                headers[key] = reference(env_name)
                seen.add(key.lower())
            if source.get("bearer_token_env_var"):
                if "authorization" in seen:
                    fail(f"MCP key {name}: ambiguous Authorization sources")
                headers["Authorization"] = "Bearer " + reference(source["bearer_token_env_var"])
            if headers:
                value["headers"] = headers
        else:
            value.update(type="stdio", command=literal(source["command"]))
            if "args" in source:
                value["args"] = literal(source["args"])
            env = literal(dict(source.get("env", {})))
            for key in source.get("env_vars", []):
                ref = reference(key)
                if key in env:
                    fail(f"MCP key {name}: ambiguous environment sources")
                env[key] = ref
            if env:
                value["env"] = env
            cwd = Path(source.get("cwd", str(project)))
            value["cwd"] = str(cwd if cwd.is_absolute() else project / cwd)
        result[name] = value
    return result


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
    target_relative = ".codex/config.toml"
    state_relative = ".agent-env-nix/mcp-state.json"
    table_key = "mcp_servers"

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
        self.target = self.project / self.target_relative
        self.state_file = self.project / self.state_relative
        if state_file is not None and Path(state_file).absolute() != self.state_file:
            fail("MCP state must be the project's owned state file")
        self.extra_configs = [Path(p).expanduser().absolute() for p in extra_configs]
        self.system_config = (Path("/etc").resolve() / "codex/config.toml"
                              if system_config is None else Path(system_config))
        self.snapshots = {}

    def snapshot(self, path):
        path = Path(os.path.abspath(path))
        if str(path) not in self.snapshots:
            self.snapshots[str(path)] = encoded(read_bytes(path))
        return self.parse_source(path, decoded(self.snapshots[str(path)]))

    def parse_source(self, path, raw):
        return parse_toml(path, raw)

    def desired(self):
        if hasattr(self, "resolved_mcp"):
            # Still snapshot the fixed generated source for publication checks.
            self.snapshot(Path(self.manifest["mcpConfig"]))
            return copy.deepcopy(self.resolved_mcp)
        return desired_mcp(self.manifest, self.snapshot)

    def render(self, document, changes):
        return render_config(document, changes)

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
        values = document.get(self.table_key, {})
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
        if not removing:
            desired = self.desired()
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
            table = document.get(self.table_key, {})
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
                    values = source.get(self.table_key, {})
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
            alternatives = [plain(document.get(self.table_key, {}).get(name))]
            pending["mcp"][name] = {
                "owner": (new["mcp"].get(name) or previous)["owner"],
                "value": wanted,
                "previousValues": alternatives,
            }
        self.check_snapshots(self.snapshots, "during preflight")
        return {"schemaVersion": SCHEMA, "project": str(self.project),
                "action": "remove" if removing else "apply",
                "stateSnapshot": encoded(raw_state), "sources": self.snapshots,
                "rendered": encoded(self.render(document, changes)) if changes else None,
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


class DshConfigEditor(ConfigEditor):
    target_relative = ".dsh/mcp.json"
    state_relative = ".agent-env-nix/dsh-mcp-state.json"
    table_key = "mcpServers"

    def parse_source(self, path, raw):
        if path == Path(self.manifest["mcpConfig"]):
            return parse_toml(path, raw)
        try:
            document = {} if raw is None else json.loads(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            fail(f"invalid JSON source: {path}")
        if not isinstance(document, dict):
            fail(f"MCP JSON must be an object: {path}")
        return document

    def sources(self):
        return [(self.target, self.snapshot(self.target))]

    def check_unsupported(self, sources, selected):
        # DSH has no Codex inherited TOML sources. Do not hide its fallback file.
        if getattr(self, "generating", False) and not exists(self.target):
            fallback = self.project / ".mcp.json"
            raw = read_bytes(fallback)
            self.snapshots[str(fallback)] = encoded(raw)
            if raw is not None:
                fail("DSH output would hide existing .mcp.json; reconcile project MCP configuration first")

    def desired(self):
        desired = dsh_mcp(super().desired(), self.project)
        self.generating = bool(desired)
        return desired

    def render(self, document, changes):
        result = copy.deepcopy(document)
        table = result.setdefault(self.table_key, {})
        for name, value in changes.items():
            if value is None:
                table.pop(name, None)
            else:
                table[name] = value
        return (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def output_editors(manifest, project, extra_configs=(), state_file=None):
    editors = [("codex", ConfigEditor(manifest, project, extra_configs, state_file=state_file))]
    if manifest.get("dshMcp", False) or exists(Path(project).resolve() / DshConfigEditor.state_relative):
        editors.append(("dsh", DshConfigEditor(manifest, project)))
    return editors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "commit", "cache-key"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project")
    parser.add_argument("--state")
    parser.add_argument("--prepared")
    parser.add_argument("--action", choices=("apply", "remove"))
    parser.add_argument("--extra-config", action="append", default=[])
    args = parser.parse_args()
    try:
        manifest = json.loads(read_bytes(Path(args.manifest)))
        if args.phase == "cache-key":
            value = json.dumps({"mcp": desired_mcp(manifest), "dshMcp": manifest.get("dshMcp", False)}, sort_keys=True, separators=(",", ":"))
            print(hashlib.sha256(value.encode()).hexdigest())
            return 0
        if not all((args.project, args.state, args.prepared, args.action)):
            parser.error("prepare/commit require --project, --state, --prepared and --action")
        editors = output_editors(manifest, args.project, args.extra_config, args.state)
        prepared = safe_path(Path(args.prepared).absolute())
        if not prepared.parent.is_dir() or prepared.parent.stat().st_mode & 0o077:
            fail("prepared MCP plan directory must be private (mode 0700)")
        if args.phase == "prepare":
            resolved = desired_mcp(manifest) if args.action != "remove" else {}
            plans = {}
            for kind, editor in editors:
                editor.resolved_mcp = resolved
                removing = args.action == "remove" or kind == "dsh" and not manifest.get("dshMcp", False)
                plans[kind] = editor.prepare(removing)
            atomic_json(prepared, plans)
        else:
            plans = json.loads(read_bytes(prepared))
            if set(plans) != {kind for kind, _ in editors}:
                fail("prepared MCP outputs differ from this invocation")
            # Preflight every output before publishing either one. Each editor
            # also checks immediately before its own replacement.
            for kind, editor in editors:
                plan = plans[kind]
                if read_bytes(editor.state_file) != decoded(plan["stateSnapshot"]):
                    raise SnapshotChanged("MCP ownership state changed; prepare again")
                editor.check_snapshots(plan["sources"], "before publication")
            retain = False
            for kind, editor in editors:
                removing = args.action == "remove" or kind == "dsh" and not manifest.get("dshMcp", False)
                retain |= editor.commit(plans[kind], removing)["retainRoots"]
            print("retain-roots" if retain else "release-roots")
    except (ActivationError, OSError, ValueError, TypeError, KeyError) as exc:
        # JSON/TOML parser values can contain secrets; report only safe errors.
        message = str(exc) if isinstance(exc, ActivationError) else "cannot read or publish MCP configuration/state"
        print(f"agent-env: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

