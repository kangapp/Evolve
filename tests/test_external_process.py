"""Actual committed target effects can coexist with lost receipts or sender failure."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.external import build_candidate
from evolve_core.external_material import freeze_material, validate_frozen
from evolve_core.external_process import finish_process, receipt


class ExternalProcessTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)

    def launch(self, entry=None):
        if entry is not None:
            (self.f.root / 'writer.py').write_text(entry)
        candidate = build_candidate(self.f.root, self.f.data)
        folder = self.f.root / '.evolve-local/control/frozen'
        freeze_material(folder, candidate)
        validate_frozen(folder, candidate)
        output = tempfile.TemporaryFile()
        self.addCleanup(output.close)
        process = subprocess.Popen([candidate['execution']['interpreter']['path'], '-B', str(folder / 'writer.py'),
            str(self.f.database), 'actual-controlled-operation'], cwd=folder, stdout=output,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        def cleanup():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        self.addCleanup(cleanup)
        return process, output

    def test_real_successful_receipt_only_allows_followup_probe_not_business_acceptance(self):
        process, output = self.launch()
        observation = finish_process(process, output, 5)
        parsed = receipt(observation, 'actual-controlled-operation', 'temporary-external-target')
        self.assertEqual(parsed['provider_operation_ref'], 'actual-controlled-operation')
        self.assertFalse(observation['command_exit_is_business_success'])
        self.assertEqual(self.f.rows('SELECT value FROM ledger WHERE id=1'), [(20,)])
        self.assertEqual(self.f.rows('SELECT outcome,finished FROM operation_receipts'), [('succeeded', 1)])
        self.assertIsNone(receipt(observation, 'other-operation', 'temporary-external-target'))
        self.assertIsNone(receipt(observation, 'actual-controlled-operation', 'other-target'))

    def test_zero_exit_with_lost_receipt_is_unknown_even_after_actual_commit(self):
        process, output = self.launch('import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("lost actual transport receipt")\n')
        observation = finish_process(process, output, 5)
        self.assertEqual(observation['returncode'], 0)
        self.assertIsNone(receipt(observation, 'actual-controlled-operation', 'temporary-external-target'))
        self.assertEqual(self.f.rows('SELECT value FROM ledger WHERE id=1'), [(20,)])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_timeout_after_actual_commit_does_not_undo_or_claim_no_effect(self):
        process, output = self.launch('import sys,time\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("committed before deliberate delay",flush=True)\ntime.sleep(60)\n')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and self.f.rows('SELECT value FROM ledger WHERE id=1') != [(20,)]:
            time.sleep(0.01)
        self.assertEqual(self.f.rows('SELECT value FROM ledger WHERE id=1'), [(20,)])
        observation = finish_process(process, output, 0.05)
        self.assertTrue(observation['timed_out'])
        self.assertIsNone(receipt(observation, 'actual-controlled-operation', 'temporary-external-target'))
        self.assertEqual(self.f.rows('SELECT outcome,finished FROM operation_receipts'), [('succeeded', 1)])
        self.assertEqual(self.f.rows('SELECT value FROM ledger WHERE id=1'), [(20,)])

    def test_large_output_is_explicitly_bounded_and_secrets_do_not_enter_the_observation(self):
        # Use a synthetic, process-local credential reference. The actual source
        # never embeds a credential value; the existing privacy rule knows this env.
        entry = 'import os\nprint("x"*70000)\nprint(os.environ["EVOLVE_TEST_SECRET"])\n'
        with patch.dict(os.environ, {'EVOLVE_TEST_SECRET': 'temporary-private-value'}):
            process, output = self.launch(entry)
            observation = finish_process(process, output, 5)
        self.assertTrue(observation['output_truncated'])
        self.assertLessEqual(len(observation['output']), 65536)
        self.assertFalse('temporary-private-value' in observation['output'], 'Synthetic environment credential reached observation')
        self.assertIsNone(receipt(observation, 'actual-controlled-operation', 'temporary-external-target'))
        self.assertEqual(self.f.rows('SELECT value FROM ledger WHERE id=1'), [(10,)])
