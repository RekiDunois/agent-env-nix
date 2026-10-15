"""Exercise the actual Nix-generated builder with temporary source fixtures."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="materialize ' fixture-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("A complete skill\n")
        self.output = self.base / "output"
        self.payload = self.output / "payload/skills/demo"
        # tests/default.nix extracts this script from the real derivation; only
        # the source literal changes so invalid trees can be made at test time.
        self.builder = Path(os.environ["AGENT_ENV_MATERIALIZE_BUILDER"]).read_text()
        source_lines = [line.strip() for line in self.builder.splitlines()
                        if line.strip().startswith("source=")]
        self.assertEqual(len(source_lines), 1)
        self.sentinel = source_lines[0]
        self.assertIn(self.sentinel, [
            "source=/agent-env-materialize-test-source",
            "source='/agent-env-materialize-test-source'",
        ])
        self.assertEqual(self.builder.count(self.sentinel), 1)

    def run_copy(self, source=None):
        script = self.builder.replace(self.sentinel, "source=" + shlex.quote(str(source or self.source)))
        return subprocess.run(
            ["bash", "-c", script],
            env={**os.environ, "out": str(self.output)},
            text=True, capture_output=True,
        )

    def assert_copied(self):
        result = self.run_copy()
        self.assertEqual(result.returncode, 0, result.stderr)

    def assert_rejected(self, message=None, source=None):
        result = self.run_copy(source=source)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        if message is not None:
            self.assertIn(message, result.stderr)

    def test_complete_tree_dotfiles_and_executable_bits(self):
        (self.source / "scripts").mkdir()
        script = self.source / "scripts/run"
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(0o755)
        (self.source / ".hidden").write_text("asset")
        (self.source / "empty").mkdir()
        self.assert_copied()
        self.assertEqual((self.payload / ".hidden").read_text(), "asset")
        self.assertEqual((self.payload / "scripts/run").stat().st_mode & 0o111, 0o111)
        self.assertTrue((self.payload / "empty").is_dir())

    def test_internal_links_materialized(self):
        (self.source / "alias").symlink_to("SKILL.md")
        (self.source / "assets").mkdir()
        (self.source / "assets/data").write_text("nested")
        (self.source / "linked-assets").symlink_to("assets", target_is_directory=True)
        self.assert_copied()
        target = self.payload / "alias"
        self.assertFalse(target.is_symlink())
        self.assertEqual(target.read_bytes(), (self.source / "SKILL.md").read_bytes())
        self.assertFalse((self.payload / "linked-assets").is_symlink())
        self.assertEqual((self.payload / "linked-assets/data").read_text(), "nested")

    def test_escape_rejected(self):
        (self.base / "outside").write_text("outside")
        (self.source / "escape").symlink_to("../outside")
        self.assert_rejected("escapes")
        self.assertFalse(self.payload.exists())

    def test_dangling_and_cyclic_links_rejected(self):
        for name, target in [("missing", "absent"), ("cycle", ".")]:
            with self.subTest(name=name):
                link = self.source / name
                link.symlink_to(target)
                self.assert_rejected()
                self.assertFalse(self.payload.exists())
                link.unlink()

    def test_top_level_link_rejected(self):
        link = self.base / "linked-source"
        link.symlink_to(self.source, target_is_directory=True)
        self.assert_rejected("non-symlink root", source=link)
        self.assertFalse(self.payload.exists())

    def test_special_file_rejected(self):
        os.mkfifo(self.source / "pipe")
        self.assert_rejected("special")
        self.assertFalse(self.payload.exists())

    def test_missing_skill_rejected(self):
        (self.source / "SKILL.md").unlink()
        self.assert_rejected("SKILL.md")


if __name__ == "__main__":
    unittest.main()
