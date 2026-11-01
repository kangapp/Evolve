"""Native workflow acceptance scopes are explicit before installation or account use."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkflowAcceptanceScopeTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_workflow_acceptance.py'),
            '--package', str(ROOT), *args], capture_output=True, text=True, timeout=15)

    def test_read_only_preflight_freezes_work_and_actual_old_update_journeys(self):
        for journey, cases in [('work', ['guide', 'plan', 'pause', 'finish', 'diagnose', 'repair']),
                               ('update', ['update_inspect', 'update_continue'])]:
            with self.subTest(journey=journey):
                result = self.invoke('--journey', journey, '--preflight-only')
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertFalse(data['model_requests_sent'])
                scope = data['expanded_scope']
                self.assertEqual(list(scope['cases']), cases)
                self.assertEqual(scope['business_write_paths'], ['calc.py'])
                self.assertEqual(scope['readonly_paths'], ['test_calc.py', 'README.md'])
                self.assertEqual(bool(scope['old_fixture_sha256']), journey == 'update')

    def test_unbound_dispatch_stops_before_creating_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'not-created'
            result = self.invoke('--journey', 'update', '--out', str(output),
                '--authorization-text', 'Unrelated prior scope', '--expected-scope-digest', 'wrong')
            self.assertEqual(result.returncode, 2)
            self.assertIn('exact scope digest', result.stderr)
            self.assertFalse(output.exists())
