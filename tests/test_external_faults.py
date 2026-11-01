"""Actual abrupt exits at dispatch registration/admission/sender boundaries."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.errors import EvolveError
from evolve_core.external import prepare, reconcile
from evolve_core.maintenance import backup, restore
from evolve_core.package import canonical, digest
from evolve_core.store import now


class ExternalFaultTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)

    def crash(self, point):
        candidate = prepare(self.f.root, self.f.request())
        request = self.f.request({'stage': 'apply', 'candidate_ref': {'run_id': candidate['run_id'],
            'result_digest': digest(canonical(candidate))}, 'approval': {'candidate_digest': candidate['candidate_digest'],
            'target_digest': candidate['candidate']['target_snapshot']['digest'],
            'source': 'actual-uniform-human-authorization-fixed-fault-fixture', 'text': 'Only this exact controlled temporary candidate.'}})
        script = ('import json,os,sys\nfrom evolve_core import external\n'
                  'def fault(name):\n    if name==sys.argv[3]: os._exit(74)\n'
                  'external.fault_point=fault\nexternal.execute(sys.argv[1],json.loads(sys.argv[2]))\n')
        environment = {**os.environ, 'PYTHONPATH': str(ROOT / 'runtime')}
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.f.root), json.dumps(request), point],
            capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 74, result.stderr)
        db = sqlite3.connect(self.f.root / 'evolve/history.db')
        try:
            return db.execute("SELECT id FROM operations WHERE effect_kind='external_write'").fetchone()[0]
        finally:
            db.close()

    def test_registration_crash_before_index_still_survives_older_restore(self):
        saved = backup(self.f.root, self.f.request({}))
        operation_id = self.crash('registered')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])
        plan = restore(self.f.root, self.f.request({'stage': 'plan', 'bundle': saved['path'], 'manifest_digest': saved['manifest_digest']}))
        self.assertEqual([r['operation_id'] for r in plan['plan']['external']['pending']], [operation_id])
        restored = restore(self.f.root, self.f.request({'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']}))
        self.f.identity['expected_workspace_epoch'] = restored['workspace_epoch']
        self.assertEqual(restored['external_pending'], 1)
        self.assertFalse(self.f.rows('SELECT operation_id FROM operation_receipts'))

    def test_admitted_but_no_pid_crash_needs_exact_stopping_evidence_and_never_resends(self):
        operation_id = self.crash('before_launch')
        index = json.loads((self.f.root / '.evolve-local/control/external.json').read_text())
        sender = index['pending'][0]['sender']
        self.assertNotIn('pid', sender)
        with self.assertRaises(EvolveError) as error:
            reconcile(self.f.root, self.f.request({'operation_id': operation_id}))
        self.assertEqual(error.exception.code, 'CHECK_EXECUTION_UNKNOWN')
        observation = {**sender, 'source': 'actual-parent-controller-known-prelaunch-exit',
            'basis': 'Child exited at the exact before_launch seam before Popen; parent observed exit 74 and no provider receipt.',
            'outcome': 'not_started', 'observed_at': now()}
        result = reconcile(self.f.root, self.f.request({'operation_id': operation_id, 'sender_observations': [observation]}))
        self.assertFalse(result['command_replayed'])
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])
        self.assertFalse(self.f.rows('SELECT operation_id FROM operation_receipts'))

    def test_started_sender_survives_owner_exit_and_blocks_reconcile_and_restore(self):
        saved = backup(self.f.root, self.f.request({}))
        (self.f.root / 'writer.py').write_text('import sys,time\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\ntime.sleep(60)\n')
        operation_id = self.crash('sender_recorded')
        index = json.loads((self.f.root / '.evolve-local/control/external.json').read_text())
        pid = index['pending'][0]['sender']['pid']
        try:
            for _ in range(100):
                if self.f.rows('SELECT COUNT(*) FROM operation_receipts') == [(1,)]:
                    break
                time.sleep(.02)
            self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
            for function, request in ((reconcile, {'operation_id': operation_id}),
                    (restore, {'stage': 'plan', 'bundle': saved['path'], 'manifest_digest': saved['manifest_digest']})):
                with self.assertRaises(EvolveError) as error:
                    function(self.f.root, self.f.request(request))
                self.assertEqual(error.exception.code, 'CHECK_RUNNING')
        finally:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_commit_then_owner_exit_before_local_receipt_is_reconciled_without_duplicate_dispatch(self):
        operation_id = self.crash('sender_finished_before_receipt')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        index = json.loads((self.f.root / '.evolve-local/control/external.json').read_text())
        self.assertEqual(index['pending'][0]['operation_id'], operation_id)
        self.assertEqual(index['pending'][0]['state'], 'unknown')
        result = reconcile(self.f.root, self.f.request({'operation_id': operation_id}))
        self.assertEqual(result['effect_outcome'], 'succeeded')
        self.assertFalse(result['command_replayed'])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_process_started_before_pid_receipt_retains_unknown_until_actual_sender_stopping_observation(self):
        from evolve_core.workspace import process_alive
        helper = self.f.root / 'helper.py'
        helper.write_text(helper.read_text().replace('import json,sqlite3', 'import json,sqlite3,os').replace("known={'ledger_id':1", "known={'actual_sender_pid':os.getpid(),'ledger_id':1"))
        operation_id = self.crash('launched_before_pid_receipt')
        for _ in range(100):
            if self.f.rows('SELECT COUNT(*) FROM operation_receipts') == [(1,)]:
                break
            time.sleep(.02)
        known = json.loads(self.f.rows('SELECT known_effects_json FROM operation_receipts')[0][0])
        pid = known['actual_sender_pid']
        for _ in range(100):
            if not process_alive(pid):
                break
            time.sleep(.02)
        self.assertFalse(process_alive(pid))
        index = json.loads((self.f.root / '.evolve-local/control/external.json').read_text())
        sender = index['pending'][0]['sender']
        self.assertNotIn('pid', sender)
        with self.assertRaises(EvolveError) as error:
            reconcile(self.f.root, self.f.request({'operation_id': operation_id}))
        self.assertEqual(error.exception.code, 'CHECK_EXECUTION_UNKNOWN')
        observation = {**sender, 'outcome': 'stopped', 'source': 'actual-controller-finite-mechanism-provider-PID-and-process-observation',
            'basis': 'This inspected synchronous helper wrote its actual os.getpid into its real provider receipt; parent observed that exact PID no longer exists and the declared mechanism has no detached work.', 'observed_at': now()}
        result = reconcile(self.f.root, self.f.request({'operation_id': operation_id, 'sender_observations': [observation]}))
        self.assertEqual(result['effect_outcome'], 'succeeded')
        self.assertFalse(result['command_replayed'])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
