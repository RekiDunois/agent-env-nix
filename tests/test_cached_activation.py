"""Offline wrapper checks with a stub installer; no Nix build or real install."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ActivationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.marker = self.project / ".agent-env-applied"
        self.lock = self.project / ".agent-env-apply.lock"
        self.log = self.root / "calls"
        self.env = dict(os.environ, CALL_LOG=str(self.log))
        self.a = self.wrapper("environment-a")
        self.b = self.wrapper("environment-b")

    def wrapper(self, name):
        environment = self.root / name
        (environment / "bin").mkdir(parents=True)
        installer = environment / "bin/agent-env"
        installer.write_text(
            f'#!{shutil.which("bash")}\nset -eu\n'
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

    def test_first_skip_upgrade_force(self):
        self.run_activation()
        self.run_activation()
        self.assertEqual(len(self.calls()), 1)
        self.run_activation(self.b)
        self.run_activation(self.b, "--force")
        self.assertEqual(len(self.calls()), 3)
        self.assertFalse(self.lock.exists())

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
