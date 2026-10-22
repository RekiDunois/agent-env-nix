"""Existing activation failure scenarios through the generated shell entry.

Fake nix-store only tests orchestration; integration.sh checks real GC roots.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


class ShellActivationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.shebang = "#!" + shutil.which("bash") + "\n"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / ".codex"),
                        PATH=str(self.bin) + os.pathsep + os.environ["PATH"])
        script = Path(os.environ["AGENT_ENV_ACTIVATION_SCRIPT"]).read_text()
        self.manifest = self.base / "manifest.json"
        source = next(line.split("=", 1)[1] for line in script.splitlines() if line.startswith("manifest="))
        manifest = json.loads(Path(source).read_text())
        manifest["mcpOwners"] = {}
        self.manifest.write_text(json.dumps(manifest))
        self.nix_store = self.bin / "nix-store"
        self.nix_store.write_text(self.shebang + 'set -eu\nenvironment=$2\nshift 2\nwhile [ "$1" != --add-root ]; do shift; done\n[ -L "$2" ] || ln -s -- "$environment" "$2"\n')
        self.nix_store.chmod(0o755)
        self.environment = "/nix/store/00000000000000000000000000000000-activation-fixture"
        replacements = {"manifest": str(self.manifest), "nix_store": str(self.nix_store), "environment": self.environment}
        self.script = self.base / "activate.sh"
        self.script.write_text("\n".join(
            key + "=" + shlex.quote(replacements[key]) if (key := line.split("=", 1)[0]) in replacements else line
            for line in script.splitlines()) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def run_activation(self, action="apply", succeeds=True):
        result = subprocess.run(["bash", str(self.script), action, "--project", str(self.project)],
                                env=self.env, text=True, capture_output=True)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_root_registration_failure_prevents_publication(self):
        self.nix_store.write_text(self.shebang + "exit 1\n")
        self.run_activation(succeeds=False)
        self.assertFalse((self.project / ".agents/skills/example").exists())
        self.assertFalse((self.project / ".codex/agents/example.toml").exists())

    def test_directory_links_support_apply_upgrade_remove(self):
        external = self.base / "outside with spaces"
        external.mkdir()
        for name in (".agents", ".codex"):
            target = external / name
            target.mkdir()
            (self.project / name).symlink_to(target)
        skills = external / "skills"
        skills.mkdir()
        (self.project / ".agents/skills").symlink_to(skills)
        roles = external / "roles"
        roles.mkdir()
        (self.project / ".codex/agents").symlink_to(roles)
        (skills / "unrelated").mkdir()
        (skills / "unrelated/keep").write_text("keep")
        self.run_activation()
        self.assertTrue((skills / "example/SKILL.md").is_file())
        self.assertTrue((roles / "example.toml").is_file())
        (skills / "example/stale").write_text("generated edit")
        self.run_activation()
        self.assertFalse((skills / "example/stale").exists())
        self.run_activation("remove")
        self.assertFalse((skills / "example").exists())
        self.assertFalse((roles / "example.toml").exists())
        self.assertEqual((skills / "unrelated/keep").read_text(), "keep")
        for relative in (".agents", ".agents/skills", ".codex", ".codex/agents"):
            self.assertTrue((self.project / relative).is_symlink())

    def test_invalid_directory_link_is_not_replaced(self):
        target = self.base / "missing"
        link = self.project / ".agents"
        link.symlink_to(target)
        self.run_activation(succeeds=False)
        self.assertTrue(link.is_symlink())
        self.assertFalse(target.exists())
        target.write_text("not a directory")
        self.run_activation(succeeds=False)
        self.assertEqual(target.read_text(), "not a directory")

    def test_selected_leaf_symlink_is_replaced_without_following(self):
        external = self.base / "outside"
        external.mkdir()
        (external / "keep").write_text("outside")
        parent = self.project / ".agents/skills"
        parent.mkdir(parents=True)
        (parent / "example").symlink_to(external)
        self.run_activation()
        self.assertFalse((parent / "example").is_symlink())
        self.assertTrue((parent / "example/SKILL.md").is_file())
        self.assertEqual((external / "keep").read_text(), "outside")

    def test_interrupted_file_copy_reruns_without_journal(self):
        real_cp = shutil.which("cp")
        fail_once = self.base / "fail-once"
        fail_once.touch()
        cp = self.bin / "cp"
        cp.write_text(self.shebang + 'set -eu\n'
                      + 'if [[ "${@: -1}" == */.codex/agents/example.toml ]] && [ -f ' + shlex.quote(str(fail_once)) + ' ]; then\n'
                      + 'rm -- ' + shlex.quote(str(fail_once)) + '; exit 1\nfi\nexec ' + shlex.quote(real_cp) + ' "$@"\n')
        cp.chmod(0o755)
        self.run_activation(succeeds=False)
        state = self.project / ".agent-env-nix"
        self.assertEqual((state / "skills.list").read_text(), "example\n")
        self.assertEqual((state / "agents.list").read_text(), "example\n")
        self.assertFalse((state / "pending.json").exists())
        self.assertEqual(len(list((state / "roots").iterdir())), 1)
        skill = self.project / ".agents/skills/example/SKILL.md"
        skill.write_text("partial edit")
        self.run_activation()
        self.assertNotEqual(skill.read_text(), "partial edit")
        self.assertTrue((self.project / ".codex/agents/example.toml").is_file())
        self.run_activation("remove")
        self.assertEqual(list((state / "roots").iterdir()), [])

    def test_generation_switch_releases_old_root_only_after_success(self):
        self.run_activation()
        roots = self.project / ".agent-env-nix/roots"
        old_root = next(roots.iterdir())
        updated = "/nix/store/11111111111111111111111111111111-activation-fixture"
        self.script.write_text(self.script.read_text().replace(self.environment, updated))
        real_cp = shutil.which("cp")
        cp = self.bin / "cp"
        cp.write_text(self.shebang
                      + 'if [[ "${@: -1}" == */.codex/agents/example.toml ]]; then exit 1; fi\n'
                      + 'exec ' + shlex.quote(real_cp) + ' "$@"\n')
        cp.chmod(0o755)
        self.run_activation(succeeds=False)
        self.assertTrue(old_root.is_symlink())
        self.assertEqual(len(list(roots.iterdir())), 2)
        cp.unlink()
        self.run_activation()
        self.assertFalse(old_root.is_symlink())
        remaining = list(roots.iterdir())
        self.assertEqual(len(remaining), 1)
        self.assertEqual(str(remaining[0].readlink()), updated)

    def test_legacy_inventory_conversion_and_unknown_schema(self):
        state = self.project / ".agent-env-nix"
        state.mkdir(mode=0o700)
        old_skill = self.project / ".agents/skills/old"
        old_skill.mkdir(parents=True)
        (old_skill / "SKILL.md").write_text("previously selected")
        legacy = {"schemaVersion": 1, "skills": {"old": {"owner": "producer"}},
                  "agents": {}, "mcp": {}, "reused": [], "roots": []}
        (state / "state.json").write_text(json.dumps(legacy))
        self.run_activation()
        self.assertFalse(old_skill.exists())
        self.assertEqual(json.loads((state / "state.json").read_text())["schemaVersion"], 2)
        (state / "state.json").write_text('{"schemaVersion":99}')
        self.run_activation(succeeds=False)
        self.assertTrue((self.project / ".agents/skills/example/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
