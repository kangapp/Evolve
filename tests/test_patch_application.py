"""Approved same-file deltas retain scope and decisions across real applications."""
import json
import subprocess
import sys
import zipfile
import unittest
from unittest.mock import patch

import test_formal_application as formal_fixture
from evolve_core.errors import EvolveError
from evolve_core.formal import apply_knowledge, verify_knowledge
from evolve_core.knowledge_proposals import propose_knowledge, check_candidate, review_candidates
from evolve_core.package import digest
from evolve_core.reading import current_state
from evolve_core.recover import recover
from evolve_core.store import Store


class PatchApplicationTests(unittest.TestCase):
    def setUp(self):
        self.f = formal_fixture.FormalApplicationTests()
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root

    def candidate(self, before, after, target, *, dependencies=None, topic=None, task=None, ac_id=None):
        base = (self.root / 'terms.md').read_bytes()
        start = base.index(before.encode()) if before else len(base)
        content = base[:start] + after.encode() + base[start + len(before.encode()):]
        data = {'path': 'terms.md', 'expected_digest': digest(base), 'content': content.decode(),
            'topic': topic or target, 'reason': 'Apply only this independently declared formal meaning.',
            'presentation': {'source': 'controlled-exact-patch-presentation', 'text': content.decode()},
            'acceptance': [{'key': 'term', 'text': 'The declared exact text change satisfies its bounded meaning.'}],
            'edits': [{'start': start, 'end': start + len(before.encode()), 'before': before, 'after': after, 'semantic_target': target}],
            'dependencies': [self.f.ref(v) for v in dependencies or []]}
        if task:
            data['delivery'] = {'role': 'required', 'change_id': self.f.plan['change_id'], 'revision_id': self.f.plan['revision_id'],
                'task_id': task['id'], 'definition_digest': task['definition_digest'], 'acceptance_ids': [ac_id]}
        return propose_knowledge(self.root, self.f.request(data))

    def approve_batch(self, items, decisions=None):
        for item in items:
            check_candidate(self.root, self.f.request({'proposal': self.f.ref(item), 'observations': self.f.observations()}))
        result = review_candidates(self.root, self.f.request({'decisions': [
            {'proposal': self.f.ref(item), 'decision': selected, 'source': 'controlled-specific-batch-decision',
             'text': 'Decide this exact independently presented patch and base.', 'reason': 'Actual bounded content review.'}
            for item, selected in zip(items, decisions or ['approved'] * len(items))]}))
        return [row['decision_event_id'] for row in result['decisions']]

    def apply(self, item, approval, *, composed=True, required=False):
        request = self.f.application_request(item, approval, required)
        if composed:
            value = current_state(self.root, item['proposal_id'])['knowledge_proposals'][0]['effective_candidate']
            if not value.get('blocked') and value['chain']:
                request['input']['composition_review'] = {'base_digest': value['base_digest'], 'result_digest': value['result_digest'],
                    'semantic_targets': value['semantic_targets'], 'status': 'passed', 'observer': 'controlled-composed-content-reviewer',
                    'basis': 'Read the actual complete composed text, retained prior clauses and each distinct semantic target.'}
        return apply_knowledge(self.root, request)

    def required_pair(self):
        from evolve_core.plans import propose
        from evolve_core.structured import document
        data = {'complexity': 'complex', 'title': 'One formal file, two required meanings', 'plan': 'Apply and verify the definition before adding its independent numeric domain.',
            'completion': 'Both approved meanings are actually present and verified.', 'scope': ['terms.md'], 'required_checks': [],
            'acceptance': [{'key': 'A', 'text': 'Total means numeric sum.'}, {'key': 'B', 'text': 'Declared input domain is numeric.'}],
            'spec': {'problem': 'Formal definition and domain are incomplete.', 'goals': ['Deliver both formal meanings.'], 'non_goals': [],
                'behavior': ['Keep both independently approved meanings.'], 'constraints': ['Only the formal document.'], 'tradeoffs': [],
                'test_decisions': ['Inspect real content; no executable code test is needed.'], 'open_questions': []}, 'tasks': []}
        for key in ('A', 'B'):
            data['tasks'].append({'local_key': key, 'title': key, 'completion': data['acceptance'][len(data['tasks'])]['text'], 'validation': 'Read actual formal content.',
                'scope': ['terms.md'], 'required_checks': [], 'responsible_action': 'sync', 'acceptance': [key], 'context_paths': [], 'exclusions': [],
                'test_decision_refs': ['spec.test_decisions/0'], 'dependencies': [] if key == 'A' else [{'upstream_task': 'A', 'condition_kind': 'verification_passed', 'basis': 'Domain delivery follows the actual verified definition.'}]})
        data['presentation'] = {'source': 'controlled-required-same-file-plan', 'document': document(data)}
        self.f.plan = propose(self.root, self.f.request(data))
        tasks = self.f.plan['tasks']
        self.f.plan.update({'task_id': tasks[0]['id'], 'definition_digest': tasks[0]['definition_digest']})
        a = self.candidate('计数。', '数值之和。', 'definition', task=tasks[0], ac_id=self.f.plan['acceptance'][0]['id'])
        b = self.candidate('', '\n仅限数值输入。\n', 'domain', task=tasks[1], ac_id=self.f.plan['acceptance'][1]['id'])
        aa, bb = self.approve_batch([a, b]); self.apply(a, aa, required=True); self.f.verify_change()
        self.f.plan.update({'task_id': tasks[1]['id'], 'definition_digest': tasks[1]['definition_digest']})
        self.apply(b, bb, required=True)
        return a, b, tasks

    def test_required_same_file_tasks_keep_both_meanings_through_reverification_and_archive(self):
        from evolve_core.archive import archive
        a, b, tasks = self.required_pair()
        self.f.plan.update({'task_id': tasks[0]['id'], 'definition_digest': tasks[0]['definition_digest']})
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        whole = self.f.verify_change(whole=True)
        self.assertEqual(whole['status'], 'passed')
        self.assertEqual(archive(self.root, self.f.change_request({'verification_id': whole['verification_id']}, whole=True))['outcome'], 'archived')
        self.assertEqual([r['state'] for r in self.f.rows('SELECT state FROM tasks')], ['done', 'done'])

    def test_later_failure_on_first_same_file_effect_blocks_prior_whole_pass(self):
        from evolve_core.archive import archive
        a, _, _ = self.required_pair(); whole = self.f.verify_change(whole=True)
        self.assertEqual(whole['status'], 'passed')
        app = self.f.rows('SELECT id FROM spec_applications WHERE proposal_id=?', (a['proposal_id'],))[0]['id']
        verify_knowledge(self.root, self.f.request({'application_id': app, 'observations': self.f.observations('failed')}))
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.f.change_request({'verification_id': whole['verification_id']}, whole=True))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_VERIFICATION')

    def test_independent_same_base_patches_compose_without_overwrite_or_repeat_approval(self):
        first = self.candidate('计数。', '输入数值之和。', 'total-definition')
        second = self.candidate('', '\n仅限数值输入。\n', 'input-domain')
        approvals = self.approve_batch([first, second]); original = self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?', (first['proposal_id'],))[0]
        a = self.apply(first, approvals[0]); before = (self.root / 'terms.md').read_text()
        with self.assertRaises(EvolveError) as caught: self.apply(second, approvals[1], composed=False)
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_COMPOSITION'); self.assertEqual((self.root / 'terms.md').read_text(), before)
        b = self.apply(second, approvals[1]); body = (self.root / 'terms.md').read_text()
        self.assertIn('输入数值之和。', body); self.assertIn('仅限数值输入。', body)
        self.assertEqual(self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?', (first['proposal_id'],))[0], original)
        self.assertEqual(b['effect']['chain'], [a['application_id']]); self.assertNotEqual(b['actual_digest'], second['candidate_digest'])
        row = self.f.rows('SELECT * FROM spec_applications WHERE id=?', (b['application_id'],))[0]
        self.assertEqual(row['baseline_digest'], a['actual_digest'])
        self.assertEqual(row['result_digest'], digest(body.encode()))
        self.assertEqual(verify_knowledge(self.root, self.f.request({'application_id': a['application_id'], 'observations': self.f.observations()}))['status'], 'passed')
        view = current_state(self.root, first['proposal_id'])['knowledge_proposals'][0]['application']
        self.assertFalse(view['current_matches']); self.assertTrue(view['effect_state']['preserved'])

    def test_overlapping_ranges_stop_even_if_both_are_approved(self):
        a = self.candidate('计数。', '总和。', 'first-intent'); b = self.candidate('计数。', '数量。', 'second-intent')
        approvals = self.approve_batch([a, b]); self.apply(a, approvals[0]); before = (self.root / 'terms.md').read_bytes()
        with self.assertRaises(EvolveError) as caught: self.apply(b, approvals[1])
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_CONFLICT'); self.assertEqual((self.root / 'terms.md').read_bytes(), before)
        self.assertEqual(self.f.rows('SELECT state FROM knowledge_proposals WHERE id=?', (b['proposal_id'],))[0]['state'], 'approved')

    def test_same_semantic_target_stops_even_when_byte_ranges_are_disjoint(self):
        a = self.candidate('计数。', '总和。', 'shared-contract', topic='definition')
        b = self.candidate('', '\n新条件。\n', 'shared-contract', topic='constraint')
        approvals = self.approve_batch([a, b]); self.apply(a, approvals[0])
        with self.assertRaises(EvolveError) as caught: self.apply(b, approvals[1])
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_CONFLICT')

    def test_invalid_byte_ranges_and_undeclared_full_text_are_rejected_without_effects(self):
        base = (self.root / 'terms.md').read_bytes(); start = base.index('计数。'.encode())
        correct = {'start': start, 'end': start + len('计数。'.encode()), 'before': '计数。', 'after': '总和。', 'semantic_target': 'definition'}
        changed = base.decode().replace('计数。', '总和。')
        for edits, content in [([{**correct, 'start': start + 1}], changed), ([correct], base.decode() + '未声明内容。\n'),
                               ([correct, {**correct, 'semantic_target': 'other'}], changed)]:
            with self.assertRaises(EvolveError) as caught:
                propose_knowledge(self.root, self.f.request({'path': 'terms.md', 'expected_digest': digest(base), 'content': content,
                    'topic': 'invalid-patch', 'reason': 'Controlled malformed byte range.', 'presentation': {'source': 'controlled-malformed-input', 'text': content},
                    'acceptance': [{'key': 'term', 'text': 'Declared change only.'}], 'edits': edits}))
            self.assertEqual(caught.exception.code, 'KNOWLEDGE_PATCH')
        self.assertEqual((self.root / 'terms.md').read_bytes(), base)
        self.assertEqual(self.f.rows("SELECT id FROM phase_runs WHERE status='started'"), [])

    def test_composition_observation_is_invalid_after_another_approved_application(self):
        a = self.candidate('计数。', '总和。', 'definition'); b = self.candidate('', '\n数值输入。\n', 'domain')
        c = self.candidate('术语', '项目术语', 'heading')
        aa, bb, cc = self.approve_batch([a, b, c]); self.apply(a, aa)
        effect = current_state(self.root, b['proposal_id'])['knowledge_proposals'][0]['effective_candidate']
        request = self.f.application_request(b, bb); request['input']['composition_review'] = {'base_digest': effect['base_digest'], 'result_digest': effect['result_digest'],
            'semantic_targets': effect['semantic_targets'], 'status': 'passed', 'observer': 'controlled-old-composition-review', 'basis': 'Reviewed the prior exact composition.'}
        self.apply(c, cc); before = (self.root / 'terms.md').read_bytes()
        with self.assertRaises(EvolveError) as caught: apply_knowledge(self.root, request)
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_COMPOSITION'); self.assertEqual((self.root / 'terms.md').read_bytes(), before)
        self.apply(b, bb)
        body = (self.root / 'terms.md').read_text()
        self.assertIn('项目术语', body); self.assertIn('总和。', body); self.assertIn('数值输入。', body)

    def test_batch_membership_does_not_approve_or_apply_an_unselected_candidate(self):
        a = self.candidate('计数。', '总和。', 'definition'); b = self.candidate('', '\n数值输入。\n', 'domain')
        check_candidate(self.root, self.f.request({'proposal': self.f.ref(b), 'batch': [self.f.ref(a), self.f.ref(b)], 'observations': self.f.observations()}))
        bb = self.f.approve(b); self.apply(b, bb)
        self.assertIsNone(self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?', (a['proposal_id'],))[0]['approved_event_id'])
        self.assertIn('计数。', (self.root / 'terms.md').read_text()); self.assertIn('数值输入。', (self.root / 'terms.md').read_text())

    def test_unfinalized_formal_version_cannot_become_a_new_candidate_baseline(self):
        a = self.candidate('计数。', '总和。', 'definition'); approval = self.f.approve(a)
        finish = Store.finish
        def interrupted(store, run_id, *args, **kwargs):
            row = store.one('SELECT action,method FROM phase_runs WHERE id=?', (run_id,))
            if row['action'] == 'sync' and row['method'] == 'apply':
                raise EvolveError('NEEDS_RECOVERY', 'Controlled committed application without receipt', exit_code=4)
            return finish(store, run_id, *args, **kwargs)
        with patch.object(Store, 'finish', interrupted), self.assertRaises(EvolveError): self.apply(a, approval)
        with self.assertRaises(EvolveError) as caught: self.candidate('', '\n数值输入。\n', 'domain')
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_PENDING')

    def test_individual_approval_does_not_invent_a_related_batch(self):
        a = self.candidate('计数。', '总和。', 'definition'); b = self.candidate('', '\n数值输入。\n', 'domain')
        aa = self.f.approve(a); bb = self.f.approve(b); self.apply(a, aa)
        with self.assertRaises(EvolveError) as caught: self.apply(b, bb)
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_BATCH')

    def test_external_bytes_do_not_join_an_approved_application_chain(self):
        a = self.candidate('计数。', '总和。', 'definition'); b = self.candidate('', '\n数值输入。\n', 'domain')
        aa, bb = self.approve_batch([a, b]); self.apply(a, aa)
        (self.root / 'terms.md').write_text((self.root / 'terms.md').read_text() + '外部未知含义。\n')
        before = (self.root / 'terms.md').read_bytes()
        with self.assertRaises(EvolveError) as caught: self.apply(b, bb)
        self.assertEqual(caught.exception.code, 'FILE_CONFLICT'); self.assertEqual((self.root / 'terms.md').read_bytes(), before)

    def test_deferred_patch_can_be_decided_after_peer_application_without_reapproving_peer(self):
        a = self.candidate('计数。', '总和。', 'definition'); b = self.candidate('', '\n数值输入。\n', 'domain')
        aa, _ = self.approve_batch([a, b], ['approved', 'deferred']); self.apply(a, aa)
        result = review_candidates(self.root, self.f.request({'batch': [self.f.ref(a), self.f.ref(b)], 'decisions': [
            {'proposal': self.f.ref(b), 'decision': 'approved', 'source': 'controlled-later-specific-decision',
             'text': 'Approve only the unchanged deferred domain patch.', 'reason': 'Actual prior approved definition remains preserved.'}]}))
        self.apply(b, result['decisions'][0]['decision_event_id'])
        self.assertEqual(self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?', (a['proposal_id'],))[0]['approved_event_id'], aa)
        self.assertIn('总和。', (self.root / 'terms.md').read_text())

    def test_declared_dependency_must_be_actually_applied_before_patch(self):
        a = self.candidate('计数。', '总和。', 'definition'); b = self.candidate('', '\n数值输入。\n', 'domain', dependencies=[a])
        aa, bb = self.approve_batch([a, b])
        with self.assertRaises(EvolveError) as caught: self.apply(b, bb)
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_DEPENDENCY')
        self.apply(a, aa); self.apply(b, bb)
        self.assertIn('总和。', (self.root / 'terms.md').read_text())

    def test_add_remove_delta_and_later_scope_preservation_have_actual_effects(self):
        a = self.candidate('', '\n数值输入。\n', 'domain'); aa = self.f.approve(a); app = self.apply(a, aa)
        b = self.candidate('总额：计数。\n', '', 'old-clause'); bb = self.f.approve(b); self.apply(b, bb)
        self.assertEqual([r['kind'] for r in self.f.rows('SELECT kind FROM delta_items ORDER BY rowid')], ['add', 'remove'])
        self.assertNotIn('计数', (self.root / 'terms.md').read_text()); self.assertIn('数值输入。', (self.root / 'terms.md').read_text())
        self.assertEqual(verify_knowledge(self.root, self.f.request({'application_id': app['application_id'], 'observations': self.f.observations()}))['status'], 'passed')

    def test_actual_composed_file_commit_recovers_exact_original_effect(self):
        a = self.candidate('计数。', '总和。', 'definition'); b = self.candidate('', '\n数值输入。\n', 'domain')
        aa, bb = self.approve_batch([a, b]); self.apply(a, aa)
        effect = current_state(self.root, b['proposal_id'])['knowledge_proposals'][0]['effective_candidate']
        request = self.f.application_request(b, bb); request['input']['composition_review'] = {'base_digest': effect['base_digest'], 'result_digest': effect['result_digest'],
            'semantic_targets': effect['semantic_targets'], 'status': 'passed', 'observer': 'controlled-composition-review', 'basis': 'Actual composed text retains both approved scopes.'}
        code = """import os,json,sys
sys.path.insert(0,sys.argv[1])
from evolve_core import formal
def stop(*args,**kwargs): os._exit(55)
formal._commit_application=stop
formal.apply_knowledge(sys.argv[2],json.load(sys.stdin))
"""
        process = subprocess.run([sys.executable, '-B', '-c', code, str(formal_fixture.ROOT / 'runtime'), str(self.root)], input=json.dumps(request), text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, 55, process.stderr)
        before = (self.root / 'terms.md').read_bytes(); run = self.f.rows('SELECT id FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]['id']
        result = recover(self.root, self.f.request({'run_id': run}))
        self.assertFalse(result['business_commands_run']); self.assertEqual((self.root / 'terms.md').read_bytes(), before)
        self.assertEqual(len(self.f.rows('SELECT * FROM spec_applications')), 2)

    def test_preserved_alpha8_writer_refuses_patch_dependency_protocol_without_writes(self):
        package = self.root / 'old-package'
        with zipfile.ZipFile(formal_fixture.ROOT / 'tests/fixtures/application-package-alpha8.zip') as a: a.extractall(package)
        before = (self.root / 'evolve/history.db').read_bytes()
        process = subprocess.run([sys.executable, '-B', str(package / 'package/runtime/evolve.py'), '--project', str(self.root), 'sync', '--method', 'apply', '--request', '-'],
            input=json.dumps({'authorization': self.f.auth, 'input': {}}), text=True, capture_output=True, timeout=15)
        self.assertEqual(json.loads(process.stdout)['error']['code'], 'SCHEMA_VERSION'); self.assertEqual((self.root / 'evolve/history.db').read_bytes(), before)
