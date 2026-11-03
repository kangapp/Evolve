"""Actual preserved protocol17 writer and archive cross the explicit upgrade path."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class Protocol18UpgradeTests(unittest.TestCase):
    def test_actual_protocol17_archive_requires_explicit_upgrade_and_old_writer_stops(self):
        with tempfile.TemporaryDirectory(prefix='evolve-protocol18-') as directory:
            lab = Path(directory)
            old, current = lab / 'old', lab / 'current'
            with zipfile.ZipFile(ROOT / 'tests/fixtures/evolve-0.2.0-protocol17.zip') as archive:
                archive.extractall(old)
            built = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_package.py'), '--out', str(current)],
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/recovery_compatibility.py'),
                '--old-package', str(old), '--package', str(current), '--out', str(lab / 'journey')],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            observed = json.loads(result.stdout)
            self.assertTrue(observed['passed'])
            self.assertEqual(observed['actual_old_protocol'], 17)
            self.assertEqual(observed['actual_new_protocol'], 18)
            self.assertTrue(observed['explicit_upgrade'])
