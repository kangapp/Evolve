"""Planning exposes input producers before writes; only actual decisions resolve them."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_structured_plans as fixtures
from evolve_core.errors import EvolveError
from evolve_core.plans import propose
from evolve_core.reading import current_state


class PlanningImpactsTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.StructuredPlanTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        self.data = copy.deepcopy(self.f.data)
        self.data['scope'].append('contract.md')
        self.data['tasks'][1]['scope'].append('contract.md')

    def test_unreviewed_producer_input_overlap_is_visible_and_blocks_dispatch(self):
        planned = propose(self.root, self.f.request(self.data))
        impact = planned['planning_impacts'][0]
        self.assertEqual((impact['producer'], impact['consumer'], impact['paths']), ('REPORT', 'SUM', ['contract.md']))
        self.assertTrue(impact['requires_review'])
        state = current_state(self.root, planned['change_id'])['changes'][0]
        self.assertFalse(state['tasks'][0]['readiness']['ready'])
        auth = {**self.f.auth, 'effect_kinds': ['project_records', 'business_files', 'checks'],
                'paths': ['total.py', 'report.py', 'contract.md']}
        before = (self.root / 'total.py').read_bytes()
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'runtime/evolve.py'),
            '--project', str(self.root), 'apply', planned['change_id'], '--request', '-'],
            input=json.dumps({'authorization': auth, 'input': {'task_key': 'SUM', 'files': []}}), capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'DEPENDENCY_NOT_READY')
        self.assertEqual((self.root / 'total.py').read_bytes(), before)

    def test_actual_dependency_consumes_produced_input_instead_of_freezing_old_bytes(self):
        self.data['tasks'][1]['dependencies'] = []
        self.data['tasks'][0]['dependencies'] = [{'upstream_task': 'REPORT', 'condition_kind': 'task_completed',
            'basis': 'The refactor checks consume the updated contract produced by REPORT.'}]
        planned = propose(self.root, self.f.request(self.data))
        self.assertEqual(planned['planning_impacts'][0]['resolution'], 'declared_dependency')
        state = current_state(self.root, planned['change_id'])['changes'][0]
        task = next(item for item in state['tasks'] if item['local_key'] == 'SUM')
        self.assertNotIn('contract.md', task['definition']['context'])
        self.assertIn('contract.md', task['definition']['dependency_inputs'])

    def test_aliased_input_is_compared_to_the_actual_output_target(self):
        (self.root / 'alias.md').symlink_to(self.root / 'contract.md')
        self.data['tasks'][0]['context_paths'] = ['alias.md']
        self.data['tasks'][1]['dependencies'] = []
        self.data['tasks'][0]['dependencies'] = [{'upstream_task': 'REPORT', 'condition_kind': 'task_completed',
            'basis': 'The alias resolves to the updated contract.'}]
        planned = propose(self.root, self.f.request(self.data))
        self.assertEqual(planned['planning_impacts'][0]['paths'], ['contract.md'])
        state = current_state(self.root, planned['change_id'])['changes'][0]
        self.assertNotIn('alias.md', state['tasks'][0]['definition']['context'])

    def test_missing_external_context_without_upstream_producer_is_rejected(self):
        self.data['tasks'][0]['context_paths'] = ['not-produced.md']
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, self.f.request(self.data))
        self.assertEqual(caught.exception.code, 'CONTEXT')
        self.assertEqual(self.f.rows('SELECT id FROM changes'), [])

    def test_transitive_consumer_can_declare_a_future_upstream_file(self):
        self.data['scope'] += ['future.py', 'summary.md']
        self.data['tasks'][0]['scope'].append('future.py')
        self.data['tasks'].append({'local_key': 'SUMMARY', 'title': 'Summarize the report',
            'completion': 'The summary refers to the produced source.', 'validation': 'Inspect the actual source and report.',
            'exclusions': [], 'scope': ['summary.md'], 'acceptance': ['report'], 'required_checks': [],
            'context_paths': ['future.py'], 'test_decision_refs': ['spec.test_decisions/0'],
            'dependencies': [{'upstream_task': 'REPORT', 'condition_kind': 'task_completed',
                              'basis': 'The summary consumes the completed report and its upstream source.'}]})
        planned = propose(self.root, self.f.request(self.data))
        task = next(item for item in current_state(self.root, planned['change_id'])['changes'][0]['tasks']
                    if item['local_key'] == 'SUMMARY')
        self.assertEqual(task['definition']['produced_context'], {'future.py': 'future.py'})
        self.assertFalse(task['readiness']['ready'])
        self.assertFalse((self.root / 'future.py').exists())

    def test_produced_context_alias_retarget_is_reported_before_dispatch(self):
        alias = self.root / 'alias.md'
        alias.symlink_to(self.root / 'contract.md')
        self.data['tasks'][0]['context_paths'] = ['alias.md']
        self.data['tasks'][1]['dependencies'] = []
        self.data['tasks'][0]['dependencies'] = [{'upstream_task': 'REPORT', 'condition_kind': 'task_completed',
            'basis': 'The consumer uses the produced contract through its existing alias.'}]
        planned = propose(self.root, self.f.request(self.data))
        alias.unlink()
        alias.symlink_to(self.root / 'total.py')
        task = next(item for item in current_state(self.root, planned['change_id'])['changes'][0]['tasks']
                    if item['local_key'] == 'SUM')
        self.assertIn('context_target_changed', {item['kind'] for item in task['readiness']['unmet']})

    def test_independent_decision_is_part_of_the_exact_presented_document(self):
        self.data['impact_resolutions'] = [{'producer': 'REPORT', 'consumer': 'SUM', 'paths': ['contract.md'],
            'decision': 'independent', 'basis': 'The consumer uses the original contract before REPORT; unchanged-input guards remain applicable.'}]
        planned = propose(self.root, self.f.request(self.data))
        self.assertFalse(planned['planning_impacts'][0]['requires_review'])
        state = current_state(self.root, planned['change_id'])['changes'][0]
        self.assertEqual(state['plan']['document']['impact_resolutions'], self.data['impact_resolutions'])

    def test_fictitious_resolution_is_rejected_before_recording(self):
        self.data['impact_resolutions'] = [{'producer': 'REPORT', 'consumer': 'SUM', 'paths': ['other.md'],
            'decision': 'independent', 'basis': 'Does not identify the actual overlap.'}]
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, self.f.request(self.data))
        self.assertEqual(caught.exception.code, 'PLAN_IMPACT')
        self.assertEqual(self.f.rows('SELECT id FROM changes'), [])

    def test_new_short_plan_observes_existing_consumers_without_creating_dependencies(self):
        first = propose(self.root, self.f.request())
        text = 'Update the contract after reviewing existing consumers.'
        planned = propose(self.root, {**{k: self.f.project[k] for k in ('project_id',)},
            'expected_workspace_epoch': self.f.project['workspace_epoch'], 'authorization': self.f.auth,
            'input': {'title': 'Contract update', 'plan': text, 'completion': 'The contract is accurate.',
                'scope': ['contract.md'], 'required_checks': [], 'acceptance': ['Contract meaning is accurate.'],
                'presentation': {'source': 'controlled-short-plan', 'text': text}}})
        impact = planned['workspace_impacts'][0]
        self.assertEqual(impact['change_id'], first['change_id'])
        self.assertTrue(impact['requires_semantic_review'])
        self.assertFalse(impact['automatic_dependency'])
