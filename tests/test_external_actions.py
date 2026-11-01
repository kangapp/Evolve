"""Cancellation retains facts, sourced claims are checked, compensation writes once."""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.cancellation import cancel_change
from evolve_core.errors import EvolveError
from evolve_core.external import execute, prepare, reconcile
from evolve_core.external_actions import compensate, record
from evolve_core.package import canonical, digest
from evolve_core.store import now


class ExternalActionsTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)

    def apply_request(self, prepared):
        return self.f.request({'stage': 'apply', 'candidate_ref': {'run_id': prepared['run_id'],
            'result_digest': digest(canonical(prepared))}, 'approval': {'candidate_digest': prepared['candidate_digest'],
            'target_digest': prepared['candidate']['target_snapshot']['digest'],
            'source': 'actual-uniform-authorization-specific-fixture', 'text': 'This exact temporary candidate only.'}})

    def perform(self, *, lost=False):
        if lost:
            (self.f.root / 'writer.py').write_text('import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("lost")\n')
        return execute(self.f.root, self.apply_request(prepare(self.f.root, self.f.request())))

    def test_cancel_unknown_keeps_claims_and_actual_effects_then_reconcile_still_records_past_facts(self):
        original = self.perform(lost=True)
        request = self.f.request({'external_operation_id': original['operation_id'], 'reason': 'Stop this original sender authorization; preserve actual effects.'})
        cancelled = cancel_change(self.f.root, request)
        self.assertFalse(cancelled['claims_released'])
        self.assertEqual(cancel_change(self.f.root, request), cancelled)
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertGreater(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE kind='authorization_revoked'").fetchone()[0], 1)
        self.assertEqual(len(json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending']), 1)
        confirmed = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(confirmed['effect_outcome'], 'succeeded')
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        self.assertTrue(confirmed['effect_record']['future_dispatch_revoked_by'])

    def test_reported_success_is_preserved_as_a_claim_and_does_not_release_unverified_effects(self):
        original = self.perform(lost=True)
        with sqlite3.connect(self.f.database) as db:
            db.execute("UPDATE identity SET value='actually-another-target'")
        observation = {'source': 'controlled-human-report', 'basis': 'Human supplied claim, independently compared with actual target.',
            'observed_at': now(), 'scope': self.f.target['scope'], 'reported_outcome': 'succeeded',
            'known_effects': ['Claims ledger row is 20'], 'unknown_scope': [], 'limitations': ['This claim is not a provider observation.']}
        result = record(self.f.root, self.f.request({'operation_id': original['operation_id'], 'observation': observation}))
        self.assertEqual(result['reported_observation'], observation)
        self.assertEqual(result['effect_outcome'], 'unknown')
        self.assertFalse(result['latest_observation']['terminal_confirmed'])
        self.assertEqual(len(json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending']), 1)
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertGreater(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE kind='external_observation_reported'").fetchone()[0], 1)

    def compensation_data(self, original):
        alias = json.loads((self.f.root / 'alias.json').read_text())
        alias.update(before=20, after=10)
        (self.f.root / 'alias.json').write_text(json.dumps(alias))
        data = copy.deepcopy(self.f.data)
        data['compensates_operation_id'] = original['operation_id']
        data['preconditions'][0]['expected_rows'] = [[1, 20]]
        data['reconciliation']['effects'][0]['expected_rows'] = [[1, 10]]
        return data

    def test_compensation_has_its_own_candidate_approval_operation_and_real_once_only_write(self):
        original = self.perform()
        candidate = compensate(self.f.root, self.f.request(self.compensation_data(original)))
        self.assertEqual(candidate['candidate']['compensation_of']['operation_id'], original['operation_id'])
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        request = self.apply_request(candidate)
        result = compensate(self.f.root, request)
        self.assertEqual(result['effect_outcome'], 'succeeded')
        self.assertNotEqual(result['operation_id'], original['operation_id'])
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(2,)])
        self.assertEqual(compensate(self.f.root, request), result)
        with self.assertRaises(EvolveError):
            compensate(self.f.root, self.apply_request(candidate))
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(2,)])

    def test_unknown_original_does_not_authorize_compensation(self):
        original = self.perform(lost=True)
        with self.assertRaises(EvolveError) as error:
            compensate(self.f.root, self.f.request(self.compensation_data(original)))
        self.assertEqual(error.exception.code, 'EXTERNAL_COMPENSATION_UNKNOWN')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])

    def test_changed_actual_original_scope_invalidates_prepared_compensation(self):
        original = self.perform()
        candidate = compensate(self.f.root, self.f.request(self.compensation_data(original)))
        with sqlite3.connect(self.f.database) as db:
            db.execute('UPDATE ledger SET value=19 WHERE id=1')
        with self.assertRaises(EvolveError):
            compensate(self.f.root, self.apply_request(candidate))
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(19,)])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
