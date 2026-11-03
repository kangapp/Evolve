"""Freeze engineering inputs and refuse unbound native dispatch before setup."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EngineeringScopeTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_engineering_acceptance.py'),
            '--package', str(ROOT), *args], capture_output=True, text=True, timeout=15)

    def test_preflight_freezes_real_fixture_and_four_distinct_sessions(self):
        completed = self.invoke('--preflight-only')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = json.loads(completed.stdout)
        self.assertFalse(data['model_requests_sent'])
        scope = data['expanded_scope']
        self.assertEqual(scope['maximum_sessions'], 4)
        self.assertTrue(scope['fresh_conversation_per_case'])
        self.assertEqual(list(scope['cases']), ['implement', 'independent_core', 'knowledge', 'finish'])
        self.assertEqual(scope['business_write_paths'], ['src/total.ts', 'src/math/total.ts'])
        self.assertEqual(scope['knowledge_write_paths'], ['evolve/codemap.md'])
        self.assertIn('package-lock.json', scope['fixture_files'])
        self.assertIn('tests/total.test.ts', scope['readonly_paths'])
        self.assertIn('--offline', scope['fixture_install'])

    def test_unbound_or_wrong_scope_cannot_install_or_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'must-not-exist'
            for arguments in ([], ['--authorization-text', 'An unrelated scope', '--expected-scope-digest', 'wrong']):
                completed = self.invoke('--out', str(output), *arguments)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn('exact scope digest', completed.stderr)
                self.assertFalse(output.exists())

    def test_fixture_lock_has_no_temporary_project_references(self):
        folder = ROOT / 'tests/fixtures/engineering-next'
        package = json.loads((folder / 'package.json').read_text())
        lock = json.loads((folder / 'package-lock.json').read_text())
        self.assertEqual(lock['version'], package['version'])
        self.assertTrue(all(not name or name.startswith('node_modules/') for name in lock['packages']))
        for key in ('dependencies', 'devDependencies'):
            for name, version in package[key].items():
                self.assertEqual(lock['packages']['node_modules/' + name]['version'], version)
