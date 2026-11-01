"""Real sender drains and selected-snapshot unknown effects survive epoch swaps."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.errors import EvolveError
from evolve_core.external import execute, prepare, reconcile
from evolve_core.maintenance import backup, restore
from evolve_core.package import canonical, digest
from evolve_core.store import now


class ExternalMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)

    def unknown(self):
        (self.f.root / 'writer.py').write_text('import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("receipt lost")\n')
        candidate = prepare(self.f.root, self.f.request())
        return execute(self.f.root, self.f.request({'stage': 'apply', 'candidate_ref': {
            'run_id': candidate['run_id'], 'result_digest': digest(canonical(candidate))},
            'approval': {'candidate_digest': candidate['candidate_digest'],
                'target_digest': candidate['candidate']['target_snapshot']['digest'],
                'source': 'actual-uniform-human-authorization-controlled-fixture', 'text': 'This exact temporary candidate.'}}))

    def plan(self, saved):
        return restore(self.f.root, self.f.request({'stage': 'plan', 'bundle': saved['path'], 'manifest_digest': saved['manifest_digest']}))

    def test_real_sender_group_prevents_restore_before_barrier_or_swap(self):
        saved = backup(self.f.root, self.f.request({}))
        result = self.unknown()
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        try:
            path = self.f.root / '.evolve-local/control/external.json'
            index = json.loads(path.read_text())
            index['pending'][0]['sender'].update(pid=child.pid, state='started')
            path.write_bytes(canonical(index))
            with self.assertRaises(EvolveError) as error:
                self.plan(saved)
            self.assertEqual(error.exception.code, 'CHECK_RUNNING')
            self.assertFalse((self.f.root / '.evolve-local/control/maintenance.json').exists())
            self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
            child.wait()
        self.assertEqual(self.plan(saved)['plan']['external']['pending'][0]['operation_id'], result['operation_id'])

    def test_lost_protocol16_index_is_not_treated_as_no_sender(self):
        saved = backup(self.f.root, self.f.request({}))
        self.unknown()
        (self.f.root / '.evolve-local/control/external.json').unlink()
        with self.assertRaises(EvolveError) as error:
            self.plan(saved)
        self.assertEqual(error.exception.code, 'EXTERNAL_PROTECTION_UNKNOWN')

    def test_selected_snapshot_unknown_is_unioned_and_missing_capsule_rebuilt_from_exact_blob(self):
        original = self.unknown()
        saved = backup(self.f.root, self.f.request({}))
        resolved = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(resolved['effect_outcome'], 'succeeded')
        capsule = self.f.root / resolved['effect_record']['capsule']['capsule_path']
        exact = capsule.read_bytes()
        capsule.unlink()
        plan = self.plan(saved)
        self.assertEqual(len(plan['plan']['external']['pending']), 1)
        self.assertFalse(capsule.exists())  # planning never repairs the live collection
        result = restore(self.f.root, self.f.request({'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']}))
        self.f.identity['expected_workspace_epoch'] = result['workspace_epoch']
        self.assertEqual(capsule.read_bytes(), exact)
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        self.assertEqual(result['external_pending'], 1)
        checked = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(checked['effect_outcome'], 'succeeded')
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_selected_snapshot_capsule_collision_preserves_third_value(self):
        original = self.unknown()
        saved = backup(self.f.root, self.f.request({}))
        resolved = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        capsule = self.f.root / resolved['effect_record']['capsule']['capsule_path']
        third = b'{"third_party":"keep actual bytes"}'
        capsule.write_bytes(third)
        with self.assertRaises(EvolveError) as error:
            self.plan(saved)
        self.assertEqual(error.exception.code, 'EXTERNAL_PROTECTION_CHANGED')
        self.assertEqual(capsule.read_bytes(), third)
