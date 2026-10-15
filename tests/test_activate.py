"""Local runtime checks. Fake executables test orchestration, not upstream/Nix."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

import tomlkit

SPEC = importlib.util.spec_from_file_location("activate", Path(__file__).parents[1] / "runtime/activate.py")
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.env_patch = patch.dict(os.environ, {"HOME": str(self.home), "CODEX_HOME": str(self.home / ".codex")})
        self.env_patch.start()
        self.bundle = self.base / "bundle"
        self.bundle.mkdir()
        skill = self.bundle / "review"
        skill.mkdir()
        (skill / "SKILL.md").write_text("Read supporting assets.\n")
        (skill / ".hidden").write_text("kept")
        (skill / "run").write_text("#!/bin/sh\nexit 0\n")
        (skill / "run").chmod(0o755)
        self.role = self.base / "reviewer.toml"
        self.role.write_text('name = "reviewer"\ndescription = "Review changes"\ndeveloper_instructions = "Review carefully."\n')
        self.mcp = self.base / "mcp.toml"
        self.mcp.write_text('[mcp_servers.fetch]\ncommand = "/nix/store/fixed-fetch/bin/fetch"\nargs = ["--safe"]\n')
        self.environment = self.base / "store/environment"
        self.environment.mkdir(parents=True)
        self.installer = self.base / "stage-skills"
        self.installer.write_text("#!" + os.sys.executable + "\nimport os, shutil\nfrom pathlib import Path\n"
                                  + f"shutil.copytree({str(self.bundle)!r}, Path(os.environ['AGENT_SKILLS_ROOT'])/'skills')\n"
                                  + "(Path(os.environ['AGENT_SKILLS_ROOT'])/'skills/.agent-skills-managed.json').write_text('{}')\n")
        self.installer.chmod(0o755)
        self.root_calls = self.base / "roots.log"
        self.nix_store = self.base / "nix-store"
        self.nix_store.write_text("#!" + os.sys.executable + "\nimport sys, os\nfrom pathlib import Path\n"
                                  + f"with open({str(self.root_calls)!r},'a') as f: f.write(' '.join(sys.argv[1:])+'\\n')\n"
                                  + "root=Path(sys.argv[sys.argv.index('--add-root')+1])\n"
                                  + "if not os.path.lexists(root): root.symlink_to(sys.argv[2])\n")
        self.nix_store.chmod(0o755)
        self.manifest = {"schemaVersion": 1, "environment": str(self.environment),
                         "nixStore": str(self.nix_store), "skillsInstaller": str(self.installer),
                         "skills": {"review": {"owner": "producer", "source": str(skill)}},
                         "agents": {"reviewer": {"owner": "producer", "source": str(self.role)}},
                         "mcpConfig": str(self.mcp), "mcpOwners": {"fetch": "producer"},
                         "packages": [{"id": "producer", "version": "1", "payload": str(self.bundle), "enableHarnesses": ["codex"]}]}
        self.system_config = self.base / "etc/codex/config.toml"

    def tearDown(self):
        self.env_patch.stop()
        self.temporary.cleanup()

    def runner(self, **kwargs):
        return a.Activator(self.manifest, self.project, system_config=self.system_config, **kwargs)

    def apply(self, **kwargs):
        return self.runner(**kwargs).run()

    def remove(self):
        return self.runner().run(removing=True)

    def state(self):
        return json.loads((self.project / ".agent-env-nix/state.json").read_text())

    def write(self, relative, text):
        target = self.project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def assert_no_published(self):
        self.assertFalse((self.project / ".agents/skills/review").exists())
        self.assertFalse((self.project / ".codex/agents/reviewer.toml").exists())

    def test_apply_copies_full_skill_and_agent_with_fixed_root(self):
        self.apply()
        target = self.project / ".agents/skills/review"
        self.assertEqual((target / ".hidden").read_text(), "kept")
        self.assertTrue((target / "run").stat().st_mode & stat.S_IXUSR)
        self.assertFalse((target.parent / a.MARKER).exists())
        self.assertFalse(any(path.is_symlink() for path in target.rglob("*")))
        self.assertEqual((self.project / ".codex/agents/reviewer.toml").read_bytes(), self.role.read_bytes())
        state = self.state()
        self.assertEqual(state["skills"]["review"]["owner"], "producer")
        root = self.project / ".agent-env-nix/roots" / state["roots"][0]["name"]
        self.assertTrue(root.is_symlink())
        self.assertEqual(os.readlink(root), str(self.environment))
        self.assertIn("--indirect", self.root_calls.read_text())

    def test_repeated_apply_is_idempotent_and_roots_do_not_move(self):
        self.apply()
        state = self.state()
        before = (self.project / ".codex/config.toml").read_bytes()
        self.apply()
        self.assertEqual(state, self.state())
        self.assertEqual(before, (self.project / ".codex/config.toml").read_bytes())
        self.assertEqual(len(list((self.project / ".agent-env-nix/roots").iterdir())), 1)

    def test_generated_owned_skill_edits_are_replaced_and_removed(self):
        self.apply()
        skill = self.project / ".agents/skills/review"
        (skill / "SKILL.md").write_text("local edit")
        (skill / "extra").write_text("remove me")
        self.apply()
        self.assertEqual((skill / "SKILL.md").read_text(), "Read supporting assets.\n")
        self.assertFalse((skill / "extra").exists())
        (skill / "SKILL.md").write_text("another edit")
        self.remove()
        self.assertFalse(skill.exists())
        self.assertTrue((self.project / ".codex/config.toml").exists())

    def test_unrelated_settings_comments_and_siblings_survive(self):
        config = self.write(".codex/config.toml", '# important comment\nmodel = "mine" # inline\n[unknown.future]\nx = 3\n[mcp_servers.other]\nurl = "https://example.com"\n')
        sibling = self.write(".agents/skills/unrelated/SKILL.md", "not owned")
        self.apply()
        self.assertIn('# important comment\nmodel = "mine" # inline', config.read_text())
        self.assertEqual(tomlkit.parse(config.read_text())["unknown"]["future"]["x"], 3)
        self.remove()
        self.assertEqual(sibling.read_text(), "not owned")
        self.assertEqual(tomlkit.parse(config.read_text())["mcp_servers"]["other"]["url"], "https://example.com")

    def test_equal_unowned_resources_remain_unowned_after_apply_remove(self):
        target = self.project / ".agents/skills/review"
        target.parent.mkdir(parents=True)
        shutil.copytree(self.bundle / "review", target)
        agent = self.write(".codex/agents/reviewer.toml", self.role.read_text())
        config = self.write(".codex/config.toml", self.mcp.read_text())
        self.apply()
        self.apply()
        self.assertEqual(self.state()["skills"], {})
        self.assertEqual(self.state()["agents"], {})
        self.assertEqual(self.state()["mcp"], {})
        self.assertEqual(len(self.state()["reused"]), 3)
        self.remove()
        self.assertTrue(target.is_dir())
        self.assertTrue(agent.is_file())
        self.assertEqual(config.read_text(), self.mcp.read_text())
        self.assertTrue(self.state()["roots"])

    def test_unequal_unowned_skill_conflicts_without_other_publication(self):
        self.write(".agents/skills/review/SKILL.md", "different")
        with self.assertRaisesRegex(a.ActivationError, "conflicting unowned tree"):
            self.apply()
        self.assertFalse((self.project / ".codex").exists())
        self.assertFalse(self.root_calls.exists())

    def test_equal_tree_with_different_executable_bit_conflicts(self):
        target = self.project / ".agents/skills/review"
        target.parent.mkdir(parents=True)
        shutil.copytree(self.bundle / "review", target)
        (target / "run").chmod(0o644)
        with self.assertRaisesRegex(a.ActivationError, "conflicting unowned tree"):
            self.apply()

    def test_edited_owned_agent_is_preserved_and_root_retained(self):
        self.apply()
        agent = self.project / ".codex/agents/reviewer.toml"
        agent.write_text(agent.read_text() + "# user edit\n")
        with self.assertRaisesRegex(a.ActivationError, "owned file was edited"):
            self.remove()
        self.assertIn("# user edit", agent.read_text())
        self.assertTrue(self.state()["roots"])
        self.assertTrue((self.project / ".agents/skills/review").is_dir())

    def test_edited_owned_mcp_is_preserved(self):
        self.apply()
        config = self.project / ".codex/config.toml"
        config.write_text(config.read_text().replace("--safe", "--local"))
        with self.assertRaisesRegex(a.ActivationError, "owned value was edited"):
            self.apply()
        self.assertIn("--local", config.read_text())

    def test_owned_agent_and_mcp_updates_succeed_when_clean(self):
        self.apply()
        self.role.write_text(self.role.read_text().replace("Review carefully.", "Review deeply."))
        self.mcp.write_text(self.mcp.read_text().replace("--safe", "--new"))
        self.apply()
        self.assertIn("Review deeply", (self.project / ".codex/agents/reviewer.toml").read_text())
        self.assertIn("--new", (self.project / ".codex/config.toml").read_text())

    def test_global_conflict_fails_without_masking(self):
        path = self.home / ".codex/config.toml"
        path.parent.mkdir()
        path.write_text('[mcp_servers.fetch]\ncommand = "/different"\n')
        with self.assertRaisesRegex(a.ActivationError, "conflicting selected definition"):
            self.apply()
        self.assert_no_published()
        self.assertFalse(self.root_calls.exists())

    def test_equal_global_definitions_avoid_project_duplicates(self):
        path = self.home / ".codex/config.toml"
        path.parent.mkdir()
        path.write_text(self.mcp.read_text())
        agent = path.parent / "agents/arbitrary-filename.toml"
        agent.parent.mkdir()
        agent.write_text(self.role.read_text())
        self.apply()
        self.assertFalse((self.project / ".codex/config.toml").exists())
        self.assertFalse((self.project / ".codex/agents/reviewer.toml").exists())
        self.assertEqual(self.state()["mcp"], {})
        self.assertEqual(self.state()["agents"], {})

    def test_ancestor_and_extra_sources_checked_even_when_local_equal(self):
        self.write(".codex/config.toml", self.mcp.read_text())
        extra = self.base / "extra.toml"
        extra.write_text('[mcp_servers.fetch]\nurl = "https://different.example"\n')
        with self.assertRaisesRegex(a.ActivationError, "extra.toml"):
            self.apply(extra_configs=[extra])
        self.assert_no_published()

    def test_ancestor_conflicting_native_declared_name_detected(self):
        ancestor = self.base / ".codex/agents/other-name.toml"
        ancestor.parent.mkdir(parents=True)
        ancestor.write_text(self.role.read_text().replace("Review carefully.", "Different."))
        with self.assertRaisesRegex(a.ActivationError, "conflicting declared name"):
            self.apply()
        self.assert_no_published()

    def test_referenced_agent_role_is_checked(self):
        source = self.home / ".codex/config.toml"
        source.parent.mkdir()
        source.write_text('[agents.reviewer]\ndescription = "Review changes"\nconfig_file = "role.toml"\n')
        (source.parent / "role.toml").write_text('developer_instructions = "Review carefully."\n')
        self.apply()
        self.assertEqual(self.state()["agents"], {})
        self.assertFalse((self.project / ".codex/agents/reviewer.toml").exists())

    def test_missing_referenced_agent_role_fails_preflight(self):
        self.write(".codex/config.toml", '[agents.reviewer]\nconfig_file = "missing.toml"\n')
        with self.assertRaisesRegex(a.ActivationError, "missing referenced role file"):
            self.apply()
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

    def test_symlinked_destination_component_fails(self):
        external = self.base / "external"
        external.mkdir()
        (self.project / ".agents").symlink_to(external)
        with self.assertRaisesRegex(a.ActivationError, "symlink"):
            self.apply()
        self.assertEqual(list(external.iterdir()), [])

    def test_owned_skill_symlink_fails_without_following_it(self):
        self.apply()
        target = self.project / ".agents/skills/review"
        shutil.rmtree(target)
        target.symlink_to(self.bundle / "review")
        with self.assertRaisesRegex(a.ActivationError, "symlink"):
            self.remove()
        self.assertTrue((self.bundle / "review/SKILL.md").is_file())

    def test_malformed_config_fails_without_publishing(self):
        self.write(".codex/config.toml", "not valid [toml")
        with self.assertRaisesRegex(a.ActivationError, "invalid TOML"):
            self.apply()
        self.assert_no_published()

    def test_root_registration_failure_prevents_publication(self):
        self.nix_store.write_text("#!/bin/sh\nexit 1\n")
        with self.assertRaisesRegex(a.ActivationError, "GC root registration failed"):
            self.apply()
        self.assert_no_published()

    def test_unrelated_config_edit_between_plan_and_publication_is_preserved(self):
        config = self.write(".codex/config.toml", '# initial\nmodel = "a"\n')
        runner = self.runner()
        def edit(operation, target):
            if operation["kind"] == "config":
                config.write_text(config.read_text() + '# editor\n')
        runner.before_publish = edit
        with self.assertRaisesRegex(a.ActivationError, "changed immediately before publication"):
            runner.run()
        self.assertIn("# editor", config.read_text())
        self.assertNotIn("mcp_servers", config.read_text())

    def test_config_creation_race_is_not_overwritten(self):
        runner = self.runner()
        def create(operation, target):
            if operation["kind"] == "config":
                target.parent.mkdir(exist_ok=True)
                target.write_text('model = "racing-editor"\n')
        runner.before_publish = create
        with self.assertRaisesRegex(a.ActivationError, "changed immediately before publication"):
            runner.run()
        self.assertEqual((self.project / ".codex/config.toml").read_text(), 'model = "racing-editor"\n')

    def test_remove_config_uses_full_file_guard(self):
        self.apply()
        runner = self.runner()
        def edit(operation, target):
            if operation["kind"] == "config":
                target.write_text(target.read_text() + '# keep\n')
        runner.before_publish = edit
        with self.assertRaisesRegex(a.ActivationError, "changed immediately before publication"):
            runner.run(removing=True)
        config = self.project / ".codex/config.toml"
        self.assertIn("# keep", config.read_text())
        self.assertIn("mcp_servers.fetch", config.read_text())

    def test_interrupted_file_publication_recovers_old_or_new_only(self):
        runner = self.runner()
        count = 0
        def interrupt(operation, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated interruption")
        runner.before_publish = interrupt
        with self.assertRaisesRegex(OSError, "simulated interruption"):
            runner.run()
        self.assertTrue((self.project / ".agent-env-nix/pending.json").exists())
        self.apply()
        self.assertTrue((self.project / ".codex/agents/reviewer.toml").is_file())
        self.assertFalse((self.project / ".agent-env-nix/pending.json").exists())

    def test_pending_conflicting_edit_preserved_and_reported(self):
        runner = self.runner()
        count = 0
        def interrupt(operation, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("interrupted")
        runner.before_publish = interrupt
        with self.assertRaises(OSError):
            runner.run()
        target = self.project / ".codex/agents/reviewer.toml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# user content after interruption\n")
        with self.assertRaisesRegex(a.ActivationError, "pending agent publication conflicts"):
            self.apply()
        self.assertEqual(target.read_text(), "# user content after interruption\n")

    def test_generation_switch_releases_old_root_only_after_success(self):
        self.apply()
        old_root = self.project / ".agent-env-nix/roots" / self.state()["roots"][0]["name"]
        environment = self.base / "store/new-environment"
        environment.mkdir()
        self.manifest["environment"] = str(environment)
        self.apply()
        self.assertFalse(old_root.exists())
        self.assertEqual(len(self.state()["roots"]), 1)
        self.assertEqual(self.state()["roots"][0]["environment"], str(environment))

    def test_clean_remove_releases_root_and_keeps_config_file(self):
        self.apply()
        self.remove()
        self.assertEqual(self.state()["roots"], [])
        self.assertFalse(any((self.project / ".agent-env-nix/roots").iterdir()))
        self.assertTrue((self.project / ".codex/config.toml").exists())

    def test_schema_mismatch_is_not_guessed(self):
        self.apply()
        state = self.state()
        state["schemaVersion"] = 99
        (self.project / ".agent-env-nix/state.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(a.ActivationError, "unsupported ownership state"):
            self.remove()
        self.assertTrue((self.project / ".agents/skills/review").is_dir())

    def test_unsafe_export_name_rejected(self):
        self.manifest["skills"]["../escape"] = self.manifest["skills"]["review"]
        with self.assertRaisesRegex(a.ActivationError, "unsafe export name"):
            self.runner()

    def test_upstream_runs_only_inside_private_staging(self):
        self.installer.write_text("#!" + os.sys.executable + "\nimport os, shutil\nfrom pathlib import Path\n"
                                  + "root=Path(os.environ['AGENT_SKILLS_ROOT'])\nassert '.agent-env-nix/staging/' in str(root)\n"
                                  + "assert root.name == 'upstream'\nassert list(root.iterdir()) == []\n"
                                  + f"shutil.copytree({str(self.bundle)!r}, root/'skills')\n")
        self.apply()
        self.assertTrue((self.project / ".agents/skills/review/SKILL.md").is_file())


    def test_config_cas_retry_rereads_new_comments(self):
        config = self.write(".codex/config.toml", '# initial\nmodel = "a"\n')
        runner = self.runner()
        def edit(operation, target):
            if operation["kind"] == "config":
                config.write_text(config.read_text() + '# editor\n')
        runner.before_publish = edit
        with self.assertRaises(a.SnapshotChanged):
            runner.run()
        self.assertFalse((self.project / ".agent-env-nix/pending.json").exists())
        self.assert_no_published()
        self.assertTrue(self.state()["roots"])
        self.apply()
        self.assertIn("# editor", config.read_text())
        self.assertIn("mcp_servers.fetch", config.read_text())

    def test_interruption_after_tree_backup_is_recoverable(self):
        self.apply()
        (self.bundle / "review/SKILL.md").write_text("new generated content")
        replace = a.os.replace
        target = self.project / ".agents/skills/review"
        def interrupt(source, destination):
            if Path(source) == target:
                replace(source, destination)
                raise OSError("interrupted after old tree rename")
            return replace(source, destination)
        with patch.object(a.os, "replace", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "after old tree rename"):
                self.apply()
        self.assertFalse(target.exists())
        self.apply()
        self.assertEqual((target / "SKILL.md").read_text(), "new generated content")

    def test_owned_mcp_comment_survives_unchanged_apply(self):
        self.apply()
        config = self.project / ".codex/config.toml"
        config.write_text(config.read_text().replace('args = ["--safe"]', 'args = ["--safe"] # user comment'))
        before = config.read_bytes()
        self.apply()
        self.assertEqual(config.read_bytes(), before)

    def test_skill_only_selection_does_not_audit_unrelated_toml(self):
        self.manifest["agents"] = {}
        self.manifest["mcpOwners"] = {}
        self.mcp.write_text("")
        config = self.write(".codex/config.toml", "unrelated invalid TOML [")
        self.apply()
        self.assertEqual(config.read_text(), "unrelated invalid TOML [")

    def test_selected_native_filename_with_different_role_name_conflicts(self):
        self.write(".codex/agents/reviewer.toml", self.role.read_text().replace('name = "reviewer"', 'name = "someone_else"'))
        with self.assertRaisesRegex(a.ActivationError, "conflicting unowned file"):
            self.apply()
        self.assertFalse((self.project / ".agents").exists())

    def test_deleted_owned_selected_objects_are_recreated(self):
        self.apply()
        shutil.rmtree(self.project / ".agents/skills/review")
        (self.project / ".codex/agents/reviewer.toml").unlink()
        (self.project / ".codex/config.toml").unlink()
        self.apply()
        self.assertTrue((self.project / ".agents/skills/review/SKILL.md").is_file())
        self.assertTrue((self.project / ".codex/agents/reviewer.toml").is_file())
        self.assertIn("mcp_servers.fetch", (self.project / ".codex/config.toml").read_text())



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
                runner.run()
        self.assertEqual(config.read_text(), '# fresh unrelated edit\nmodel = "newer"\n')
        self.assert_no_published()
        self.assertFalse(self.root_calls.exists())



    def test_config_change_before_first_publication_can_retry_fresh(self):
        config = self.write(".codex/config.toml", '# initial\nmodel = "a"\n')
        runner = self.runner()
        register_root = runner.register_root
        def edited_after_preflight():
            root = register_root()
            config.write_text(config.read_text() + '# before publish\n')
            return root
        with patch.object(runner, "register_root", side_effect=edited_after_preflight):
            with self.assertRaisesRegex(a.SnapshotChanged, "changed before publication"):
                runner.run()
        self.assert_no_published()
        self.assertFalse((self.project / ".agent-env-nix/pending.json").exists())
        self.apply()
        self.assertIn("# before publish", config.read_text())
        self.assertIn("mcp_servers.fetch", config.read_text())

    def test_reused_unowned_skill_retains_its_root_after_remove(self):
        target = self.project / ".agents/skills/review"
        target.parent.mkdir(parents=True)
        shutil.copytree(self.bundle / "review", target)
        self.apply()
        root = self.project / ".agent-env-nix/roots" / self.state()["roots"][0]["name"]
        self.remove()
        self.assertTrue(target.is_dir())
        self.assertTrue(root.is_symlink())
        self.assertTrue(self.state()["roots"])

    def test_native_whitespace_only_fields_rejected(self):
        self.role.write_text(self.role.read_text().replace('"Review changes"', '"   "'))
        with self.assertRaisesRegex(a.ActivationError, "invalid native agent definition"):
            self.apply()
        self.assert_no_published()



    def test_nested_native_declared_name_conflicts(self):
        nested = self.home / ".codex/agents/team/reviewer.toml"
        nested.parent.mkdir(parents=True)
        nested.write_text(self.role.read_text().replace("Review carefully.", "Conflicting instructions."))
        with self.assertRaisesRegex(a.ActivationError, "conflicting declared name"):
            self.apply()
        self.assert_no_published()

    def test_declared_alias_uses_native_name_and_metadata_precedence(self):
        config = self.home / ".codex/config.toml"
        config.parent.mkdir(parents=True)
        config.write_text('[agents]\nmax_threads = 6\ndefault_subagent_model = "preserve-me"\n[agents.alias]\ndescription = "Overridden metadata"\nconfig_file = "external-role.toml"\n')
        role = config.parent / "external-role.toml"
        role.write_text(self.role.read_text().replace('name = "reviewer"', 'name = " reviewer "'))
        self.apply()
        self.assertFalse((self.project / ".codex/agents/reviewer.toml").exists())
        self.assertEqual(self.state()["agents"], {})
        role.write_text(role.read_text().replace("Review carefully.", "Conflicting instructions."))
        with self.assertRaisesRegex(a.ActivationError, "conflicting declared name"):
            self.apply()

    def test_declared_legacy_role_uses_hint_and_is_not_discovered_twice(self):
        config = self.home / ".codex/config.toml"
        config.parent.mkdir(parents=True)
        config.write_text('[agents.reviewer]\ndescription = "  Review changes  "\nconfig_file = "agents/legacy-role.toml"\n')
        role = config.parent / "agents/legacy-role.toml"
        role.parent.mkdir()
        role.write_text('name = "  "\ndeveloper_instructions = "Review carefully."\n')
        self.apply()
        self.assertEqual(self.state()["agents"], {})
        self.assertFalse((self.project / ".codex/agents/reviewer.toml").exists())



    def test_equal_unowned_destination_referenced_by_alias_is_reused(self):
        target = self.write(".codex/agents/reviewer.toml", self.role.read_text())
        config = self.write(".codex/config.toml", '[agents.alias]\nconfig_file = "agents/reviewer.toml"\n')
        self.apply()
        self.assertEqual(self.state()["agents"], {})
        self.assertTrue(any(item["kind"] == "agent" and item["source"] == str(target)
                            for item in self.state()["reused"]))
        self.remove()
        self.assertEqual(target.read_text(), self.role.read_text())
        self.assertIn('[agents.alias]', config.read_text())


if __name__ == "__main__":
    unittest.main()
