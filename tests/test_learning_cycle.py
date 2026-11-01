"""A real input-domain counterexample propagates without manufacturing authority."""
import json

from learning_cycle_fixture import LearningCycleFixture, IMPROVED, FINAL
from evolve_core.errors import EvolveError
from evolve_core.learning import learn
from evolve_core.reading import current_state


class LearningCycleTests(LearningCycleFixture):
    def test_actual_counterexample_to_check_fix_and_scoped_feedback(self):
        self.seed()
        self.counterexample()
        old_verifications = {r['id']: r for r in self.rows('SELECT * FROM verifications')}
        self.propose_check()
        self.implement_check()
        self.fix_and_archive()
        self.feedback_and_resume()
        self.assertTrue(all(self.rows('SELECT * FROM verifications WHERE id=?', (key,))[0] == row
                            for key, row in old_verifications.items()))
        self.assertEqual(len(self.rows('SELECT * FROM knowledge_proposals')), 2)
        self.assertEqual(len(self.rows('SELECT * FROM rule_bindings')), 1)

    def test_counterexample_reaches_rule_and_pending_plan_without_rewriting(self):
        self.seed()
        before = {r['id']: r for r in self.rows('SELECT * FROM verifications')}
        pending = self.rows('SELECT * FROM tasks WHERE change_id=?', (self.c['change_id'],))
        self.counterexample()
        self.assertEqual(((self.root / 'guide.md').read_bytes(), (self.root / 'guide.md').stat().st_mtime_ns), self.guide_after_seed)
        self.assertEqual(self.rows('SELECT * FROM tasks WHERE change_id=?', (self.c['change_id'],)), pending)
        self.assertTrue(all(self.rows('SELECT * FROM verifications WHERE id=?', (key,))[0] == row for key, row in before.items()))
        proposal = current_state(self.root, self.rule_ref['proposal_id'])['knowledge_proposals'][0]
        self.assertEqual(proposal['rule_state']['applicability'], 'needs_review')
        blocked = self.rows('SELECT items_json FROM verifications WHERE id=?',
            (self.rows('SELECT verification_id FROM spec_applications WHERE id=?', (self.rule_application['application_id'],))[0]['verification_id'],))[0]
        self.assertTrue(json.loads(blocked['items_json'])['current_matches_application'])
        self.assertIsNotNone(json.loads(blocked['items_json'])['implementation_basis_error'])
        self.assertEqual((self.root / 'guide.md').read_text(), FINAL)
        self.assertEqual(self.entry(self.old_experience)['applications'][0]['effect'], 'unknown')

    def test_old_actual_green_cannot_clear_a_new_input_domain_counterexample(self):
        self.seed()
        self.counterexample()
        entry = self.entry(self.old_experience)
        with self.assertRaises(EvolveError) as caught:
            learn(self.root, self.project_request({'kind': 'state', 'experience_ref': self.old_experience,
                'expected_state_ref': entry['state_ref'], 'state': 'active',
                'basis': 'Old list observations predate the actual iterator counterexample.', 'sources': [self.old_support],
                'reviewed_counterexamples': [self.counter_feedback['run_id']]}), method='review')
        self.assertEqual(caught.exception.code, 'LEARNING_REVIEW_REQUIRED')
        self.assertEqual(self.entry(self.old_experience)['state'], 'needs_review')

    def test_independent_guard_requires_real_extra_coverage_and_original_literals(self):
        original = self.run_check('guard')
        self.assertEqual(original.returncode, 1)
        self.assertEqual(json.loads(original.stdout)['variants']['iterator_zero']['returncode'], 0)
        (self.root / 'test_total.py').write_text(IMPROVED)
        improved = self.run_check('guard')
        self.assertEqual(improved.returncode, 0, improved.stdout + improved.stderr)
        result = json.loads(improved.stdout)
        self.assertEqual(result['variants']['correct']['returncode'], 0)
        self.assertTrue(all(result['variants'][name]['returncode'] != 0 for name in ('count', 'iterator_zero')))
        (self.root / 'test_total.py').write_text(IMPROVED.replace('total([2,3]),5', 'total([2,3]),2'))
        tampered = self.run_check('guard')
        self.assertEqual(tampered.returncode, 1)
        self.assertFalse(json.loads(tampered.stdout)['original_literals_preserved'])
        self.assertEqual(((self.root / 'guard.py').read_bytes(), (self.root / 'guard.py').stat().st_mtime_ns), self.original_guard)
