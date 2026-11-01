"""A diagnosed repair retains its actual criterion inside a complex Task."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
import zipfile

import test_diagnostic_workflow as diagnostic_fixture
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.plans import propose
from evolve_core.revisions import revise
from evolve_core.structured import document, whole_definition
from evolve_core.verify import verify
from evolve_core.work import fingerprint


class StructuredDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.f = diagnostic_fixture.DiagnosticWorkflowTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.investigate_symptom()
        self.root = self.f.root
        self.data = {'complexity': 'complex', 'title': 'Diagnosed structured sum repair',
            'plan': 'Repair only total.py using the original investigation and literal check.',
            'completion': 'The original sum symptom is independently reverified.',
            'scope': ['total.py'], 'required_checks': ['unit'],
            'acceptance': [{'key': 'SUM', 'text': 'Positive, empty and negative inputs retain the original literal sums.'}],
            'analysis_basis': self.f.analysis_basis,
            'spec': {'problem': 'The observed count implementation fails the literal sum criterion.',
                'goals': ['Restore the original sum behavior.'], 'non_goals': ['No test changes.'],
                'behavior': ['Preserve positive, empty and negative sums.'], 'constraints': ['Keep the actual original criterion.'],
                'tradeoffs': [], 'test_decisions': ['Repeat the original literal check and independently observe the symptom.'],
                'open_questions': []},
            'tasks': [{'local_key': 'SUM', 'title': 'Correct total', 'completion': 'Original sum behavior passes.',
                'validation': 'Repeat the actual original criterion.', 'scope': ['total.py'], 'required_checks': ['unit'],
                'acceptance': ['SUM'], 'context_paths': ['test_total.py'], 'exclusions': ['Test modification'],
                'test_decision_refs': ['spec.test_decisions/0'], 'dependencies': []}]}

    def proposal(self, data=None):
        data = copy.deepcopy(self.data if data is None else data)
        data['presentation'] = {'source': 'controlled-full-diagnostic-spec', 'document': document(data)}
        return {**self.f.identity(), 'request_id': str(uuid.uuid4()), 'authorization': self.f.auth, 'input': data}

    def select(self, plan):
        self.f.plan = {**plan, 'task_id': plan['tasks'][0]['id'],
                       'definition_digest': plan['tasks'][0]['definition_digest']}

    def task_request(self, request):
        request['input']['task_id'] = self.f.plan['task_id']
        request['expected_versions'] = {'change': request['expected_versions']['change'],
                                       'tasks': {self.f.plan['task_id']: request['expected_versions']['task']}}
        return request

    def whole_request(self):
        request = self.task_request(self.f.verification_request())
        revision = self.f.rows('SELECT * FROM plan_revisions WHERE id=?', (self.f.plan['revision_id'],))[0]
        tasks = self.f.rows('SELECT * FROM tasks WHERE revision_id=?', (revision['id'],))
        observed = fingerprint(self.root, whole_definition(revision, tasks))
        request['input'].update(task_id=None, definition_digest=revision['definition_digest'])
        for review in request['input']['reviews']:
            review['fingerprint_digest'] = observed['digest']
        return request

    def test_single_task_root_binding_requires_original_post_repair_observation(self):
        request = self.proposal()
        plan = propose(self.root, request)
        self.assertEqual(request['input']['presentation']['document']['analysis_basis'], self.f.analysis_basis)
        self.select(plan)
        definition = json.loads(self.f.rows('SELECT definition_json FROM tasks WHERE id=?', (self.f.plan['task_id'],))[0]['definition_json'])
        self.assertEqual(definition['analysis_basis'], self.f.analysis_basis)
        self.assertEqual(definition['symptom_before']['status'], 'reproduced')
        links = self.f.rows('SELECT * FROM source_runs WHERE run_id=? AND purpose=?', (plan['run_id'], 'repair_analysis_basis'))
        self.assertEqual(links[0]['source_run_id'], self.f.analysis_basis['run_id'])
        implement(self.root, self.task_request(self.f.apply_request()))
        self.assertEqual(verify(self.root, self.whole_request())['status'], 'blocked')
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, self.task_request(self.f.verification_request()))
        self.assertEqual(caught.exception.code, 'SYMPTOM_REVERIFY_REQUIRED')
        request = self.task_request(self.f.observed_verification())
        self.assertEqual(verify(self.root, request)['status'], 'passed')
        whole = verify(self.root, self.whole_request())
        self.assertEqual(whole['status'], 'passed')
        request = self.whole_request()
        request['input']['verification_id'] = whole['verification_id']
        self.assertEqual(archive(self.root, request)['outcome'], 'archived')
        (self.root / 'test_total.py').write_text((self.root / 'test_total.py').read_text() + '# External input change\n')
        self.assertEqual(verify(self.root, self.whole_request())['status'], 'blocked')

    def test_task_level_binding_is_presented_and_not_silently_ignored(self):
        data = copy.deepcopy(self.data)
        data['tasks'][0]['analysis_basis'] = data.pop('analysis_basis')
        plan = propose(self.root, self.proposal(data))
        definition = json.loads(self.f.rows('SELECT definition_json FROM tasks WHERE id=?', (plan['tasks'][0]['id'],))[0]['definition_json'])
        self.assertEqual(definition['analysis_basis'], self.f.analysis_basis)
        self.assertEqual(definition['symptom_before']['criterion']['check'], self.f.checks[0])

    def test_cosmetic_revision_preserves_binding_but_removal_needs_exact_confirmation(self):
        plan = propose(self.root, self.proposal())
        self.select(plan)
        implement(self.root, self.task_request(self.f.apply_request()))
        observed = verify(self.root, self.task_request(self.f.observed_verification()))
        old = self.f.rows('SELECT * FROM verifications WHERE id=?', (observed['verification_id'],))[0]
        data = copy.deepcopy(self.data)
        data.update(title='Readable diagnosed repair', plan='Same original criterion, clearer prose.')
        proposal = self.proposal(data)['input']
        request = self.whole_request()
        request['input'].update(proposal=proposal, reason='Clarify prose without changing the observed repair.')
        revised = revise(self.root, request)
        self.assertTrue(revised['semantic_same'])
        self.assertTrue(revised['tasks'][0]['result_reused'])
        self.select({**revised, 'acceptance': plan['acceptance']})
        self.assertEqual(self.f.rows('SELECT * FROM verifications WHERE id=?', (observed['verification_id'],))[0], old)
        self.assertEqual(verify(self.root, self.whole_request())['status'], 'passed')
        data.pop('analysis_basis')
        request = self.whole_request()
        request['input'].update(proposal=self.proposal(data)['input'], reason='Explicitly propose removing the old investigation criterion.')
        self.assertEqual(revise(self.root, request)['outcome'], 'scope_confirmation_required')

    def test_complete_alpha17_writer_cannot_ignore_protocol14_repair_semantics(self):
        old = self.root / '.evolve-local/old-alpha17'
        source = Path(__file__).resolve().parents[1] / 'tests/fixtures/runtime-package-alpha17.zip'
        with zipfile.ZipFile(source) as bundle:
            bundle.extractall(old)
        database = self.root / 'evolve/history.db'
        before = database.read_bytes()
        result = subprocess.run([sys.executable, '-B', str(old / 'runtime/evolve.py'), '--project', str(self.root),
            'apply', '--request', '-'], input=json.dumps(self.f.apply_request()), capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'SCHEMA_VERSION')
        self.assertEqual(database.read_bytes(), before)

    def test_task_binding_rejects_a_changed_criterion_or_missing_original_check(self):
        for change in ('criterion', 'check'):
            data = copy.deepcopy(self.data)
            basis = data.pop('analysis_basis')
            if change == 'criterion':
                basis['criterion_digest'] = 'another-expected-value'
            else:
                data['tasks'][0]['required_checks'] = []
            data['tasks'][0]['analysis_basis'] = basis
            with self.assertRaises(EvolveError) as caught:
                propose(self.root, self.proposal(data))
            self.assertEqual(caught.exception.code, 'SYMPTOM_CHANGED')

    def test_unpresented_root_binding_and_ambiguous_multi_task_binding_are_rejected(self):
        request = self.proposal()
        request['input']['presentation']['document'].pop('analysis_basis', None)
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, request)
        self.assertEqual(caught.exception.code, 'PRESENTATION')
        data = copy.deepcopy(self.data)
        data['scope'].append('report.py')
        task = copy.deepcopy(data['tasks'][0])
        task.update(local_key='REPORT', scope=['report.py'])
        data['tasks'].append(task)
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, self.proposal(data))
        self.assertEqual(caught.exception.code, 'ANALYSIS_REFERENCE')
