"""New native scope cannot dispatch on old or absent authorization."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DataScopeTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_data_acceptance.py'),
            '--package', str(ROOT), *args], capture_output=True, text=True, timeout=15)

    def test_preflight_exposes_exact_five_session_three_file_scope_without_dispatch(self):
        result = self.invoke('--preflight-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['model_requests_sent'])
        scope = data['expanded_scope']
        self.assertEqual(scope['maximum_sessions'], 5)
        self.assertEqual(scope['business_write_paths'], ['model.sql'])
        self.assertEqual(scope['readonly_paths'], ['orders.json', 'test_reconciliation.py'])
        self.assertEqual(len(scope['first_files']), 3)
        self.assertEqual(scope['protocol_version'], 17)

    def test_absent_or_wrong_scope_refuses_before_creating_project(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'must-not-exist'
            for fields in ([], ['--authorization-text', 'Authorized older scope', '--expected-scope-digest', 'old'],
                           ['--authorization-text', ' ', '--expected-scope-digest', 'old']):
                result = self.invoke('--out', str(out), *fields)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('exact scope digest', result.stderr)
                self.assertFalse(out.exists())

    def test_preflight_and_installation_preparation_are_mutually_exclusive(self):
        result = self.invoke('--preflight-only', '--prepare-only')
        self.assertEqual(result.returncode, 2)
