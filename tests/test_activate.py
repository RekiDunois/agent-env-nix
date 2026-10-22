"""Offline MCP-only checks; shell integration covers file and root lifecycle."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tomlkit

SPEC = importlib.util.spec_from_file_location("config", Path(__file__).parents[1] / "runtime/config.py")
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / ".agent-env-nix").mkdir(mode=0o700)
        self.home = self.base / "home"
        self.home.mkdir()
        self.env_patch = patch.dict(os.environ, {"HOME": str(self.home), "CODEX_HOME": str(self.home / ".codex")})
        self.env_patch.start()
        self.mcp = self.base / "mcp.toml"
        self.mcp.write_text('[mcp_servers.fetch]\ncommand = "/nix/store/fixed-fetch/bin/fetch"\nargs = ["--safe"]\n')
        self.manifest = {"schemaVersion": 1, "mcpConfig": str(self.mcp), "mcpOwners": {"fetch": "producer"}}
        self.system_config = self.base / "etc/codex/config.toml"

    def tearDown(self):
        self.env_patch.stop()
        self.temporary.cleanup()

    def runner(self, **kwargs):
        return a.ConfigEditor(self.manifest, self.project, system_config=self.system_config, **kwargs)

    def apply(self, **kwargs):
        runner = self.runner(**kwargs)
        return runner.commit(runner.prepare())

    def remove(self):
        runner = self.runner()
        return runner.commit(runner.prepare(removing=True), removing=True)

    def state(self):
        return json.loads((self.project / ".agent-env-nix/mcp-state.json").read_text())

    def write(self, relative, text):
        target = self.project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def assert_no_published(self):
        self.assertFalse((self.project / ".agent-env-nix/mcp-state.json").exists())

    def test_directory_link_preserves_config_edits_and_link(self):
        external = self.base / "external codex"
        external.mkdir()
        link = self.project / ".codex"
        link.symlink_to(external)
        config = external / "config.toml"
        config.write_text('# user config\nmodel = "mine"\n')
        self.apply()
        self.assertTrue(link.is_symlink())
        self.assertIn('# user config', config.read_text())
        config.write_text(config.read_text().replace('args = ["--safe"]', 'args = ["--user"]'))
        with self.assertRaises(a.ActivationError):
            self.remove()
        self.assertTrue(link.is_symlink())
        self.assertIn('--user', config.read_text())

    def test_unrelated_settings_comments_and_siblings_survive(self):
        config = self.write(".codex/config.toml", '# important comment\nmodel = "mine" # inline\n[unknown.future]\nx = 3\n[mcp_servers.other]\nurl = "https://example.com"\n')
        sibling = self.write(".agents/skills/unrelated/SKILL.md", "not owned")
        self.apply()
        self.assertIn('# important comment\nmodel = "mine" # inline', config.read_text())
        self.assertEqual(tomlkit.parse(config.read_text())["unknown"]["future"]["x"], 3)
        self.remove()
        self.assertEqual(sibling.read_text(), "not owned")
        self.assertEqual(tomlkit.parse(config.read_text())["mcp_servers"]["other"]["url"], "https://example.com")

    def test_edited_owned_mcp_is_preserved(self):
        self.apply()
        config = self.project / ".codex/config.toml"
        config.write_text(config.read_text().replace("--safe", "--local"))
        with self.assertRaisesRegex(a.ActivationError, "owned value was edited"):
            self.apply()
        self.assertIn("--local", config.read_text())

    def test_global_conflict_fails_without_masking(self):
        path = self.home / ".codex/config.toml"
        path.parent.mkdir()
        path.write_text('[mcp_servers.fetch]\ncommand = "/different"\n')
        with self.assertRaisesRegex(a.ActivationError, "conflicting selected definition"):
            self.apply()
        self.assert_no_published()

    def test_ancestor_and_extra_sources_checked_even_when_local_equal(self):
        self.write(".codex/config.toml", self.mcp.read_text())
        extra = self.base / "extra.toml"
        extra.write_text('[mcp_servers.fetch]\nurl = "https://different.example"\n')
        with self.assertRaisesRegex(a.ActivationError, "extra.toml"):
            self.apply(extra_configs=[extra])
        self.assert_no_published()

    def test_profile_selected_source_is_explicitly_unsupported(self):
        self.write(".codex/config.toml", '[profiles.work.mcp_servers.fetch]\ncommand = "/other"\n')
        with self.assertRaisesRegex(a.ActivationError, "unsupported selected"):
            self.apply()
        self.assert_no_published()

    def test_selected_unknown_mcp_fields_participate_in_equality(self):
        self.write(".codex/config.toml", self.mcp.read_text() + "future_field = true\n")
        with self.assertRaisesRegex(a.ActivationError, "conflicting selected definition"):
            self.apply()

    def test_malformed_config_fails_without_publishing(self):
        self.write(".codex/config.toml", "not valid [toml")
        with self.assertRaisesRegex(a.ActivationError, "invalid TOML"):
            self.apply()
        self.assert_no_published()

    def test_owned_mcp_comment_survives_unchanged_apply(self):
        self.apply()
        config = self.project / ".codex/config.toml"
        config.write_text(config.read_text().replace('args = ["--safe"]', 'args = ["--safe"] # user comment'))
        before = config.read_bytes()
        self.apply()
        self.assertEqual(config.read_bytes(), before)

    def test_skill_only_selection_does_not_audit_unrelated_toml(self):
        self.manifest["mcpOwners"] = {}
        self.mcp.write_text("")
        config = self.write(".codex/config.toml", "unrelated invalid TOML [")
        self.apply()
        self.assertEqual(config.read_text(), "unrelated invalid TOML [")

    def test_config_snapshot_comes_from_the_exact_parsed_bytes(self):
        config = self.write(".codex/config.toml", '# original\nmodel = "original"\n')
        runner = self.runner()
        sources = runner.sources
        def edited_after_parse():
            parsed = sources()
            config.write_text('# fresh unrelated edit\nmodel = "newer"\n')
            return parsed
        with patch.object(runner, "sources", side_effect=edited_after_parse):
            with self.assertRaisesRegex(a.ActivationError, "config changed during preflight"):
                runner.prepare()
        self.assertEqual(config.read_text(), '# fresh unrelated edit\nmodel = "newer"\n')
        self.assert_no_published()

    def test_repeated_apply_is_idempotent(self):
        self.apply()
        state = self.state()
        before = (self.project / ".codex/config.toml").read_bytes()
        self.apply()
        self.assertEqual(state, self.state())
        self.assertEqual(before, (self.project / ".codex/config.toml").read_bytes())

    def test_equal_unowned_mcp_remains_unowned_after_apply_remove(self):
        config = self.write(".codex/config.toml", self.mcp.read_text())
        self.apply()
        self.apply()
        self.assertEqual(self.state()["mcp"], {})
        self.assertEqual(len(self.state()["reused"]), 1)
        self.remove()
        self.assertEqual(config.read_text(), self.mcp.read_text())
        self.assertTrue(self.state()["retainRoots"])

    def test_owned_mcp_updates_succeed_when_clean(self):
        self.apply()
        self.mcp.write_text(self.mcp.read_text().replace("--safe", "--new"))
        self.apply()
        self.assertIn("--new", (self.project / ".codex/config.toml").read_text())

    def test_equal_global_definitions_avoid_project_duplicates(self):
        path = self.home / ".codex/config.toml"
        path.parent.mkdir()
        path.write_text(self.mcp.read_text())
        self.apply()
        self.assertFalse((self.project / ".codex/config.toml").exists())
        self.assertEqual(self.state()["mcp"], {})

    def test_symlinked_destination_component_fails(self):
        external = self.base / "external"
        external.mkdir()
        (self.project / ".codex").symlink_to(external)
        with self.assertRaisesRegex(a.ActivationError, "symlink"):
            self.apply()
        self.assertEqual(list(external.iterdir()), [])

    def test_unrelated_config_edit_between_plan_and_publication_is_preserved(self):
        config = self.write(".codex/config.toml", '# initial\nmodel = "a"\n')
        runner = self.runner()
        prepared = runner.prepare()
        config.write_text(config.read_text() + '# editor\n')
        with self.assertRaisesRegex(a.SnapshotChanged, "changed before publication"):
            runner.commit(prepared)
        self.assertIn("# editor", config.read_text())
        self.assertNotIn("mcp_servers", config.read_text())
        self.apply()
        self.assertIn("# editor", config.read_text())

    def test_config_creation_race_is_not_overwritten(self):
        runner = self.runner()
        prepared = runner.prepare()
        config = self.write(".codex/config.toml", 'model = "racing-editor"\n')
        with self.assertRaises(a.SnapshotChanged):
            runner.commit(prepared)
        self.assertEqual(config.read_text(), 'model = "racing-editor"\n')

    def test_remove_config_uses_full_file_guard(self):
        self.apply()
        runner = self.runner()
        prepared = runner.prepare(removing=True)
        config = self.project / ".codex/config.toml"
        config.write_text(config.read_text() + '# keep\n')
        with self.assertRaises(a.SnapshotChanged):
            runner.commit(prepared, removing=True)
        self.assertIn("# keep", config.read_text())
        self.assertIn("mcp_servers.fetch", config.read_text())

    def test_config_cas_retry_rereads_new_comments(self):
        config = self.write(".codex/config.toml", '# initial\nmodel = "a"\n')
        runner = self.runner()
        prepared = runner.prepare()
        atomic_json = a.atomic_json
        def edit_after_bookkeeping(path, value):
            atomic_json(path, value)
            config.write_text(config.read_text() + '# editor\n')
        with patch.object(a, "atomic_json", side_effect=edit_after_bookkeeping):
            with self.assertRaisesRegex(a.SnapshotChanged, "immediately before publication"):
                runner.commit(prepared)
        self.assertNotIn("mcp_servers.fetch", config.read_text())
        self.apply()
        self.assertIn("# editor", config.read_text())
        self.assertIn("mcp_servers.fetch", config.read_text())

    def test_interrupted_config_bookkeeping_accepts_generated_value_on_retry(self):
        self.apply()
        self.mcp.write_text(self.mcp.read_text().replace("--safe", "--new"))
        runner = self.runner()
        prepared = runner.prepare()
        replace = a.os.replace
        target = self.project / ".codex/config.toml"
        def interrupt(source, destination):
            result = replace(source, destination)
            if Path(destination) == target:
                raise OSError("interrupted after config replace")
            return result
        with patch.object(a.os, "replace", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "after config replace"):
                runner.commit(prepared)
        self.assertIn("previousValues", self.state()["mcp"]["fetch"])
        self.apply()
        self.assertIn("--new", target.read_text())
        self.assertNotIn("previousValues", self.state()["mcp"]["fetch"])

    def test_interrupted_config_conflicting_edit_preserved_and_reported(self):
        runner = self.runner()
        prepared = runner.prepare()
        replace = a.os.replace
        target = self.project / ".codex/config.toml"
        def interrupt(source, destination):
            result = replace(source, destination)
            if Path(destination) == target:
                raise OSError("interrupted after config replace")
            return result
        with patch.object(a.os, "replace", side_effect=interrupt):
            with self.assertRaises(OSError):
                runner.commit(prepared)
        target.write_text(target.read_text().replace("--safe", "--user"))
        with self.assertRaisesRegex(a.ActivationError, "owned value was edited"):
            self.apply()
        self.assertIn("--user", target.read_text())

    def test_clean_remove_keeps_config_file_without_owned_keys(self):
        self.apply()
        self.remove()
        self.assertEqual(self.state()["mcp"], {})
        self.assertFalse(self.state()["retainRoots"])
        self.assertTrue((self.project / ".codex/config.toml").exists())

    def test_schema_mismatch_is_not_guessed(self):
        self.apply()
        state = self.state()
        state["schemaVersion"] = 99
        (self.project / ".agent-env-nix/mcp-state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(a.ActivationError, "unsupported ownership state"):
            self.remove()
        self.assertIn("mcp_servers.fetch", (self.project / ".codex/config.toml").read_text())

    def test_unsafe_export_name_rejected(self):
        self.manifest["mcpOwners"]["../escape"] = "producer"
        with self.assertRaisesRegex(a.ActivationError, "unsafe export name"):
            self.runner()

    def test_deleted_owned_mcp_is_recreated(self):
        self.apply()
        (self.project / ".codex/config.toml").unlink()
        self.apply()
        self.assertIn("mcp_servers.fetch", (self.project / ".codex/config.toml").read_text())


if __name__ == "__main__":
    unittest.main()
