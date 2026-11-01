"""Actual public CLI exercises the six parent boundaries before native dispatch."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExternalAcceptanceScopeTests(unittest.TestCase):
    def test_six_session_scope_and_missing_approval_cannot_dispatch(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/model_external_acceptance.py'), '--package', str(ROOT)]
        result = subprocess.run([*command, '--preflight-only'], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        scope = json.loads(result.stdout)['expanded_scope']
        self.assertEqual((scope['slice'], scope['maximum_sessions'], scope['protocol_version']), ('IMP-013', 6, 16))
        self.assertEqual(scope['business_write_paths'], [])
        self.assertEqual(len(scope['readonly_paths']), 6)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'must-not-exist'
            refused = subprocess.run([*command, '--out', str(output)], capture_output=True, text=True, timeout=20)
            self.assertNotEqual(refused.returncode, 0)
            self.assertFalse(output.exists())

    def test_real_six_parent_boundaries_and_readonly_tamper_rejection_without_models(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Path(directory)
            package = lab / 'package'
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_package.py'), '--out', str(package)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'tests/external_acceptance_driver.py'), str(package), str(ROOT), str(lab)], capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout[-4000:])
            observed = json.loads(result.stdout)
            self.assertEqual(len(observed['observations']), 6)
            self.assertTrue(observed['tampering_rejected'])
            self.assertFalse(observed['model_requests_sent'])
