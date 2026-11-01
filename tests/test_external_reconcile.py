"""Resolve real unknown effects without replay, including after older archive restore."""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.external import execute, prepare, reconcile
from evolve_core.maintenance import backup, restore
from evolve_core.package import canonical, digest


class ExternalReconcileTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)

    def unknown(self):
        (self.f.root / 'writer.py').write_text('import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("lost receipt after actual commit")\n')
        prepared = prepare(self.f.root, self.f.request())
        request = self.f.request({'stage': 'apply', 'candidate_ref': {'run_id': prepared['run_id'], 'result_digest': digest(canonical(prepared))},
            'approval': {'candidate_digest': prepared['candidate_digest'], 'target_digest': prepared['candidate']['target_snapshot']['digest'],
                'source': 'actual-uniform-human-authorization-specific-controlled-fixture', 'text': 'This exact temporary SQLite candidate only, not production.'}})
        result = execute(self.f.root, request)
        self.assertEqual(result['effect_outcome'], 'unknown')
        return result

    def test_lost_receipt_is_actually_probed_once_and_never_replayed(self):
        original = self.unknown()
        request = self.f.request({'operation_id': original['operation_id']})
        result = reconcile(self.f.root, request)
        self.assertEqual(result['effect_outcome'], 'succeeded')
        self.assertFalse(result['command_replayed'])
        self.assertEqual(result['latest_observation']['scope_observations'][0]['rows'], [[1, 20]])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        self.assertEqual(reconcile(self.f.root, request), result)
        self.assertFalse(json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending'])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM phase_runs WHERE status='started'").fetchone()[0], 0)

    def test_probe_failure_retains_unknown_then_later_failure_does_not_erase_confirmed_facts(self):
        original = self.unknown()
        with sqlite3.connect(self.f.database) as db:
            db.execute("UPDATE identity SET value='wrong-resolved-target'")
        failed = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(failed['effect_outcome'], 'unknown')
        self.assertFalse(failed['latest_observation']['terminal_confirmed'])
        self.assertEqual(len(json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending']), 1)
        with sqlite3.connect(self.f.database) as db:
            db.execute("UPDATE identity SET value='temporary-external-target'")
        confirmed = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(confirmed['effect_outcome'], 'succeeded')
        with sqlite3.connect(self.f.database) as db:
            db.execute("UPDATE identity SET value='wrong-resolved-target'")
        later = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(later['effect_outcome'], 'succeeded')
        self.assertEqual(later['latest_observation']['effect_outcome'], 'unknown')
        self.assertTrue(later['effect_record']['terminal_confirmed'])
        self.assertEqual(later['effect_record']['confirmed_observation_digest'], confirmed['effect_record']['confirmed_observation_digest'])
        self.assertEqual(later['effect_record']['confirmed_observation_run_id'], confirmed['effect_record']['confirmed_observation_run_id'])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_older_archive_preserves_pending_capsule_and_reconciliation_does_not_invent_old_run(self):
        saved = backup(self.f.root, self.f.request({}))
        original = self.unknown()
        plan = restore(self.f.root, self.f.request({'stage': 'plan', 'bundle': saved['path'], 'manifest_digest': saved['manifest_digest']}))
        restored = restore(self.f.root, self.f.request({'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']}))
        self.f.identity['expected_workspace_epoch'] = restored['workspace_epoch']
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        self.assertEqual(len(json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending']), 1)
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM operations WHERE effect_kind='external_write'").fetchone()[0], 0)
        result = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(result['effect_outcome'], 'succeeded')
        self.assertTrue(result['effect_record']['restored_protection_source']['source_is_protected_capsule_not_a_fabricated_old_run'])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM phase_runs WHERE id=?', (original['run_id'],)).fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)

    def test_valid_but_different_pending_capsule_cannot_override_the_recorded_operation_source(self):
        from evolve_core.errors import EvolveError
        original = self.unknown()
        with sqlite3.connect(self.f.database) as db:
            db.execute('UPDATE ledger SET value=19 WHERE id=1')
        index_path = self.f.root / '.evolve-local/control/external.json'
        index = json.loads(index_path.read_text())
        pending = index['pending'][0]
        capsule_path = self.f.root / pending['capsule_path']
        capsule = json.loads(capsule_path.read_text())
        capsule['candidate']['reconciliation']['effects'][0]['expected_rows'] = [[1, 19]]
        capsule['candidate_digest'] = digest(canonical(capsule['candidate']))
        capsule['approval']['candidate_digest'] = capsule['candidate_digest']
        encoded = canonical(capsule)
        capsule_path.write_bytes(encoded)
        pending['capsule_digest'] = digest(encoded)
        index_path.write_bytes(canonical(index))
        with self.assertRaises(EvolveError) as error:
            reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(error.exception.code, 'EXTERNAL_SOURCE_CONFLICT')
        from evolve_core.cancellation import cancel_change
        with self.assertRaises(EvolveError) as cancelled:
            cancel_change(self.f.root, self.f.request({'external_operation_id': original['operation_id'], 'reason': 'Preserve conflicting source; no guessed revocation.'}))
        self.assertEqual(cancelled.exception.code, 'EXTERNAL_SOURCE_CONFLICT')
        self.assertEqual(capsule_path.read_bytes(), encoded)
        self.assertEqual(json.loads(index_path.read_text())['pending'][0]['operation_id'], original['operation_id'])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            value = json.loads(db.execute('SELECT result_json FROM operations WHERE id=?', (original['operation_id'],)).fetchone()[0])
            self.assertEqual(value['effect_outcome'], 'unknown')
            self.assertGreater(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)


    def test_pending_resources_cannot_change_the_immutable_capsule_resource_protection(self):
        from evolve_core.errors import EvolveError
        original = self.unknown()
        path = self.f.root / '.evolve-local/control/external.json'
        index = json.loads(path.read_text())
        index['pending'][0]['resources'] = ['external:another-provider:object:ledger']
        changed = canonical(index)
        path.write_bytes(changed)
        with self.assertRaises(EvolveError) as error:
            reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(error.exception.code, 'EXTERNAL_SOURCE_CONFLICT')
        self.assertEqual(path.read_bytes(), changed)
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
