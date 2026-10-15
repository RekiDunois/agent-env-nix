import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("materialize", Path(__file__).parents[1] / "runtime/materialize.py")
materialize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(materialize)


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("A complete skill\n")
        self.output = self.base / "output"

    def run_copy(self):
        materialize.materialize({"skills/demo": str(self.source)}, {"demo": "skills/demo"}, self.output)

    def test_complete_tree_dotfiles_and_executable_bits(self):
        (self.source / "scripts").mkdir()
        script = self.source / "scripts/run"
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(0o755)
        (self.source / ".hidden").write_text("asset")
        (self.source / "empty").mkdir()
        self.run_copy()
        self.assertEqual((self.output / "skills/demo/.hidden").read_text(), "asset")
        self.assertEqual((self.output / "skills/demo/scripts/run").stat().st_mode & 0o111, 0o111)
        self.assertTrue((self.output / "skills/demo/empty").is_dir())

    def test_internal_links_materialized(self):
        (self.source / "alias").symlink_to("SKILL.md")
        self.run_copy()
        target = self.output / "skills/demo/alias"
        self.assertFalse(target.is_symlink())
        self.assertEqual(target.read_bytes(), (self.source / "SKILL.md").read_bytes())

    def test_escape_rejected(self):
        (self.base / "outside").write_text("outside")
        (self.source / "escape").symlink_to("../outside")
        with self.assertRaisesRegex(materialize.MaterializeError, "escapes"):
            self.run_copy()

    def test_dangling_and_cyclic_links_rejected(self):
        for name, target in [("missing", "absent"), ("cycle", ".")]:
            with self.subTest(name=name):
                link = self.source / name
                link.symlink_to(target)
                with self.assertRaises(materialize.MaterializeError):
                    materialize.materialize({"skill": str(self.source)}, {"demo": "skill"}, self.base / name)
                link.unlink()

    def test_special_file_rejected(self):
        os.mkfifo(self.source / "pipe")
        with self.assertRaisesRegex(materialize.MaterializeError, "special"):
            self.run_copy()

    def test_overlap_and_unsafe_paths_rejected(self):
        for files in [{"a": str(self.source), "a/b": str(self.source)}, {"../escape": str(self.source)}, {"/absolute": str(self.source)}]:
            with self.subTest(files=files), self.assertRaises(materialize.MaterializeError):
                materialize.materialize(files, {}, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_skill_rejected(self):
        with self.assertRaisesRegex(materialize.MaterializeError, "SKILL.md"):
            materialize.materialize({"skill": str(self.source)}, {"demo": "missing"}, self.output)

    def test_nonempty_output_rejected(self):
        self.output.mkdir()
        (self.output / "keep").write_text("keep")
        with self.assertRaises(materialize.MaterializeError):
            self.run_copy()
        self.assertEqual((self.output / "keep").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
