"""Focused output projection/ownership tests; no DSH, gateway or Nix installation."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import tomlkit

PATH = Path(__file__).parents[1] / 'runtime/config.py'
spec = importlib.util.spec_from_file_location('dsh_config', PATH)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class DshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS /var is a symlink to /private/var; the helper resolves physical paths.
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project with spaces'
        self.project.mkdir()
        self.state = self.project / '.agent-env-nix'
        self.state.mkdir(mode=0o700)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.environment = patch.dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / '.codex'),
                                      TEST_DSH_PORT='18080', TEST_DSH_TOKEN='never-materialize-me')
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.source = self.root / 'generated.toml'
        self.manifest_path = self.root / 'manifest.json'
        self.manifest = dict(schemaVersion=1, mcpConfig=str(self.source), dshMcp=True,
                             mcpOwners={'kb': 'knowledge', 'fetch': 'base'}, mcpPortEnv={'kb': 'TEST_DSH_PORT'})
        self.servers = {
            'kb': dict(url='http://127.0.0.1:9090/mcp', bearer_token_env_var='TEST_DSH_TOKEN'),
            'fetch': dict(command='/nix/store/fixed-fetch/bin/fetch', args=['--safe'], env_vars=['TEST_DSH_TOKEN']),
        }
        self.write_source()
        self.target = self.project / '.dsh/mcp.json'
        self.prepared = self.state / 'prepared.json'

    def write_source(self):
        self.source.write_text(tomlkit.dumps({'mcp_servers': self.servers}))
        self.manifest_path.write_text(json.dumps(self.manifest))

    def editor(self):
        return a.DshConfigEditor(self.manifest, self.project)

    def apply(self):
        editor = self.editor()
        return editor.commit(editor.prepare())

    def cli(self, phase, success=True, action='apply'):
        args = [sys.executable, str(PATH), phase, '--manifest', str(self.manifest_path)]
        if phase != 'cache-key':
            args += ['--project', str(self.project), '--state', str(self.state / 'mcp-state.json'),
                     '--prepared', str(self.prepared), '--action', action]
        result = subprocess.run(args, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def json(self):
        return json.loads(self.target.read_text())

    def test_harness_selection_and_owned_cleanup(self):
        self.manifest['mcpHarnesses'] = {'kb': ['dsh'], 'fetch': ['codex']}
        self.write_source()
        self.cli('prepare'); self.cli('commit')
        self.assertEqual(set(self.json()['mcpServers']), {'kb'})
        codex = self.project / '.codex/config.toml'
        self.assertEqual(set(tomlkit.parse(codex.read_text())['mcp_servers']), {'fetch'})
        before = self.cli('cache-key').stdout
        document = self.json()
        document['mcpServers']['unrelated'] = {'type': 'http', 'url': 'https://other.invalid/mcp'}
        self.target.write_text(json.dumps(document))
        self.manifest['mcpHarnesses'] = {'kb': ['codex'], 'fetch': ['dsh']}
        self.write_source()
        self.assertNotEqual(before, self.cli('cache-key').stdout)
        self.cli('prepare'); self.cli('commit')
        self.assertEqual(set(self.json()['mcpServers']), {'fetch', 'unrelated'})
        self.assertEqual(set(tomlkit.parse(codex.read_text())['mcp_servers']), {'kb'})
        self.manifest['mcpHarnesses'] = {'kb': [], 'fetch': []}
        self.write_source()
        self.cli('prepare'); self.cli('commit')
        self.assertEqual(set(self.json()['mcpServers']), {'unrelated'})
        self.assertEqual(dict(tomlkit.parse(codex.read_text()).get('mcp_servers', {})), {})

    def test_normal_shared_projection_and_default_opt_out(self):
        self.cli('prepare'); self.cli('commit')
        values = self.json()['mcpServers']
        self.assertEqual(values['kb'], {'type': 'http', 'url': 'http://127.0.0.1:18080/mcp',
                                      'headers': {'Authorization': 'Bearer ${TEST_DSH_TOKEN}'}})
        self.assertEqual(values['fetch']['cwd'], str(self.project))
        self.assertEqual(values['fetch']['command'], self.servers['fetch']['command'])
        self.assertEqual(values['fetch']['args'], ['--safe'])
        self.assertEqual(values['fetch']['env'], {'TEST_DSH_TOKEN': '${TEST_DSH_TOKEN}'})
        codex = tomlkit.parse((self.project / '.codex/config.toml').read_text())
        self.assertEqual(codex['mcp_servers']['kb']['url'], values['kb']['url'])
        for path in (self.target, self.prepared, self.state / 'dsh-mcp-state.json'):
            self.assertNotIn('never-materialize-me', path.read_text())
        self.manifest['dshMcp'] = False
        self.write_source(); self.cli('prepare'); self.cli('commit')
        self.assertEqual(self.json()['mcpServers'], {})
        other = self.root / 'default-project'; other.mkdir()
        self.assertEqual(len(a.output_editors(self.manifest, other)), 1)
        self.assertFalse((other / '.dsh').exists())

    def test_mapping_and_unrepresentable_values(self):
        source = {'a.b': {'command': '/nix/store/fixed/bin/tool', 'cwd': 'sub', 'tool_timeout_sec': 2.5,
                          'required': True, 'startup_timeout_sec': 20},
                  'off': {'enabled': False},
                  'http': {'url': 'https://example.invalid/mcp', 'http_headers': {'X-Static': 'plain'},
                           'env_http_headers': {'X-Key': 'TEST_DSH_TOKEN'}}}
        value = a.dsh_mcp(source, self.project)
        self.assertEqual(value['a.b']['toolCallTimeoutMs'], 2500)
        self.assertEqual(value['a.b']['cwd'], str(self.project / 'sub'))
        self.assertNotIn('required', value['a.b'])
        self.assertNotIn('startup_timeout_sec', value['a.b'])
        self.assertEqual(value['off'], {'disabled': True})
        self.assertEqual(value['http']['headers']['X-Key'], '${TEST_DSH_TOKEN}')
        for field, value in [('enabled_tools', ['read']), ('enabled_tools', []), ('args', ['${SECRET_VALUE}'])]:
            self.servers['fetch'][field] = value
            self.write_source()
            result = self.cli('prepare', success=False)
            self.assertFalse(self.target.exists())
            self.assertFalse((self.project / '.codex/config.toml').exists())
            self.assertNotIn('SECRET_VALUE', result.stderr)
            del self.servers['fetch'][field]

    def test_unmanaged_preserved_reused_and_conflict(self):
        self.target.parent.mkdir()
        wanted = a.dsh_mcp(a.desired_mcp(self.manifest), self.project)
        original = {'note': 'keep', 'mcpServers': {'other': {'url': 'https://other.invalid'}, 'kb': wanted['kb']}}
        self.target.write_text(json.dumps(original))
        state = self.apply()
        self.assertEqual(self.json()['note'], 'keep')
        self.assertEqual(self.json()['mcpServers']['other'], original['mcpServers']['other'])
        self.assertNotIn('kb', state['mcp'])
        self.assertTrue(state['retainRoots'])
        doc = self.json(); doc['mcpServers']['kb']['url'] = 'https://changed.invalid'
        self.target.write_text(json.dumps(doc)); before = self.target.read_bytes()
        with self.assertRaises(a.ActivationError): self.apply()
        self.assertEqual(self.target.read_bytes(), before)

    def test_owned_edit_and_fallback_protected(self):
        fallback = self.project / '.mcp.json'; fallback.write_text('{"mcpServers":{"unrelated":{}}}')
        before = fallback.read_bytes()
        self.cli('prepare', success=False)
        self.assertEqual(fallback.read_bytes(), before)
        self.assertFalse(self.target.exists())
        self.assertFalse((self.project / '.codex/config.toml').exists())
        fallback.unlink()
        self.apply()
        doc = self.json(); doc['mcpServers']['fetch']['args'] = ['manual']
        self.target.write_text(json.dumps(doc)); before = self.target.read_bytes()
        with self.assertRaises(a.ActivationError): self.apply()
        self.assertEqual(self.target.read_bytes(), before)

    def test_retry_update_removal_and_cache(self):
        old_key = self.cli('cache-key').stdout
        self.cli('prepare')
        plans = json.loads(self.prepared.read_text())
        # Interrupt after Codex publication; a new prepare must reconcile it.
        codex = a.ConfigEditor(self.manifest, self.project)
        codex.commit(plans['codex'])
        self.assertFalse(self.target.exists())
        self.cli('prepare'); self.cli('commit')
        os.environ['TEST_DSH_PORT'] = '18081'
        self.assertNotEqual(self.cli('cache-key').stdout, old_key)
        self.cli('prepare'); self.cli('commit')
        self.assertEqual(self.json()['mcpServers']['kb']['url'], 'http://127.0.0.1:18081/mcp')
        doc = self.json(); doc['mcpServers']['other'] = {'url': 'https://other.invalid'}
        self.target.write_text(json.dumps(doc))
        self.cli('prepare', action='remove'); self.cli('commit', action='remove')
        self.assertEqual(self.json()['mcpServers'], {'other': {'url': 'https://other.invalid'}})
        self.manifest['dshMcp'] = False; self.write_source()
        self.assertNotEqual(self.cli('cache-key').stdout, old_key)


if __name__ == '__main__':
    unittest.main()

