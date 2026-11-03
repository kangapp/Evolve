"""Semantic knowledge views close at the implementation cutoff, even without documents."""
import json

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.knowledge_impact import REVIEW_VIEWS, assess
from evolve_core.plans import propose
from evolve_core.verify import verify


class WorkKnowledgeReviewTests(WorkflowFixture):
    def review(self, result='unchanged', paths=None):
        return [{'views': list(REVIEW_VIEWS), 'result': result,
            'basis': 'Only restore the already specified arithmetic result; entry points, domain, rules, data, decisions, environment and requirements retain their meanings.',
            'source_paths': ['test_total.py'] if paths is None else paths}]

    def propose_review(self, review=None, impacts=None):
        text = 'Restore the specified arithmetic result and assess knowledge meanings.'
        return propose(self.root, {**self.identity(), 'authorization': self.auth, 'input': {
            'title': 'Reviewed arithmetic repair', 'plan': text, 'completion': 'Original literals pass.',
            'scope': ['total.py'], 'required_checks': ['unit'], 'acceptance': ['Original arithmetic literals pass.'],
            'knowledge_review': self.review() if review is None else review,
            **({'knowledge_impact': impacts} if impacts is not None else {}),
            'presentation': {'source': 'actual-reviewed-plan', 'text': text}}})

    def test_all_views_are_retained_and_archive_requires_actual_current_assessment(self):
        self.plan = self.propose_review()
        implement(self.root, self.apply_request())
        verified = verify(self.root, self.verification_request())
        self.assertEqual(verified['status'], 'passed')
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.request({'verification_id': verified['verification_id']}))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_INCOMPLETE')
        assessed = assess(self.root, self.request({'change_id': self.plan['change_id'],
            'revision_id': self.plan['revision_id'], 'observations': [], 'knowledge_review': self.review()}))
        self.assertEqual({view for item in assessed['knowledge_review'] for view in item['views']}, set(REVIEW_VIEWS))
        self.assertEqual(archive(self.root, self.request({'verification_id': verified['verification_id']}))['outcome'], 'archived')
        self.assertFalse((self.root / 'evolve/domain.md').exists())

    def test_missing_views_cannot_be_treated_as_unchanged(self):
        review = self.review()
        review[0]['views'].pop()
        before = self.rows('SELECT COUNT(*) n FROM changes')[0]['n']
        with self.assertRaises(EvolveError) as caught:
            self.propose_review(review)
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_REVIEW')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM changes')[0]['n'], before)

    def test_changed_view_requires_a_concrete_update_or_followup(self):
        with self.assertRaises(EvolveError) as caught:
            self.propose_review(self.review('changed'))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_REVIEW')

    def test_changed_conclusions_need_revision_instead_of_silent_reclassification(self):
        self.plan = self.propose_review()
        implement(self.root, self.apply_request())
        with self.assertRaises(EvolveError) as caught:
            assess(self.root, self.request({'change_id': self.plan['change_id'], 'revision_id': self.plan['revision_id'],
                'observations': [], 'knowledge_review': self.review('unknown')}))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_REVIEW')

    def test_legacy_plan_is_not_rewritten_with_fabricated_review(self):
        definition = json.loads(self.rows('SELECT definition_json FROM tasks WHERE id=?', (self.plan['task_id'],))[0]['definition_json'])
        self.assertNotIn('knowledge_review', definition)
        self.assertIn('不代表已调查所有业务含义', (self.root / 'evolve/changes' / self.plan['change_id'] / 'summary.md').read_text())
