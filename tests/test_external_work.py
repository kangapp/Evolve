"""External data uses the same current Change/Task definition and progress facts."""
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
from evolve_core.external import execute, prepare
from evolve_core.package import canonical, digest


class ExternalWorkTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture(with_work=True)
        self.addCleanup(self.f.close)

    def test_current_work_candidate_and_actual_effect_share_the_real_task(self):
        prepared = prepare(self.f.root, self.f.work_request())
        binding = prepared['candidate']['work_binding']
        self.assertEqual(binding['change_id'], self.f.plan['change_id'])
        self.assertEqual(binding['task_id'], self.f.plan['task_id'])
        result = execute(self.f.root, self.f.work_request({'stage': 'apply', 'candidate_ref': {
            'run_id': prepared['run_id'], 'result_digest': digest(canonical(prepared))}, 'approval': {
                'candidate_digest': prepared['candidate_digest'], 'target_digest': prepared['candidate']['target_snapshot']['digest'],
                'source': 'actual-uniform-human-authorization-specific-controlled-work',
                'text': 'Accept this exact business plan and candidate for this isolated ledger task; run its declared checks and keep the mechanism/test bytes unchanged.'}}))
        self.assertEqual(result['effect_outcome'], 'succeeded')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            task = db.execute('SELECT state,result_json FROM tasks WHERE id=?', (self.f.plan['task_id'],)).fetchone()
            self.assertEqual(task[0], 'done')  # Actual task checks passed; whole verify remains independent.
            saved = json.loads(task[1])
            self.assertEqual(saved['external_operation_id'], result['operation_id'])
            self.assertEqual(saved['external_effect_outcome'], 'succeeded')
            self.assertTrue(saved['external_checks_passed'])
            self.assertIsNotNone(saved['external_goal_observation_digest'])
            self.assertTrue(result['task_completed'])
            self.assertEqual(result['overall_verification'], 'not_run')
            self.assertEqual(db.execute('SELECT state FROM changes WHERE id=?', (self.f.plan['change_id'],)).fetchone()[0], 'active')

    def test_ordinary_file_apply_cannot_satisfy_an_explicit_data_task(self):
        request = self.f.work_request({'files': [], 'accepted_plan_digest': self.f.plan['plan_digest']})
        request['authorization'] = {**self.f.auth, 'effect_kinds': self.f.auth['effect_kinds'] + ['business_files']}
        with self.assertRaises(EvolveError) as error:
            implement(self.f.root, request)
        self.assertEqual(error.exception.code, 'EXTERNAL_METHOD_REQUIRED')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])
        self.assertFalse(self.f.rows('SELECT operation_id FROM operation_receipts'))
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT state FROM tasks').fetchone()[0], 'todo')

    def test_wrong_task_target_is_not_attached_or_executed(self):
        request = self.f.work_request()
        request['input'] = {**request['input'], 'target': {**self.f.target, 'scope': 'some other data range'}}
        request['authorization'] = {**self.f.auth, 'external_targets': [{**self.f.auth['external_targets'][0], 'scope': 'some other data range'}]}
        with self.assertRaises(EvolveError) as error:
            prepare(self.f.root, request)
        self.assertEqual(error.exception.code, 'EXTERNAL_TASK')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])

    def verified_request(self, *, passed):
        from evolve_core.work import fingerprint
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            definition = json.loads(db.execute('SELECT definition_json FROM tasks WHERE id=?', (self.f.plan['task_id'],)).fetchone()[0])
        snapshot = fingerprint(self.f.root, definition)
        reviews = [{'axis': axis, 'observer': 'actual-controlled-fixture-review',
            'summary': 'Actually inspected fixed mechanism, provider receipt, actual scoped data and independent test; this is controlled fixture evidence, not native review.',
            'fingerprint_digest': snapshot['digest'], 'findings': []} for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': a['id'], 'status': 'passed' if passed else 'failed',
            'basis': 'Actual target ledger id=1 compared with literal 20 and the original provider receipt.'} for a in self.f.plan['acceptance']]
        return self.f.work_request({'reviews': reviews})

    def perform_bound(self, *, lost=False):
        if lost:
            (self.f.root / 'writer.py').write_text('import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("lost receipt")\n')
        observations = {name: digest((self.f.root / name).read_bytes()) for name in self.f.files}
        prepared = prepare(self.f.root, self.f.work_request({**self.f.data, 'observations': observations}))
        request = self.f.work_request({'stage': 'apply', 'observations': observations, 'candidate_ref': {
            'run_id': prepared['run_id'], 'result_digest': digest(canonical(prepared))}, 'approval': {
            'candidate_digest': prepared['candidate_digest'], 'target_digest': prepared['candidate']['target_snapshot']['digest'],
            'source': 'actual-uniform-human-authorization-controlled-bound-candidate', 'text': 'Accept this exact isolated ledger business plan and candidate, including actual task checks.'}})
        return execute(self.f.root, request)

    def test_actual_task_checks_and_final_verification_archive_then_current_data_failure(self):
        from evolve_core.verify import verify
        from evolve_core.archive import archive
        result = self.perform_bound()
        self.assertTrue(result['task_completed'])
        verified = verify(self.f.root, self.verified_request(passed=True))
        self.assertEqual(verified['status'], 'passed')
        sealed = archive(self.f.root, self.f.work_request({'verification_id': verified['verification_id']}))
        self.assertEqual(sealed['outcome'], 'archived')
        with sqlite3.connect(self.f.database) as db:
            db.execute('UPDATE ledger SET value=19 WHERE id=1')
        later = verify(self.f.root, self.verified_request(passed=False))
        self.assertEqual(later['status'], 'blocked')
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT state FROM changes').fetchone()[0], 'archived')
            self.assertEqual(db.execute('SELECT status FROM verifications ORDER BY rowid').fetchall(), [('passed',), ('blocked',)])
            actual = json.loads(db.execute('SELECT items_json FROM verifications WHERE id=?', (later['verification_id'],)).fetchone()[0])
            self.assertEqual(actual['external_goal_observations'][self.f.plan['task_id']]['status'], 'blocked')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(19,)])

    def test_unknown_reconcile_and_explicit_checks_continue_without_replaying_data(self):
        from evolve_core.external import reconcile
        original = self.perform_bound(lost=True)
        self.assertEqual(original['effect_outcome'], 'unknown')
        observed = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(observed['effect_outcome'], 'succeeded')
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT state FROM tasks').fetchone()[0], 'in_progress')
        checked = execute(self.f.root, self.f.work_request({'stage': 'checks', 'operation_id': original['operation_id'],
            'observations': {'writer.py': digest((self.f.root / 'writer.py').read_bytes())}}))
        self.assertTrue(checked['task_completed'])
        self.assertFalse(checked['external_dispatch'])
        self.assertFalse(checked['command_replayed'])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_real_check_process_exit_after_commit_is_recovered_without_replaying_data_or_checks(self):
        import subprocess
        from evolve_core.external import reconcile
        from evolve_core.recover import recover
        original = self.perform_bound(lost=True)
        reconciled = reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        self.assertEqual(reconciled['effect_outcome'], 'succeeded')
        request = self.f.work_request({'stage': 'checks', 'operation_id': original['operation_id']})
        script = ('import json,os,sys\nfrom evolve_core import external\n'
                  'def fault(name):\n    if name=="task_checks_committed": os._exit(73)\n'
                  'external.fault_point=fault\nexternal.execute(sys.argv[1],json.loads(sys.argv[2]))\n')
        environment = dict(__import__('os').environ)
        environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'runtime')
        child = subprocess.run([sys.executable, '-B', '-c', script, str(self.f.root), json.dumps(request)], env=environment, capture_output=True, text=True)
        self.assertEqual(child.returncode, 73, child.stderr)
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            run_id, operation_id = db.execute("SELECT r.id,o.id FROM phase_runs r JOIN operations o ON o.run_id=r.id WHERE r.status='started' AND o.effect_kind='project_records'").fetchone()
            check_count = db.execute("SELECT COUNT(*) FROM events WHERE run_id=? AND kind='check_process_started'", (run_id,)).fetchone()[0]
            self.assertEqual(db.execute('SELECT state FROM tasks WHERE id=?', (self.f.plan['task_id'],)).fetchone()[0], 'done')
        result = recover(self.f.root, self.f.request({'operation_id': operation_id}))
        self.assertTrue(result['original_facts_committed'])
        self.assertFalse(result['business_commands_run'])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE run_id=? AND kind='check_process_started'", (run_id,)).fetchone()[0], check_count)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT status FROM phase_runs WHERE id=?', (run_id,)).fetchone()[0], 'interrupted')
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_proven_same_definition_revision_continues_readonly_checks_but_cannot_rebind_write_candidate(self):
        import copy
        from evolve_core.external import reconcile
        from evolve_core.revisions import revise, _old_document
        original = self.perform_bound(lost=True)
        reconcile(self.f.root, self.f.request({'operation_id': original['operation_id']}))
        data = copy.deepcopy(self.f.data)
        data['preconditions'][0]['expected_rows'] = [[1, 20]]
        observations = {name: digest((self.f.root / name).read_bytes()) for name in self.f.files}
        prepared = prepare(self.f.root, self.f.work_request({**data, 'observations': observations}))
        from evolve_core.store import Store
        store = Store(self.f.root)
        try:
            change = store.one('SELECT * FROM changes WHERE id=?', (self.f.plan['change_id'],))
            revision = store.one('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],))
            tasks = store.connection.execute('SELECT * FROM tasks WHERE revision_id=?', (revision['id'],)).fetchall()
            proposal = _old_document(store.connection, change, revision, tasks)
        finally:
            store.close()
        proposal['plan'] = 'Clearer description of the same isolated ledger behavior and unchanged original checks.'
        proposal['presentation'] = {'source': 'actual-controlled-same-definition-fixture', 'text': proposal['plan']}
        revised = revise(self.f.root, self.f.work_request({'reason': 'Clarify prose without changing the concrete data behavior.', 'proposal': proposal}))
        self.assertTrue(revised['semantic_same'])
        self.f.plan['task_id'] = revised['tasks'][0]['id']
        with self.assertRaises(EvolveError) as error:
            execute(self.f.root, self.f.work_request({'stage': 'apply', 'observations': observations, 'candidate_ref': {
                'run_id': prepared['run_id'], 'result_digest': digest(canonical(prepared))}, 'approval': {
                    'candidate_digest': prepared['candidate_digest'], 'target_digest': prepared['candidate']['target_snapshot']['digest'],
                    'source': 'actual-controlled-old-candidate', 'text': 'Old candidate must not acquire a new revision binding.'}}))
        self.assertEqual(error.exception.code, 'EXTERNAL_TASK_CHANGED')
        completed = execute(self.f.root, self.f.work_request({'stage': 'checks', 'operation_id': original['operation_id'], 'observations': observations}))
        self.assertTrue(completed['task_completed'])
        self.assertFalse(completed['external_dispatch'])
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])

    def test_other_change_cannot_resend_to_the_same_unknown_provider_scope(self):
        import copy
        from evolve_core.plans import propose
        original = self.perform_bound(lost=True)
        self.f.plan = propose(self.f.root, self.f.request({'title': 'Another plan for the same unknown data scope',
            'plan': 'Observe current ledger and use the same finite mechanism only after unknown effects are resolved.',
            'completion': 'Independent current data check passes.', 'scope': sorted(self.f.files) + ['test_target.py'],
            'required_checks': ['data'], 'execution_kind': 'external_write', 'external_target': self.f.target,
            'acceptance': ['Actual ledger is (1,20) with no unresolved prior effect.'], 'presentation': {
                'source': 'actual-controlled-second-change-fixture',
                'text': 'Observe current ledger and use the same finite mechanism only after unknown effects are resolved.'}}))
        data = copy.deepcopy(self.f.data)
        data['preconditions'][0]['expected_rows'] = [[1, 20]]
        candidate = prepare(self.f.root, self.f.work_request(data))
        with self.assertRaises(EvolveError) as error:
            execute(self.f.root, self.f.work_request({'stage': 'apply', 'candidate_ref': {
                'run_id': candidate['run_id'], 'result_digest': digest(canonical(candidate))}, 'approval': {
                    'candidate_digest': candidate['candidate_digest'], 'target_digest': candidate['candidate']['target_snapshot']['digest'],
                    'source': 'actual-controlled-new-change', 'text': 'A new Change must not bypass the same unknown target.'}}))
        self.assertEqual(error.exception.code, 'EXTERNAL_PENDING')
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
        self.assertEqual(json.loads((self.f.root / '.evolve-local/control/external.json').read_text())['pending'][0]['operation_id'], original['operation_id'])
