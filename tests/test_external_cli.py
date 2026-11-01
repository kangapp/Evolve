"""Actual public subprocess CLI over the controlled real SQLite mechanism."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.external import execute, prepare
from evolve_core.package import canonical, digest


class ExternalCliTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture(with_work=True)
        self.addCleanup(self.f.close)

    def cli(self, action, method, request):
        child = subprocess.run([sys.executable, '-B', str(ROOT / 'runtime/evolve.py'), '--project', str(self.f.root),
            action, '--method', method, '--request', '-'], input=json.dumps(request), text=True, capture_output=True)
        self.assertTrue(child.stdout.strip(), child.stderr)
        value = json.loads(child.stdout)
        return child.returncode, value

    def approved(self, prepared, **extra):
        return self.f.work_request({'stage': 'apply', 'candidate_ref': {
            'run_id': prepared['run_id'], 'result_digest': prepared['result_digest']}, 'approval': {
                'candidate_digest': prepared['candidate_digest'], 'target_digest': prepared['candidate']['target_snapshot']['digest'],
                'source': 'actual-uniform-human-authorization-specific-public-fixture',
                'text': 'This exact temporary business plan/candidate and independent task checks only.'}, **extra})

    def test_missing_check_protection_blocks_dispatch_without_advancing_work(self):
        _, reply = self.cli('apply', 'external.execute', self.f.work_request())
        request = self.approved(reply['data'])
        (self.f.root / '.evolve-local/control/checks.json').unlink()
        before = (self.f.root / 'evolve/history.db').read_bytes()
        code, failed = self.cli('apply', 'external.execute', request)
        self.assertNotEqual(code, 0)
        self.assertEqual(failed['error']['code'], 'PROTECTION_UNKNOWN')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])
        self.assertEqual((self.f.root / 'evolve/history.db').read_bytes(), before)

    def test_missing_check_protection_blocks_check_continuation_before_run_and_claims(self):
        _, reply = self.cli('apply', 'external.execute', self.f.work_request())
        code, applied = self.cli('apply', 'external.execute', self.approved(reply['data']))
        self.assertEqual(code, 0, applied)
        (self.f.root / '.evolve-local/control/checks.json').unlink()
        before = (self.f.root / 'evolve/history.db').read_bytes()
        code, failed = self.cli('apply', 'external.execute', self.f.work_request({
            'stage': 'checks', 'operation_id': applied['data']['operation_id']}))
        self.assertNotEqual(code, 0)
        self.assertEqual(failed['error']['code'], 'PROTECTION_UNKNOWN')
        self.assertEqual((self.f.root / 'evolve/history.db').read_bytes(), before)
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])

    def test_failed_actual_task_check_keeps_external_stage_blocked_and_guides_checks_only(self):
        check = self.f.root / 'test_target.py'
        check.write_text(check.read_text().replace('[(1,20)]', '[(1,999)]'))
        observations = {'test_target.py': digest(check.read_bytes())}
        code, prepared = self.cli('apply', 'external.execute', self.f.work_request({**self.f.data, 'observations': observations}))
        self.assertEqual(code, 0, prepared)
        code, reply = self.cli('apply', 'external.execute', self.approved(prepared['data'], observations=observations))
        self.assertEqual(code, 0, reply)
        self.assertEqual(reply['data']['effect_outcome'], 'succeeded')
        self.assertFalse(reply['data']['task_completed'])
        self.assertEqual(reply['data']['task_checks'][0]['status'], 'failed')
        self.assertEqual(reply['workflow']['phase_status'], 'blocked')
        self.assertFalse(reply['workflow']['stage_complete'])
        self.assertTrue(reply['workflow']['remaining'])
        following = reply['workflow']['next_steps'][0]
        self.assertEqual(following['stage'], 'checks')
        self.assertEqual(following['operation_id'], reply['data']['operation_id'])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_public_prepare_exact_receipt_apply_retry_and_independent_checks(self):
        code, reply = self.cli('apply', 'external.execute', self.f.work_request())
        self.assertEqual(code, 0, reply)
        prepared = reply['data']
        self.assertTrue(prepared['result_digest'])
        self.assertFalse(prepared['dispatch_performed'])
        self.assertEqual(reply['workflow']['phase_status'], 'waiting_confirmation')
        self.assertEqual(reply['workflow']['next_steps'][0]['method'], 'external.execute')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])
        request = self.f.work_request({'stage': 'apply', 'candidate_ref': {
            'run_id': prepared['run_id'], 'result_digest': prepared['result_digest']}, 'approval': {
                'candidate_digest': prepared['candidate_digest'], 'target_digest': prepared['candidate']['target_snapshot']['digest'],
                'source': 'actual-uniform-human-authorization-specific-public-fixture',
                'text': 'This exact temporary business plan/candidate and independent task checks only.'}})
        code, first = self.cli('apply', 'external.execute', request)
        self.assertEqual(code, 0, first)
        self.assertTrue(first['data']['task_completed'])
        self.assertEqual(first['data']['effect_outcome'], 'succeeded')
        self.assertEqual(self.cli('apply', 'external.execute', request), (code, first))
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM verifications').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT state FROM tasks").fetchone()[0], 'done')

    def test_public_write_without_current_task_is_rejected_before_dispatch(self):
        code, reply = self.cli('apply', 'external.execute', self.f.request())
        self.assertNotEqual(code, 0)
        self.assertEqual(reply['error']['code'], 'TARGET')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])

    def test_operation_observation_and_cancellation_do_not_require_a_current_work_item(self):
        # Private fixture component produces an operation with no Change, so CLI
        # observation cannot accidentally rely on the fixture's other work item.
        (self.f.root / 'writer.py').write_text('import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("lost")\n')
        candidate = prepare(self.f.root, self.f.request())
        original = execute(self.f.root, self.f.request({'stage': 'apply', 'candidate_ref': {
            'run_id': candidate['run_id'], 'result_digest': digest(canonical(candidate))}, 'approval': {
                'candidate_digest': candidate['candidate_digest'], 'target_digest': candidate['candidate']['target_snapshot']['digest'],
                'source': 'actual-uniform-authorization-specific-private-fixture', 'text': 'This exact controlled candidate.'}}))
        code, cancelled = self.cli('maintain', 'cancel', self.f.request({'external_operation_id': original['operation_id'], 'reason': 'Stop future dispatch only.'}))
        self.assertEqual(code, 0, cancelled)
        self.assertFalse(cancelled['data']['claims_released'])
        code, observed = self.cli('apply', 'external.reconcile', self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(code, 0, observed)
        self.assertEqual(observed['data']['effect_outcome'], 'succeeded')
        self.assertFalse(observed['data']['command_replayed'])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
