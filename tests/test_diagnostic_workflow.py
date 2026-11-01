"""A real red symptom, authorized repair and unchanged-criterion revalidation."""
import json
import subprocess
import sys
import uuid

from workflow_fixture import WorkflowFixture
from evolve_core.analysis import investigate, symptom_reverification
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.store import Store, now
from evolve_core.verify import verify


class DiagnosticWorkflowTests(WorkflowFixture):
    def investigate_symptom(self):
        before = subprocess.run(self.checks[0]['argv'], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(before.returncode, 1)
        source_time = now()
        request = {**self.identity(), 'request_id': str(uuid.uuid4()),
            'authorization': {'source': 'controlled-read-only-investigation', 'text': 'Investigate and record; do not modify business files.',
                              'effect_kinds': ['project_records']},
            'input': {'question': 'Why does total return the count rather than the expected sum?',
                'scope': ['total.py', 'test_total.py'], 'business_effect': 'read_only', 'record_intent': 'record',
                'sources': [{'id': key, 'kind': 'file', 'path': path,
                             'expected_digest': digest((self.root / path).read_bytes()),
                             'observer': 'fixture-source-observer', 'observed_at': source_time, 'limitations': []}
                            for key, path in (('S1', 'total.py'), ('S2', 'test_total.py'))] + [
                    {'id': 'S3', 'kind': 'observation', 'object': 'isolated total tests', 'version': digest((self.root / 'total.py').read_bytes()),
                     'observer': 'actual-fixture-subprocess', 'observed_at': source_time, 'method': 'Configured unit argv',
                     'content': before.stdout + before.stderr, 'limitations': []}],
                'analysis': {'observations': [{'local_key': 'F1', 'statement': 'The literal expected sum fails under the existing test.', 'sources': ['S2', 'S3']}],
                    'hypotheses': [{'local_key': 'H1', 'statement': 'len counts elements instead of adding their values.',
                                    'status': 'supported', 'observations': ['F1'], 'basis': 'Actual failure plus inspection of the one-line function.'}],
                    'answer_status': 'answered', 'conclusion': 'The observed count implementation explains this fixed failing input.',
                    'coverage': ['The isolated files and configured test'], 'limitations': ['No claim about unobserved production data.'],
                    'remaining_questions': [], 'next_steps': ['Propose repair when explicitly authorized.'],
                    'symptom': {'criterion': {'method': 'Configured unit argv with independent literal expectations', 'check': self.checks[0],
                        'environment': 'Isolated Python fixture', 'input': [[2, 3], [], [-2, 3]], 'expected': [5, 0, 1],
                        'expected_source': 'S2', 'side_effects': 'No business writes; Python bytecode disabled'},
                        'status': 'reproduced', 'attempts': 1, 'failures': 1, 'sources': ['S3'], 'limitations': []}}}}
        result = investigate(self.root, request)
        row = self.rows("SELECT result_digest FROM phase_runs WHERE id='" + result['run_id'] + "'")[0]
        self.analysis_basis = {'run_id': result['run_id'], 'result_digest': row['result_digest'],
                               'criterion_digest': result['criterion_digest'],
                               'adoption_basis': 'The same source files, literal expected values and configured command define the authorized repair.'}
        return result

    def diagnostic_plan(self, basis=None, checks=None):
        text = 'Return the sum for ordinary numeric inputs, preserve literal expectations and repeat the original symptom check.'
        return propose(self.root, {**self.identity(), 'request_id': str(uuid.uuid4()), 'authorization': self.auth,
            'input': {'title': 'Repair the investigated count/sum symptom', 'plan': text, 'completion': 'The total sums ordinary input values.',
                'scope': ['total.py', 'test_total.py'], 'required_checks': ['unit'] if checks is None else checks,
                'acceptance': ['Return the sum for ordinary numeric inputs', 'Retain empty and negative behavior', 'Preserve literal test expectations'],
                'analysis_basis': basis or self.analysis_basis,
                'presentation': {'source': 'controlled-diagnostic-plan-message', 'text': text}}})

    def observed_verification(self):
        request = self.verification_request()
        actual = subprocess.run(self.checks[0]['argv'], cwd=self.root, capture_output=True, text=True)
        request['input']['symptom_result'] = {'criterion_digest': self.analysis_basis['criterion_digest'],
            'fingerprint_digest': request['input']['reviews'][0]['fingerprint_digest'],
            'status': 'passed' if actual.returncode == 0 else 'failed', 'observer': 'actual-fixture-subprocess',
            'observed_at': now(), 'basis': 'Repeated the exact original configured test with its unchanged literal expectations.',
            'evidence': actual.stdout + actual.stderr, 'attempts': 1, 'failures': 0 if actual.returncode == 0 else 1,
            'limitations': ['Only the fixed local criterion is established.']}
        return request

    def test_investigation_does_not_grant_modification_and_original_red_is_retained_after_closure(self):
        source = (self.root / 'total.py').read_bytes()
        investigated = self.investigate_symptom()
        self.assertEqual((self.root / 'total.py').read_bytes(), source)
        self.plan = self.diagnostic_plan()
        request = self.apply_request()
        request['authorization'] = {'source': 'investigation-only', 'text': 'Only investigate.', 'effect_kinds': ['project_records']}
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'AUTHORIZATION')
        self.assertEqual((self.root / 'total.py').read_bytes(), source)
        self.assertEqual(implement(self.root, self.apply_request())['outcome'], 'implemented')
        accepted = verify(self.root, self.observed_verification())
        self.assertEqual(accepted['status'], 'passed')
        result = archive(self.root, self.request({'verification_id': accepted['verification_id']}))
        self.assertEqual(result['outcome'], 'archived')
        saved = self.rows("SELECT result_json FROM phase_runs WHERE id='" + investigated['run_id'] + "'")[0]
        self.assertEqual(json.loads(saved['result_json'])['analysis']['symptom']['status'], 'reproduced')
        self.assertIn('AssertionError', self.rows("SELECT b.content FROM evidence e JOIN blobs b ON b.digest=e.content_digest WHERE e.method='analysis:observation'")[0]['content'].decode())
        actual = self.rows("SELECT items_json FROM verifications WHERE id='" + accepted['verification_id'] + "'")[0]
        self.assertEqual(json.loads(actual['items_json'])['symptom_result']['criterion_digest'], investigated['criterion_digest'])

    def test_changing_or_omitting_the_original_check_cannot_silently_change_the_criterion(self):
        self.investigate_symptom()
        for basis, checks in (({**self.analysis_basis, 'criterion_digest': 'different-expectation'}, None), (self.analysis_basis, [])):
            with self.assertRaises(EvolveError) as caught:
                self.diagnostic_plan(basis, checks)
            self.assertEqual(caught.exception.code, 'SYMPTOM_CHANGED')

    def test_green_checks_and_reviews_are_insufficient_without_current_symptom_observation(self):
        self.investigate_symptom()
        self.plan = self.diagnostic_plan()
        implement(self.root, self.apply_request())
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, self.verification_request())
        self.assertEqual(caught.exception.code, 'SYMPTOM_REVERIFY_REQUIRED')
        request = self.observed_verification()
        request['input']['symptom_result']['criterion_digest'] = 'replacement-symptom'
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, request)
        self.assertEqual(caught.exception.code, 'SYMPTOM_CHANGED')

    def test_pre_repair_observation_time_cannot_be_reused_as_post_repair_evidence(self):
        before = self.investigate_symptom()
        self.plan = self.diagnostic_plan()
        implement(self.root, self.apply_request())
        request = self.observed_verification()
        request['input']['symptom_result']['observed_at'] = before['sources'][-1]['observed_at']
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, request)
        self.assertEqual(caught.exception.code, 'SYMPTOM')

    def test_missing_red_or_one_intermittent_absence_must_keep_its_limitations(self):
        self.investigate_symptom()
        self.plan = self.diagnostic_plan()
        implement(self.root, self.apply_request())
        request = self.observed_verification()
        task = self.rows("SELECT * FROM tasks WHERE id='" + self.plan['task_id'] + "'")[0]
        definition = json.loads(task['definition_json'])
        store = Store(self.root)
        try:
            for update in ({'status': 'blocked'}, {'intermittent': True}):
                controlled_definition = json.loads(json.dumps(definition))
                controlled_definition['symptom_before'].update(update)
                item = {**request['input']['symptom_result'], 'limitations': []}
                with self.assertRaises(EvolveError) as caught:
                    symptom_reverification(store, task, controlled_definition, self.current_fingerprint(), item)
                self.assertEqual(caught.exception.code, 'SYMPTOM_LIMITATIONS')
                item['limitations'] = ['This bounded sample does not establish causal elimination.']
                observed = symptom_reverification(store, task, controlled_definition, self.current_fingerprint(), item)
                self.assertTrue(observed['bounded_observation_only'])
                self.assertEqual(observed['causal_resolution'], 'not_inferred')
        finally:
            store.close()

    def test_actual_same_revision_fix_resolves_a_required_finding_without_weakening_the_original_criterion(self):
        self.investigate_symptom()
        self.plan = self.diagnostic_plan()
        revision = self.plan['revision_id']
        implement(self.root, self.apply_request('def total(values):\n    return {(2,3):5, ():0, (-2,3):1}[tuple(values)]\n'))
        request = self.observed_verification()
        request['input']['reviews'][0]['findings'] = [{'id': 'F-hardcoded', 'path': 'total.py', 'blocking': True,
            'basis': 'Inspected the literal lookup table. It only accepts the three test inputs.',
            'impact': 'Ordinary numeric inputs outside the examples do not return their sum, contrary to the accepted plan.'}]
        failed = verify(self.root, request)
        self.assertEqual(failed['status'], 'failed')
        fix = self.apply_request()
        fix['input']['reopen_verification_id'] = failed['verification_id']
        self.assertEqual(implement(self.root, fix)['outcome'], 'implemented')
        request = self.observed_verification()
        observed = subprocess.run([sys.executable, '-B', '-c', 'from total import total; print(total([7,4]))'],
                                  cwd=self.root, capture_output=True, text=True, check=True)
        self.assertEqual(observed.stdout.strip(), '11')
        request['input']['reviews'][0]['resolutions'] = [{'verification_id': failed['verification_id'], 'finding_id': 'F-hardcoded',
            'basis': 'The lookup is replaced by sum(values); a real additional ordinary [7,4] input returns eleven.'}]
        accepted = verify(self.root, request)
        self.assertEqual(accepted['status'], 'passed')
        self.assertEqual(accepted['revision_id'], revision)
        self.assertEqual(archive(self.root, self.request({'verification_id': accepted['verification_id']}))['outcome'], 'archived')
