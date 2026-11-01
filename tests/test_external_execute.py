"""Real SQLite modifications behind exact candidate approval and durable admission."""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.errors import EvolveError
from evolve_core.external import execute, prepare
from evolve_core.package import canonical, digest


class ExternalExecuteTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)

    def approved(self, data=None, request_id=None):
        prepared = prepare(self.f.root, self.f.request(data))
        return self.f.request({'stage': 'apply', 'candidate_ref': {
            'run_id': prepared['run_id'], 'result_digest': digest(canonical(prepared))},
            'approval': {'candidate_digest': prepared['candidate_digest'],
                'target_digest': prepared['candidate']['target_snapshot']['digest'],
                'source': 'actual-uniform-human-authorization-specific-temporary-data-fixture',
                'text': 'Apply this exact saved candidate against this exact isolated target/scope; this is the controlled fixture, not production.'}}, request_id)

    def test_actual_write_has_receipt_data_observation_and_no_duplicate_replay(self):
        request = self.approved(request_id='actual-external-write')
        result = execute(self.f.root, request)
        self.assertEqual(result['effect_outcome'], 'succeeded')
        self.assertEqual(result['business_acceptance'], 'not_inferred')
        self.assertEqual(result['effect_record']['last_observation']['verification_status'], 'passed')
        self.assertEqual(self.f.rows('SELECT id,value FROM ledger'), [(1, 20)])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        self.assertEqual(execute(self.f.root, request), result)
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        index = json.loads((self.f.root / '.evolve-local/control/external.json').read_text())
        self.assertFalse(index['pending'])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM phase_runs WHERE status='started'").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM source_runs WHERE purpose='external_execution_candidate'").fetchone()[0], 1)

    def test_wrong_actual_approval_and_indirect_changes_do_not_dispatch(self):
        request = self.approved()
        wrong = copy.deepcopy(request)
        wrong['input']['approval']['target_digest'] = 'other-actual-target'
        with self.assertRaises(EvolveError) as error:
            execute(self.f.root, wrong)
        self.assertEqual(error.exception.code, 'EXTERNAL_APPROVAL')
        (self.f.root / 'step.sql').write_text('UPDATE ledger SET value=99;\n')
        with self.assertRaises(EvolveError) as error:
            execute(self.f.root, request)
        self.assertEqual(error.exception.code, 'EXTERNAL_MATERIAL_CHANGED')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])
        self.assertFalse(self.f.rows('SELECT operation_id FROM operation_receipts'))
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM phase_runs WHERE status='started'").fetchone()[0], 0)

    def test_lost_receipt_keeps_actual_effects_unknown_claimed_and_not_resent(self):
        (self.f.root / 'writer.py').write_text('import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("deliberately lost receipt")\n')
        request = self.approved()
        result = execute(self.f.root, request)
        self.assertEqual(result['effect_outcome'], 'unknown')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        self.assertEqual(execute(self.f.root, request), result)
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        index = json.loads((self.f.root / '.evolve-local/control/external.json').read_text())
        self.assertEqual(index['pending'][0]['operation_id'], result['operation_id'])
        self.assertEqual(index['pending'][0]['state'], 'unknown')
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertGreater(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM phase_runs WHERE status='started'").fetchone()[0], 0)
        # Same scope remains protected even if a new candidate is prepared from
        # the actual new value; a fresh request cannot guess away unknown effects.
        self.f.data['preconditions'][0]['expected_rows'] = [[1, 20]]
        another = self.approved()
        with self.assertRaises(EvolveError) as error:
            execute(self.f.root, another)
        self.assertEqual(error.exception.code, 'EXTERNAL_PENDING')
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_actual_partial_commit_is_failed_with_complete_known_scope_not_not_started(self):
        with sqlite3.connect(self.f.database) as db:
            db.execute('INSERT INTO ledger VALUES(2,10)')
        self.f.target['scope'] = 'ledger ids 1 and 2 and this operation receipt only'
        self.f.auth['external_targets'][0]['scope'] = self.f.target['scope']
        (self.f.root / 'writer.py').write_text('import json,sqlite3,sys\np=sys.argv[1];op=sys.argv[2]\n'
            'with sqlite3.connect(p) as db:\n    identity=db.execute("SELECT value FROM identity").fetchone()[0]\n'
            '    assert identity=="temporary-external-target"\n    db.execute("UPDATE ledger SET value=20 WHERE id=1 AND value=10")\n'
            '    db.execute("INSERT INTO operation_receipts VALUES(?,?,?,1)",(op,"failed",json.dumps({"changed_ids":[1],"unchanged_ids":[2]})))\n'
            'print(json.dumps({"operation_id":op,"target_identity":identity,"provider_operation_ref":op}))\n')
        self.f.data['preconditions'][0].update(sql='SELECT id,value FROM ledger ORDER BY id', expected_rows=[[1, 10], [2, 10]])
        self.f.data['reconciliation']['effects'][0].update(sql='SELECT id,value FROM ledger ORDER BY id', expected_rows=[[1, 20], [2, 20]])
        self.f.data['reconciliation']['coverage_basis'] = 'Actually inspected the complete two-row target and finite writer; row 1 changes, row 2 remains, provider explicitly ends failed.'
        result = execute(self.f.root, self.approved())
        self.assertEqual(result['effect_outcome'], 'failed')
        self.assertTrue(result['effect_record']['terminal_confirmed'])
        observed = result['effect_record']['last_observation']
        self.assertEqual(observed['scope_observations'][0]['rows'], [[1, 20], [2, 10]])
        self.assertEqual(observed['provider_known_effects'], {'changed_ids': [1], 'unchanged_ids': [2]})
        self.assertEqual(self.f.rows('SELECT id,value FROM ledger ORDER BY id'), [(1, 20), (2, 10)])
        self.assertFalse(json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending'])
        self.assertEqual(result['business_acceptance'], 'not_inferred')

    def test_actual_timeout_after_commit_keeps_unknown_until_separate_probe_without_resend(self):
        from evolve_core.external import reconcile
        (self.f.root / 'writer.py').write_text('import sys,time\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\ntime.sleep(60)\n')
        data = copy.deepcopy(self.f.data)
        data['execution']['timeout'] = 1
        result = execute(self.f.root, self.approved(data))
        self.assertEqual(result['effect_outcome'], 'unknown')
        self.assertTrue(result['effect_record']['transport']['timed_out'])
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        self.assertEqual(len(json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending']), 1)
        observed = reconcile(self.f.root, self.f.request({'operation_id': result['operation_id']}))
        self.assertEqual(observed['effect_outcome'], 'succeeded')
        self.assertFalse(observed['command_replayed'])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_unknown_target_does_not_block_another_actual_provider_identity(self):
        from external_fixture import ENTRY
        (self.f.root / 'writer.py').write_text('import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("lost")\n')
        first = execute(self.f.root, self.approved())
        self.assertEqual(first['effect_outcome'], 'unknown')
        second_db = self.f.root / 'other-business.db'
        db = sqlite3.connect(second_db)
        try:
            db.executescript("CREATE TABLE identity(value TEXT); INSERT INTO identity VALUES('another-actual-provider'); "
                'CREATE TABLE ledger(id INTEGER PRIMARY KEY,value INTEGER); INSERT INTO ledger VALUES(1,10); '
                'CREATE TABLE operation_receipts(operation_id TEXT PRIMARY KEY,outcome TEXT,known_effects_json TEXT,finished INTEGER);')
            db.commit()
        finally:
            db.close()
        self.f.target = {**self.f.target, 'path': 'other-business.db',
            'identity': {'sql': 'SELECT value FROM identity', 'expected': 'another-actual-provider'}}
        self.f.data['target'] = self.f.target
        self.f.auth['external_targets'].append({**{k: self.f.target[k] for k in ('kind', 'path', 'environment', 'objects', 'scope')}, 'provider_identity': 'another-actual-provider'})
        (self.f.root / 'alias.json').write_text(json.dumps({'sql': 'step.sql', 'identity': 'another-actual-provider', 'before': 10, 'after': 20}))
        (self.f.root / 'writer.py').write_text(ENTRY)
        second = execute(self.f.root, self.approved())
        self.assertEqual(second['effect_outcome'], 'succeeded')
        pending = json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending']
        self.assertEqual([r['operation_id'] for r in pending], [first['operation_id']])
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        db = sqlite3.connect(second_db)
        try:
            self.assertEqual(db.execute('SELECT value FROM ledger').fetchall(), [(20,)])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM operation_receipts').fetchone()[0], 1)
        finally:
            db.close()
