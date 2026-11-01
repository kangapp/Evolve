"""Different Changes and owners retain exact same-file approvals and prerequisites."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_rule_owner as rule_fixture
import test_patch_application as patch_fixture
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.formal import apply_knowledge
from evolve_core.knowledge_proposals import check_candidate, review_candidates
from evolve_core.plans import propose
from evolve_core.reading import current_state
from evolve_core.structured import document


class CrossFormalTests(unittest.TestCase):
    def setUp(self):
        self.r = rule_fixture.RuleOwnerTests()
        self.r.setUp()
        self.addCleanup(self.r.doCleanups)
        self.f, self.root = self.r.f, self.r.root
        self.p = patch_fixture.PatchApplicationTests()
        self.p.f, self.p.root = self.f, self.root

    def plan(self, key, owner, text, references=None):
        data = {'complexity': 'complex', 'title': 'Independent formal ' + key, 'plan': text,
            'completion': text, 'scope': ['terms.md'], 'required_checks': [],
            'acceptance': [{'key': key, 'text': text}],
            'spec': {'problem': 'Deliver this explicitly approved formal meaning.', 'goals': [text], 'non_goals': [],
                'behavior': [text], 'constraints': ['Preserve other formal meanings and exact approvals.'], 'tradeoffs': [],
                'test_decisions': ['Read the actual composed content and the actual source work.'], 'open_questions': []},
            'tasks': [{'local_key': key, 'title': key, 'completion': text, 'validation': 'Inspect actual formal content.',
                'scope': ['terms.md'], 'required_checks': [], 'responsible_action': owner, 'acceptance': [key],
                'context_paths': [], 'exclusions': [], 'test_decision_refs': ['spec.test_decisions/0'],
                'dependencies': [], 'external_dependencies': references or []}]}
        data['presentation'] = {'source': 'controlled-cross-owner-spec', 'document': document(data)}
        result = propose(self.root, self.f.request(data))
        result.update(task_id=result['tasks'][0]['id'], definition_digest=result['tasks'][0]['definition_digest'])
        return result

    def prepare(self, condition='knowledge_applied'):
        self.a = self.plan('DOC', 'sync', 'Total means numeric sum.')
        reference = {'upstream_change_id': self.a['change_id'], 'upstream_task_id': self.a['task_id'],
            'required_revision_id': self.a['revision_id'], 'required_definition_digest': self.a['definition_digest'],
            'condition_kind': condition, 'basis': 'The independent review rule follows the concrete numeric definition.'}
        if condition == 'knowledge_applied':
            reference['condition_ref'] = 'terms.md'
        self.b = self.plan('RULE', 'learn', 'Review uses independent literal examples and states its bounded scope.', [reference])
        self.f.plan = self.a
        self.first = self.p.candidate('计数。', '数值之和。', 'sum-definition',
            task=self.a['tasks'][0], ac_id=self.a['acceptance'][0]['id'])
        self.f.plan = self.b
        self.second = self.r.candidate(required=True)
        batch = [self.f.ref(self.first), self.f.ref(self.second)]
        for item, basis in ((self.first, 'Read the exact numeric-sum definition candidate.'),
                            (self.second, 'Read the scoped literal-review rule, actual work sources and all known counterexamples.')):
            observations = [{'criterion_key': 'term', 'status': 'passed', 'observer': 'controlled-actual-content-reviewer', 'basis': basis}]
            check_candidate(self.root, self.f.request({'proposal': self.f.ref(item), 'batch': batch, 'observations': observations}))
        decisions = review_candidates(self.root, self.f.request({'batch': batch, 'decisions': [
            {'proposal': self.f.ref(item), 'decision': 'approved', 'source': 'controlled-specific-two-owner-decision',
             'text': 'Approve only this exact independent meaning and baseline.', 'reason': 'Read the full candidate and actual sources.'}
            for item in (self.first, self.second)]}))['decisions']
        self.approvals = [row['decision_event_id'] for row in decisions]

    def ready_b(self):
        return current_state(self.root, self.b['change_id'])['changes'][0]['tasks'][0]['readiness']

    def apply_b(self):
        self.f.plan = self.b
        effect = current_state(self.root, self.second['proposal_id'])['knowledge_proposals'][0]['effective_candidate']
        composition = {key: effect[key] for key in ('base_digest', 'result_digest', 'semantic_targets')}
        composition.update(status='passed', observer='controlled-actual-composed-content-reader',
                           basis='Read the whole composed text, preserving the numeric definition and the independently approved review rule.')
        return self.r.apply(self.second, self.approvals[1], required=True, composition_review=composition)

    def test_batch_approval_does_not_bypass_cross_change_application_condition(self):
        self.prepare()
        before = (self.root / 'terms.md').read_bytes()
        self.f.plan = self.b
        with self.assertRaises(EvolveError) as caught:
            self.r.apply(self.second, self.approvals[1], required=True)
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        self.assertEqual((self.root / 'terms.md').read_bytes(), before)
        self.f.plan = self.a
        applied = self.p.apply(self.first, self.approvals[0], required=True)
        self.assertTrue(self.ready_b()['ready'])
        actual = self.apply_b()
        self.assertIn(applied['application_id'], actual['effect']['chain'])
        self.assertIn('数值之和。', (self.root / 'terms.md').read_text())
        self.assertIn(rule_fixture.RULE, (self.root / 'terms.md').read_text())
        self.assertEqual(self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?',
            (self.second['proposal_id'],))[0]['approved_event_id'], self.approvals[1])

    def test_verified_formal_dependency_retains_both_owner_meanings(self):
        self.prepare('verification_passed')
        self.f.plan = self.a
        self.p.apply(self.first, self.approvals[0], required=True)
        self.assertFalse(self.ready_b()['ready'])
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        self.assertTrue(self.ready_b()['ready'])
        self.apply_b()
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        self.f.plan = self.a
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        self.assertFalse(self.ready_b()['revalidation_required'])
        self.f.plan = self.b
        self.assertEqual(self.f.verify_change()['status'], 'passed')

    def test_external_formal_edit_stops_only_related_b_and_keeps_approval(self):
        self.prepare()
        self.f.plan = self.a
        self.p.apply(self.first, self.approvals[0], required=True)
        foreign = (self.root / 'terms.md').read_text() + '\n外部未批准内容。\n'
        (self.root / 'terms.md').write_text(foreign)
        self.assertFalse(self.ready_b()['ready'])
        self.f.plan = self.b
        with self.assertRaises(EvolveError):
            self.r.apply(self.second, self.approvals[1], required=True)
        self.assertEqual((self.root / 'terms.md').read_text(), foreign)
        self.assertEqual(self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?',
            (self.second['proposal_id'],))[0]['approved_event_id'], self.approvals[1])

    def test_whole_acceptance_retains_first_owner_after_other_change_composes(self):
        self.prepare('verification_passed')
        self.f.plan = self.a
        self.p.apply(self.first, self.approvals[0], required=True)
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        original = self.f.rows('SELECT result_json FROM tasks WHERE id=?', (self.a['task_id'],))[0]['result_json']
        self.apply_b()
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        before = ((self.root / 'terms.md').read_bytes(), (self.root / 'terms.md').stat().st_mtime_ns)
        self.f.plan = self.a
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        whole = self.f.verify_change(whole=True)
        self.assertEqual(whole['status'], 'passed')
        self.assertEqual(archive(self.root, self.f.change_request({'verification_id': whole['verification_id']}, whole=True))['outcome'], 'archived')
        self.assertEqual(self.f.rows('SELECT result_json FROM tasks WHERE id=?', (self.a['task_id'],))[0]['result_json'], original)
        self.assertEqual(((self.root / 'terms.md').read_bytes(), (self.root / 'terms.md').stat().st_mtime_ns), before)
        foreign = before[0] + b'\nForeign unapproved content.\n'
        (self.root / 'terms.md').write_bytes(foreign)
        self.assertEqual(self.f.verify_change(whole=True)['status'], 'blocked')
        self.assertEqual(self.f.rows('SELECT state FROM changes WHERE id=?', (self.a['change_id'],))[0]['state'], 'archived')
        self.assertEqual((self.root / 'terms.md').read_bytes(), foreign)

    def test_real_exit_after_second_owner_write_recovers_the_original_preserving_chain(self):
        self.prepare()
        self.f.plan = self.a
        self.p.apply(self.first, self.approvals[0], required=True)
        self.f.plan = self.b
        effect = current_state(self.root, self.second['proposal_id'])['knowledge_proposals'][0]['effective_candidate']
        composition = {key: effect[key] for key in ('base_digest', 'result_digest', 'semantic_targets')}
        composition.update(status='passed', observer='controlled-actual-composed-content-reader',
                           basis='Read the actual composed definition and bounded rule before dispatch.')
        request = self.f.application_request(self.second, self.approvals[1], True)
        request['input'].update(stage='apply', composition_review=composition)
        code = '''import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core import formal
from evolve_core.learning import learn
actual=formal.install_files
def crash(*args,**kwargs):
    actual(*args,**kwargs)
    os._exit(28)
formal.install_files=crash
learn(sys.argv[2],json.loads(sys.argv[3]),method='promote')
'''
        runtime = Path(__file__).resolve().parents[1] / 'runtime'
        result = subprocess.run([sys.executable, '-B', '-c', code, str(runtime), str(self.root), json.dumps(request)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 28, result.stdout + result.stderr)
        before = ((self.root / 'terms.md').read_bytes(), (self.root / 'terms.md').stat().st_mtime_ns)
        pending = self.f.rows("SELECT id FROM phase_runs WHERE status='started'")[0]['id']
        from evolve_core.recover import recover
        recovered = recover(self.root, self.f.request({'run_id': pending}))
        self.assertEqual(recovered['outcome'], 'recovered_knowledge')
        self.assertEqual(((self.root / 'terms.md').read_bytes(), (self.root / 'terms.md').stat().st_mtime_ns), before)
        self.assertEqual(self.f.rows("SELECT count(*) AS n FROM spec_applications WHERE proposal_id=?",
            (self.second['proposal_id'],))[0]['n'], 1)

    def test_known_conflicting_approved_successor_is_rejected_before_file_write(self):
        self.prepare()
        self.f.plan = self.a
        self.p.apply(self.first, self.approvals[0], required=True)
        definition = json.loads(self.f.rows('SELECT definition_json FROM tasks WHERE id=?', (self.b['task_id'],))[0]['definition_json'])
        conflicting = self.plan('CONFLICT', 'sync', 'Replace the sum definition with another meaning.', definition['external_dependencies'])
        self.f.plan = conflicting
        candidate = self.p.candidate('数值之和。', '另一含义。', 'sum-definition',
            task=conflicting['tasks'][0], ac_id=conflicting['acceptance'][0]['id'])
        approval = self.f.approve(candidate)
        before = (self.root / 'terms.md').read_bytes()
        with self.assertRaises(EvolveError) as caught:
            self.p.apply(candidate, approval, required=True)
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        self.assertEqual((self.root / 'terms.md').read_bytes(), before)
        self.assertFalse(self.f.rows('SELECT * FROM resource_claims'))
        self.assertFalse(self.f.rows("SELECT * FROM phase_runs WHERE status='started'"))
        self.assertFalse(self.f.rows("SELECT * FROM operations WHERE state='needs_recovery'"))
