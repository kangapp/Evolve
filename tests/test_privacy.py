"""Known credentials are rejected before persistence; check output is redacted."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.checks import run_check
from evolve_core.errors import EvolveError
from evolve_core.requests import normalize
from evolve_core.workspace import durable_write, prepare_files


class CredentialBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.secret = 'synthetic-fixture-secret-never-real'
        self.environment = patch.dict(os.environ, {'EVOLVE_FIXTURE_API_KEY': self.secret})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-privacy-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_request_rejects_credentials_without_echoing_them(self):
        with self.assertRaises(EvolveError) as caught:
            normalize({'input': {'nested': [self.secret]}})
        self.assertEqual(caught.exception.code, 'CREDENTIAL_CONTENT')
        self.assertNotIn(self.secret, str(caught.exception))

    def test_file_journal_does_not_base64_encode_a_known_credential(self):
        with self.assertRaises(EvolveError):
            prepare_files(self.root, 'fixture-op', [{'path': 'source.txt', 'expected_digest': None, 'content': self.secret}])
        self.assertFalse((self.root / '.evolve-local').exists())

    def test_durable_write_rejects_credentials_before_creating_directories(self):
        with self.assertRaises(EvolveError):
            durable_write(self.root / 'nested/output.txt', self.secret.encode())
        self.assertFalse((self.root / 'nested').exists())

    def test_check_output_uses_environment_without_recording_credential_plaintext(self):
        check = {'id': 'secret-output', 'argv': [sys.executable, '-c',
                 'import os; print(os.environ["EVOLVE_FIXTURE_API_KEY"])'], 'timeout': 5}
        result = run_check(self.root, check)
        self.assertEqual(result['status'], 'passed')
        self.assertIn('[REDACTED]', result['output'])
        self.assertNotIn(self.secret, str(result))
