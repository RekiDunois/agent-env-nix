"""Offline wrapper checks with a stub installer; no Nix build or real install."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import unittest


class ActivationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS /var is a symlink to /private/var; the wrapper resolves physical paths.
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.marker = self.project / ".agent-env-applied"
        self.lock = self.project / ".agent-env-apply.lock"
        self.log = self.root / "calls"
        self.env = dict(os.environ, CALL_LOG=str(self.log))
        self.env.pop("TEST_MCP_PORT", None)
        self.a = self.wrapper("environment-a")
        self.b = self.wrapper("environment-b")

    def wrapper(self, name):
        environment = self.root / name
        (environment / "bin").mkdir(parents=True)
        for file in ("mcp-proxy.json", "mcp-connections.json"):
            (environment / file).write_text(json.dumps({"fixture": name, "file": file}))
        installer = environment / "bin/agent-env"
        installer.write_text(
            f'#!{shutil.which("bash")}\nset -eu\n'
            'if [[ $1 == cache-key ]]; then printf "static\\n"; exit; fi\n'
            '[[ $1 == apply && $2 == --project && $# == 3 ]]\n'
            'printf "%s\\n" "$3" >> "$CALL_LOG"\n'
            '[[ ${FAIL_APPLY:-0} != 1 ]]\n'
        )
        installer.chmod(0o755)
        template = (Path(__file__).resolve().parents[1] / "runtime/cached-activate.sh").read_text()
        # Exercise exactly the source packaged by cached-activation.nix, with host tools.
        script = self.root / name.replace("environment", "activate")
        script.write_text(template.replace("@environment@", str(environment))
                          .replace("@name@", name.replace("environment", "activate"))
                          .replace("@bash@", str(Path(shutil.which("bash")).parent.parent))
                          .replace("@coreutils@", str(Path(shutil.which("mkdir")).parent.parent)))
        script.chmod(0o755)
        return script

    def run_activation(self, script=None, *args, success=True):
        result = subprocess.run([str(script or self.a), *args], cwd=self.project,
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_real_port_resolver_cache_and_literal_publication(self):
        environment = self.root / "environment-a"
        config = environment / "mcp.toml"
        config.write_text('[mcp_servers.demo]\nurl = "http://localhost:9090/mcp"\n')
        manifest = environment / "manifest.json"
        manifest.write_text(json.dumps({"schemaVersion": 1, "mcpConfig": str(config),
                                       "mcpOwners": {"demo": "producer"},
                                       "mcpPortEnv": {"demo": "TEST_MCP_PORT"}}))
        helper = Path(__file__).resolve().parents[1] / "runtime/config.py"
        installer = environment / "bin/agent-env"
        installer.write_text(f'''#!{sys.executable}
import importlib.util, json, os, pathlib, sys
spec = importlib.util.spec_from_file_location("config", {str(helper)!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
manifest_path = {str(manifest)!r}
if sys.argv[1] == "cache-key":
    sys.argv = [sys.argv[0], "cache-key", "--manifest", manifest_path]
    sys.exit(m.main())
project = pathlib.Path(sys.argv[3])
with open(os.environ["CALL_LOG"], "a") as log:
    log.write(str(project) + "\\n")
if os.environ.get("FAIL_APPLY") == "1":
    sys.exit(1)
(project / ".agent-env-nix").mkdir(mode=0o700, exist_ok=True)
editor = m.ConfigEditor(json.loads(pathlib.Path(manifest_path).read_text()), project,
                        system_config=project / "absent-system.toml")
editor.commit(editor.prepare())
''')
        self.env["HOME"] = str(self.root / "home")
        self.env["CODEX_HOME"] = str(self.root / "home/.codex")
        self.run_activation()
        self.env["TEST_MCP_PORT"] = "09090"
        self.run_activation()  # Same effective URL: a cache hit.
        self.assertEqual(len(self.calls()), 1)
        self.env["TEST_MCP_PORT"] = "8000"
        self.run_activation()
        self.assertEqual(len(self.calls()), 2)
        self.assertIn('url = "http://localhost:8000/mcp"',
                      (self.project / ".codex/config.toml").read_text())
        before = (self.project / ".codex/config.toml").read_bytes()
        self.env["TEST_MCP_PORT"] = ""
        self.run_activation(success=False)
        self.assertFalse(self.marker.exists())
        self.assertEqual((self.project / ".codex/config.toml").read_bytes(), before)
        self.assertEqual(len(self.calls()), 2)
        self.env["TEST_MCP_PORT"] = "8001"
        self.env["FAIL_APPLY"] = "1"
        self.run_activation(success=False)
        self.assertFalse(self.marker.exists())
        del self.env["FAIL_APPLY"]
        self.run_activation()
        self.assertEqual(len(self.calls()), 4)

    def test_first_skip_upgrade_force(self):
        self.run_activation()
        self.run_activation()
        self.assertEqual(len(self.calls()), 1)
        self.run_activation(self.b)
        self.run_activation(self.b, "--force")
        self.assertEqual(len(self.calls()), 3)
        self.assertFalse(self.lock.exists())

    def test_cached_export_overwrites_and_recreates_generated_fragments(self):
        self.run_activation()
        outside = self.root / "outside"
        outside.write_text("untouched")
        (self.project / "mcp-proxy.json").symlink_to(outside)
        (self.project / "mcp-connections.json").write_text("old or edited")
        result = self.run_activation()
        for file in ("mcp-proxy.json", "mcp-connections.json"):
            target = self.project / file
            self.assertEqual(target.read_bytes(), (self.root / "environment-a" / file).read_bytes())
            self.assertFalse(target.is_symlink())
            self.assertIn(str(target), result.stdout)
            target.unlink()
        self.assertEqual(outside.read_text(), "untouched")
        self.run_activation()
        self.assertTrue((self.project / "mcp-proxy.json").is_file())
        self.assertTrue((self.project / "mcp-connections.json").is_file())
        self.assertEqual(len(self.calls()), 1)

    def test_different_entrypoints_share_project_state(self):
        self.run_activation()
        self.run_activation(self.b)
        self.run_activation()  # B replaced A: A must apply again.
        self.assertEqual(len(self.calls()), 3)
        self.lock.mkdir()
        self.run_activation(self.b, success=False)
        self.assertEqual(len(self.calls()), 3)
        self.lock.rmdir()

    def test_help_and_newline_path(self):
        self.assertIn("Usage: activate-a", self.run_activation(self.a, "--help").stdout)
        bad = self.root / "line\n"
        bad.mkdir()
        self.run_activation(self.a, "--project", str(bad), success=False)
        self.assertEqual(self.calls(), [])

    def test_failure_invalidates_old_marker_and_retries(self):
        self.run_activation()
        self.env["FAIL_APPLY"] = "1"
        self.run_activation(self.b, success=False)
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.lock.exists())
        del self.env["FAIL_APPLY"]
        self.run_activation()  # Rollback must apply, not trust the old success.
        self.assertEqual(len(self.calls()), 3)
        self.env["FAIL_APPLY"] = "1"
        self.run_activation(self.a, "--force", success=False)
        self.assertFalse(self.marker.exists())

    def test_physical_path_and_move(self):
        link = self.root / "alias"
        link.symlink_to(self.project, target_is_directory=True)
        self.run_activation(self.a, "--project", str(link))
        self.run_activation()
        self.assertEqual(self.calls(), [str(self.project)])
        moved = self.root / "moved"
        self.project.rename(moved)
        self.project = moved
        self.run_activation()
        self.assertEqual(self.calls(), [str(self.root / "project with spaces"), str(moved)])

    def test_relative_project_ignores_cdpath(self):
        intended = self.project / "demo"
        intended.mkdir()
        other = self.root / "other"
        wrong = other / "demo"
        wrong.mkdir(parents=True)
        self.env["CDPATH"] = str(other)
        self.run_activation(self.a, "--project", "demo")
        self.assertEqual(self.calls(), [str(intended)])
        self.assertTrue((intended / ".agent-env-applied").is_file())
        self.assertEqual(list(wrong.iterdir()), [])

    def test_reject_unsafe_marker_lock_and_bad_args(self):
        target = self.root / "untouched"
        target.write_text("keep")
        self.marker.symlink_to(target)
        self.run_activation(success=False)
        self.assertEqual(target.read_text(), "keep")
        self.marker.unlink()
        self.marker.mkdir()
        self.run_activation(success=False)
        self.marker.rmdir()
        self.lock.mkdir()
        self.run_activation(success=False)
        self.lock.rmdir()
        for args in [("--project",), ("--project", "--force"), ("--unknown",)]:
            self.run_activation(self.a, *args, success=False)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()

