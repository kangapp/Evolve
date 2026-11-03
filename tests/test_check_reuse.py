"""Explicit check reuse preserves original execution and current review facts."""
import json
import os
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.plans import propose
from evolve_core.verify import verify


class CheckReuseTests(WorkflowFixture):
    def configure(self, **options):
        check = {**self.checks[0], 'reuse': True, **options}
        data = {'checks': [check]}
        candidate = connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': data})
        connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': {**data,
            'expected_config_digest': candidate['expected_config_digest'],
            'presentation': {'source': 'controlled-explicit-reuse-candidate', 'text': candidate['candidate']}}})
        self.replan()

    def replan(self, **extra):
        text = 'Repair totals and explicitly reuse only matching recorded local checks.'
        data = {'title': 'Cacheable arithmetic checks', 'plan': text, 'completion': 'Independent literal examples pass.',
            'scope': ['total.py'], 'required_checks': ['unit'], 'acceptance': ['Preserve original literals.'],
            'presentation': {'source': 'controlled-reuse-plan', 'text': text}, **extra}
        self.plan = propose(self.root, {**self.identity(), 'authorization': self.auth, 'input': data})

    def dispatches(self):
        return self.rows("SELECT COUNT(*) n FROM events WHERE kind='check_dispatch_prepared'")[0]['n']

    def test_default_check_executes_again(self):
        implement(self.root, self.apply_request())
        before = self.dispatches()
        result = verify(self.root, self.verification_request())
        self.assertEqual(self.dispatches(), before + 1)
        self.assertTrue(result['checks'][0]['executed'])
        self.assertFalse(result['checks'][0]['reused'])

    def test_exact_check_is_referenced_without_fabricating_execution(self):
        self.configure()
        applied = implement(self.root, self.apply_request())
        original = self.rows('SELECT result_json FROM phase_runs WHERE id=?', (applied['run_id'],))[0]['result_json']
        before = self.dispatches()
        for _ in range(2):
            result = verify(self.root, self.verification_request())
            self.assertEqual(result['status'], 'passed')
            check = result['checks'][0]
            self.assertTrue(check['reused'])
            self.assertFalse(check['executed'])
            self.assertEqual(check['reuse_source']['run_id'], applied['run_id'])
            method = self.rows('SELECT method FROM evidence WHERE id=?', (check['evidence_id'],))[0]['method']
            self.assertEqual(method, 'argv-check-reuse')
        self.assertEqual(self.dispatches(), before)
        self.assertEqual(self.rows('SELECT result_json FROM phase_runs WHERE id=?', (applied['run_id'],))[0]['result_json'], original)

    def test_explicit_fresh_check_runs_and_becomes_new_origin(self):
        self.configure()
        implement(self.root, self.apply_request())
        request = self.verification_request()
        request['input']['fresh_checks'] = ['unit']
        before = self.dispatches()
        fresh = verify(self.root, request)
        self.assertEqual(self.dispatches(), before + 1)
        self.assertTrue(fresh['checks'][0]['executed'])
        reused = verify(self.root, self.verification_request())
        self.assertEqual(reused['checks'][0]['reuse_source']['run_id'], fresh['run_id'])

    def test_source_change_forces_actual_check(self):
        self.configure()
        implement(self.root, self.apply_request())
        (self.root / 'total.py').write_text('def total(values):\n    return 0\n')
        before = self.dispatches()
        result = verify(self.root, self.verification_request())
        self.assertEqual(self.dispatches(), before + 1)
        self.assertTrue(result['checks'][0]['executed'])
        self.assertEqual(result['checks'][0]['status'], 'failed')

    def test_environment_change_forces_actual_check(self):
        self.configure(environment_variables=['EVOLVE_FIXTURE_MODE'])
        with patch.dict(os.environ, {'EVOLVE_FIXTURE_MODE': 'original'}):
            implement(self.root, self.apply_request())
        with patch.dict(os.environ, {'EVOLVE_FIXTURE_MODE': 'changed'}):
            result = verify(self.root, self.verification_request())
        self.assertTrue(result['checks'][0]['executed'])

    def test_preflight_is_always_executed(self):
        self.configure(preflight=True)
        (self.root / 'total.py').write_text('def total(values):\n    return sum(values)\n')
        self.replan()
        implement(self.root, self.apply_request())
        before = self.dispatches()
        result = verify(self.root, self.verification_request())
        self.assertEqual(self.dispatches(), before + 1)
        self.assertTrue(result['checks'][0]['executed'])

    def test_preservation_pair_remains_actual_but_acceptance_can_reference_after(self):
        self.configure()
        (self.root / 'total.py').write_text('def total(values):\n    return sum(values)\n')
        self.replan(pre_refactor=True, preservation_checks=['unit'], preservation_inputs=['test_total.py'])
        before = self.dispatches()
        applied = implement(self.root, self.apply_request('def total(values):\n    value = 0\n    for item in values:\n        value += item\n    return value\n'))
        self.assertEqual(self.dispatches(), before + 2)
        self.assertEqual(applied['preservation']['status'], 'passed')
        self.assertTrue(applied['task_checks'][0]['executed'])
        result = verify(self.root, self.verification_request())
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['checks'][0]['reused'])

    def test_unknown_fresh_check_rejected_before_dispatch(self):
        self.configure()
        implement(self.root, self.apply_request())
        before = self.dispatches()
        request = self.verification_request()
        request['input']['fresh_checks'] = ['unknown']
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, request)
        self.assertEqual(caught.exception.code, 'INPUT')
        self.assertEqual(self.dispatches(), before)

    def test_latest_failure_prevents_falling_back_to_older_green(self):
        self.configure()
        implement(self.root, self.apply_request())
        original = (self.root / 'total.py').read_bytes()
        (self.root / 'total.py').write_text('def total(values):\n    return 0\n')
        failed = verify(self.root, self.verification_request())
        self.assertEqual(failed['checks'][0]['status'], 'failed')
        (self.root / 'total.py').write_bytes(original)
        before = self.dispatches()
        result = verify(self.root, self.verification_request())
        self.assertEqual(self.dispatches(), before + 1)
        self.assertTrue(result['checks'][0]['executed'])

    def test_input_policy_change_requires_fresh_execution(self):
        self.configure()
        implement(self.root, self.apply_request())
        data = {'generated_paths': ['scratch-output']}
        candidate = connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': data})
        connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': {**data,
            'expected_config_digest': candidate['expected_config_digest'],
            'presentation': {'source': 'actual-generated-policy-change', 'text': candidate['candidate']}}})
        result = verify(self.root, self.verification_request())
        self.assertTrue(result['checks'][0]['executed'])

    def test_changed_check_definition_requires_a_new_plan(self):
        self.configure()
        implement(self.root, self.apply_request())
        data = {'checks': [{**self.checks[0], 'reuse': True, 'timeout': 11}]}
        candidate = connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': data})
        connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': {**data,
            'expected_config_digest': candidate['expected_config_digest'],
            'presentation': {'source': 'actual-check-definition-change', 'text': candidate['candidate']}}})
        before = self.dispatches()
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, self.verification_request())
        self.assertEqual(caught.exception.code, 'CHECK_CONFIG')
        self.assertEqual(self.dispatches(), before)
