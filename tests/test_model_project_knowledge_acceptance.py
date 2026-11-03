"""Freeze the real Codex scope and refuse unbound account dispatch before installation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProjectKnowledgeScopeTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_project_knowledge_acceptance.py'),
            '--package', str(ROOT), *args], capture_output=True, text=True, timeout=15)

    def test_preflight_freezes_six_sessions_and_required_knowledge_without_dispatch(self):
        result = self.invoke('--preflight-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['model_requests_sent'])
        scope = data['expanded_scope']
        self.assertEqual(scope['maximum_sessions'], 6)
        self.assertEqual(scope['protocol_version'], 18)
        self.assertEqual(scope['business_write_paths'], ['calc.py'])
        self.assertEqual(scope['readonly_paths'], ['README.md', 'legacy.md', 'test_calc.py', 'test_summary.py'])
        self.assertEqual(list(scope['cases']), ['survey', 'initial_delivery', 'implement', 'finish', 'facts', 'conflict'])
        self.assertIn('required', scope['cases']['implement'])
        self.assertIn('FILE_CONFLICT', scope['cases']['conflict'])

    def test_wrong_or_absent_scope_stops_before_profile_or_account_use(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'not-created'
            for fields in ([], ['--authorization-text', 'An earlier unrelated fixture', '--expected-scope-digest', 'old']):
                result = self.invoke('--out', str(output), *fields)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('exact scope digest', result.stderr)
                self.assertFalse(output.exists())

    def test_preflight_and_installation_preparation_remain_distinct(self):
        result = self.invoke('--preflight-only', '--prepare-only')
        self.assertEqual(result.returncode, 2)
