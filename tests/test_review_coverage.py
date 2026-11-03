"""Actual check coverage and observer modes remain distinct, plan-bound facts."""
from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
from evolve_core.plans import propose
from evolve_core.verify import verify


class ReviewCoverageTests(WorkflowFixture):
    def independent_plan(self):
        text = 'Restore the arithmetic result and obtain independent review.'
        self.plan = propose(self.root, {**self.identity(), 'authorization': self.auth, 'input': {
            'title': 'Independently reviewed arithmetic', 'plan': text, 'completion': 'Original literals pass.',
            'scope': ['total.py'], 'required_checks': ['unit'], 'acceptance': ['Original totals are preserved.'],
            'review_policy': 'independent', 'presentation': {'source': 'controlled-policy-plan', 'text': text}}})

    def test_acceptance_links_only_declared_checks_to_actual_evidence(self):
        implement(self.root, self.apply_request())
        request = self.verification_request()
        for review in request['input']['reviews']:
            review['mode'] = 'self'
        for item in request['input']['reviews'][0]['acceptance_results']:
            item['check_ids'] = ['unit']
        result = verify(self.root, request)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(all(item['mode'] == 'self' and item['independent'] is False for item in result['review_provenance']))
        for item in result['coverage']:
            self.assertEqual(item['checks'][0]['evidence_id'], result['checks'][0]['evidence_id'])
            self.assertEqual(item['checks'][0]['status'], 'passed')
            self.assertEqual(item['check_mapping'], 'declared')

    def test_legacy_observations_are_explicitly_not_recorded_instead_of_inferred_independent(self):
        implement(self.root, self.apply_request())
        result = verify(self.root, self.verification_request())
        self.assertTrue(all(item['mode'] == 'not_recorded' for item in result['review_provenance']))
        self.assertTrue(all(item['check_mapping'] == 'not_recorded' for item in result['coverage']))

    def test_independent_plan_rejects_self_review_before_check_dispatch(self):
        self.independent_plan()
        implement(self.root, self.apply_request())
        before = self.rows("SELECT COUNT(*) n FROM events WHERE kind='check_dispatch_prepared'")[0]['n']
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, self.verification_request())
        self.assertEqual(caught.exception.code, 'REVIEW_INDEPENDENCE_REQUIRED')
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='check_dispatch_prepared'")[0]['n'], before)

    def test_independence_metadata_requires_actual_source_and_basis(self):
        self.independent_plan()
        implement(self.root, self.apply_request())
        request = self.verification_request()
        for item in request['input']['reviews']:
            item['mode'] = 'independent'
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, request)
        self.assertEqual(caught.exception.code, 'REVIEW_REQUIRED')
        request = self.verification_request()
        for item in request['input']['reviews']:
            item.update(mode='independent', source='controlled-fixture-separate-observer-metadata',
                independence_basis='Controlled fixture metadata exercises the policy; actual Codex independence is a separate native acceptance gate.')
        self.assertEqual(verify(self.root, request)['status'], 'passed')

    def test_unknown_check_cannot_be_claimed_as_acceptance_coverage(self):
        implement(self.root, self.apply_request())
        request = self.verification_request()
        request['input']['reviews'][0]['acceptance_results'][0]['check_ids'] = ['not-registered']
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, request)
        self.assertEqual(caught.exception.code, 'ACCEPTANCE')
