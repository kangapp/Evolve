"""The new multi-work host scope cannot reuse a different native authorization."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/model_multi_acceptance.py'


class MultiScopeTests(unittest.TestCase):
    def invoke(self, *args, runner=RUNNER):
        return subprocess.run([sys.executable, '-B', str(runner), '--package', str(ROOT), *args],
                              capture_output=True, text=True, timeout=15)

    def test_preflight_exposes_seven_fresh_sessions_and_concrete_formal_decisions(self):
        result = self.invoke('--preflight-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['model_requests_sent'])
        scope = data['expanded_scope']
        self.assertEqual(scope['slice'], 'IMP-009')
        self.assertEqual(scope['maximum_sessions'], 7)
        self.assertEqual(len(scope['first_files']), 6)
        self.assertEqual(scope['business_write_paths'], ['total.py', 'report.py'])
        self.assertEqual(scope['formal_write_paths'], ['terms.md'])
        self.assertEqual(len(scope['readonly_paths']), 3)
        self.assertIn('审查约定：核对整数求和时使用独立字面量样例，注明观察范围。',
                      scope['specific_formal_decisions']['final_composed_text'])

    def test_old_or_absent_authorization_is_rejected_before_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'must-not-exist'
            for fields in ([], ['--authorization-text', 'Authorized IMP-008 only', '--expected-scope-digest', 'old-sql-scope']):
                result = self.invoke('--out', str(output), *fields)
                self.assertEqual(result.returncode, 2)
                self.assertIn('exact scope digest', result.stderr)
                self.assertFalse(output.exists())

    def test_frozen_controller_preflight_survives_a_real_directory_alias(self):
        original = self.invoke('--preflight-only')
        self.assertEqual(original.returncode, 0, original.stderr)
        scope = json.loads(original.stdout)['expanded_scope']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / 'controller'
            for name in scope['runner_files']:
                destination = controller / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, destination)
            alias = root / 'alias'
            alias.symlink_to(controller, target_is_directory=True)
            result = self.invoke('--preflight-only', runner=alias / 'scripts/model_multi_acceptance.py')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['expanded_scope']['scope_digest'], scope['scope_digest'])
