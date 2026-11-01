"""Initial formal owner uses the same candidate, decision, journal and Task gates."""
import json
import subprocess
import sys
import unittest
import zipfile

import test_formal_application as fixture
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.formal import apply_knowledge, verify_knowledge
from evolve_core.knowledge import propose_baseline, apply_baseline
from evolve_core.knowledge_proposals import propose_knowledge
from evolve_core.knowledge_proposals import check_candidate, review_candidates
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.reading import current_state
from evolve_core.recover import recover


class InitialDocumentOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.FormalApplicationTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root

    def plan(self, path='guide.md'):
        text = 'Create this exact initial formal guide through init, then inspect its actual content.'
        self.f.plan = propose(self.root, self.f.request({'title': '初次正式文档', 'plan': text, 'completion': 'The actual formal guide has its declared meaning.',
            'scope': [path], 'acceptance': ['The actual guide states the numeric sum meaning.'], 'required_checks': [], 'responsible_action': 'init',
            'presentation': {'source': 'controlled-initial-document-plan', 'text': text}}))

    def candidate(self, *, path='guide.md', required=False, edits=None, content=None, topic='initial-guide'):
        value = content or fixture.CANDIDATE
        data = {'path': path, 'expected_digest': digest((self.root / path).read_bytes()) if (self.root / path).is_file() else None,
            'content': value, 'topic': topic, 'reason': 'Establish the exact first approved formal meaning.',
            'presentation': {'source': 'controlled-full-initial-guide', 'text': value}, 'acceptance': [{'key': 'term', 'text': 'The exact guide defines numeric sum.'}]}
        if required:
            data['delivery'] = {'role': 'required', **{k: self.f.plan[k] for k in ('change_id', 'revision_id', 'task_id', 'definition_digest')},
                'acceptance_ids': [self.f.plan['acceptance'][0]['id']]}
        if edits is not None: data['edits'] = edits
        return propose_baseline(self.root, self.f.request(data))

    def apply(self, item, approval, required=False):
        return apply_baseline(self.root, self.f.application_request(item, approval, required))

    def test_new_file_required_initial_document_uses_actual_application_and_verification(self):
        self.plan(); item = self.candidate(required=True)
        self.assertFalse((self.root / 'guide.md').exists())
        approval = self.f.approve(item); self.assertFalse((self.root / 'guide.md').exists())
        result = self.apply(item, approval, required=True)
        self.assertEqual((self.root / 'guide.md').read_text(), fixture.CANDIDATE)
        app = self.f.rows('SELECT * FROM spec_applications')[0]
        self.assertIsNone(app['baseline_digest'])
        self.assertEqual(self.f.rows('SELECT state FROM tasks')[0]['state'], 'done')
        self.assertEqual(result['overall_verification'], 'not_run')
        with self.assertRaises(EvolveError) as caught: archive(self.root, self.f.change_request({'verification_id': 'not-yet-applied-ver'}))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_VERIFICATION')
        verified = self.f.verify_change(); self.assertEqual(verified['status'], 'passed')
        self.assertEqual(archive(self.root, self.f.change_request({'verification_id': verified['verification_id']}))['outcome'], 'archived')
        run = self.f.rows('SELECT action,method,owner_skill FROM phase_runs WHERE id=?', (result['run_id'],))[0]
        self.assertEqual(run, {'action': 'init', 'method': 'baseline.apply', 'owner_skill': 'evolve-init'})

    def test_sync_cannot_write_an_init_owned_candidate(self):
        item = self.candidate(); approval = self.f.approve(item)
        with self.assertRaises(EvolveError) as caught: apply_knowledge(self.root, self.f.application_request(item, approval))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_OWNER'); self.assertFalse((self.root / 'guide.md').exists())

    def test_legacy_inline_approval_cannot_bypass_typed_initial_content_check(self):
        item = self.candidate()
        with self.assertRaises(EvolveError) as caught:
            apply_baseline(self.root, self.f.request({'proposal_id': item['proposal_id'], 'approval': {
                **{k: item[k] for k in ('proposal_version', 'candidate_digest', 'expected_digest')},
                'source': 'controlled-inline-approval-attempt', 'text': 'Approve this exact candidate.'}}))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_APPROVAL'); self.assertFalse((self.root / 'guide.md').exists())

    def test_stale_legacy_initial_candidate_cannot_revise_an_unchanged_registered_baseline(self):
        (self.root / 'guide.md').write_text(fixture.CANDIDATE)
        old_text = fixture.CANDIDATE + '\n旧的初次候选附带说明。\n'
        old = propose_baseline(self.root, self.f.request({'path': 'guide.md', 'expected_digest': digest(fixture.CANDIDATE.encode()),
            'content': old_text, 'presentation': {'source': 'controlled-earlier-legacy-candidate', 'text': old_text}}))
        current = self.candidate(); approval = self.f.approve(current); self.apply(current, approval)
        with self.assertRaises(EvolveError) as caught:
            apply_baseline(self.root, self.f.request({'proposal_id': old['proposal_id'], 'approval': {
                **{k: old[k] for k in ('proposal_version', 'candidate_digest', 'expected_digest')},
                'source': 'controlled-stale-initial-approval', 'text': 'Approve this older initial candidate.'}}))
        self.assertEqual(caught.exception.code, 'BASELINE_EXISTS')
        self.assertEqual((self.root / 'guide.md').read_text(), fixture.CANDIDATE)

    def test_second_initial_candidate_cannot_overwrite_an_already_established_baseline(self):
        a = self.candidate(); b = self.candidate(content=fixture.CANDIDATE + '\nInput domain.\n')
        # A later version replaces the first; only the new specific candidate may be approved.
        with self.assertRaises(EvolveError): self.f.approve(a)
        approval = self.f.approve(b); self.apply(b, approval)
        with self.assertRaises(EvolveError) as caught: self.candidate(content='Different initial meaning.\n')
        self.assertEqual(caught.exception.code, 'BASELINE_EXISTS')

    def test_existing_unmapped_document_can_be_registered_without_rewriting_its_bytes(self):
        (self.root / 'guide.md').write_text(fixture.CANDIDATE)
        before = (self.root / 'guide.md').read_bytes(); item = self.candidate(); approval = self.f.approve(item)
        result = self.apply(item, approval)
        self.assertEqual((self.root / 'guide.md').read_bytes(), before)
        self.assertEqual(verify_knowledge(self.root, self.f.request({'application_id': result['application_id'], 'observations': self.f.observations()}))['status'], 'passed')
        self.assertEqual(self.f.rows('SELECT kind FROM delta_items')[0]['kind'], 'add')

    def test_independently_approved_initial_candidates_do_not_overwrite_each_other(self):
        a = self.candidate(topic='initial-a'); b = self.candidate(topic='initial-b', content=fixture.CANDIDATE + '\nDistinct candidate.\n')
        aa = self.f.approve(a); bb = self.f.approve(b); self.apply(a, aa)
        before = (self.root / 'guide.md').read_bytes()
        with self.assertRaises(EvolveError) as caught: self.apply(b, bb)
        self.assertEqual(caught.exception.code, 'BASELINE_EXISTS'); self.assertEqual((self.root / 'guide.md').read_bytes(), before)
        self.assertEqual(len(self.f.rows('SELECT * FROM spec_applications')), 1)

    def test_legacy_presentation_cannot_impersonate_common_owner_metadata(self):
        propose_baseline(self.root, self.f.request({'path': 'guide.md', 'expected_digest': None, 'content': fixture.CANDIDATE,
            'presentation': {'source': 'controlled-legacy-extra-fields', 'text': fixture.CANDIDATE, 'format': 'knowledge-proposal-v2',
                'code': 'KP-fake', 'base_digest': digest(b''), 'formal_version_id': None}}))
        self.assertEqual(current_state(self.root)['knowledge_proposals'], [])

    def test_required_initial_and_sync_tasks_finish_one_shared_document_through_actual_owners(self):
        original = '# 术语\n\n总额：计数。\n'; (self.root / 'guide.md').write_text(original)
        data = {'complexity': 'complex', 'title': 'Initial baseline and independent domain', 'plan': 'Init establishes and verifies the sum meaning, then sync adds its independent domain.',
            'completion': 'Both actual formal meanings are delivered and accepted.', 'scope': ['guide.md'], 'required_checks': [],
            'acceptance': [{'key': 'INIT', 'text': 'Total means numeric sum.'}, {'key': 'SYNC', 'text': 'Input domain is numeric.'}],
            'spec': {'problem': 'No formal baseline or input-domain statement.', 'goals': ['Deliver the actual guide.'], 'non_goals': [],
                'behavior': ['Keep both specifically approved meanings.'], 'constraints': ['Each actual owner writes its declared output.'], 'tradeoffs': [],
                'test_decisions': ['Read actual full text, without code-test claims.'], 'open_questions': []}, 'tasks': []}
        for key, owner in [('INIT', 'init'), ('SYNC', 'sync')]:
            data['tasks'].append({'local_key': key, 'title': key, 'completion': data['acceptance'][len(data['tasks'])]['text'], 'validation': 'Read actual guide.',
                'scope': ['guide.md'], 'required_checks': [], 'responsible_action': owner, 'acceptance': [key], 'context_paths': [], 'exclusions': [],
                'test_decision_refs': ['spec.test_decisions/0'], 'dependencies': [] if key == 'INIT' else [{'upstream_task': 'INIT', 'condition_kind': 'verification_passed', 'basis': 'The initial meaning needs actual acceptance first.'}]})
        from evolve_core.structured import document
        data['presentation'] = {'source': 'controlled-complete-cross-owner-plan', 'document': document(data)}
        self.f.plan = propose(self.root, self.f.request(data)); tasks = self.f.plan['tasks']
        self.f.plan.update({'task_id': tasks[0]['id'], 'definition_digest': tasks[0]['definition_digest']})
        start = original.encode().index('计数。'.encode()); text = original.replace('计数。', '数值之和。')
        first = self.candidate(required=True, content=text, edits=[{'start': start, 'end': start + len('计数。'.encode()), 'before': '计数。', 'after': '数值之和。', 'semantic_target': 'definition'}])
        approval = self.f.approve(first); initial = self.apply(first, approval, True)
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        base = (self.root / 'guide.md').read_bytes(); content = base.decode() + '\n仅限数值输入。\n'
        second = propose_knowledge(self.root, self.f.request({'path': 'guide.md', 'content': content, 'expected_digest': digest(base), 'topic': 'domain', 'reason': 'Add only the independent domain.',
            'presentation': {'source': 'controlled-full-next-owner-candidate', 'text': content}, 'acceptance': [{'key': 'term', 'text': 'Input domain is numeric.'}],
            'edits': [{'start': len(base), 'end': len(base), 'before': '', 'after': '\n仅限数值输入。\n', 'semantic_target': 'domain'}],
            'dependencies': [self.f.ref(first)], 'delivery': {'role': 'required', 'change_id': self.f.plan['change_id'], 'revision_id': self.f.plan['revision_id'],
                'task_id': tasks[1]['id'], 'definition_digest': tasks[1]['definition_digest'], 'acceptance_ids': [self.f.plan['acceptance'][1]['id']]}}))
        check_candidate(self.root, self.f.request({'proposal': self.f.ref(second), 'observations': self.f.observations()}))
        decision = review_candidates(self.root, self.f.request({'batch': [self.f.ref(first), self.f.ref(second)], 'decisions': [
            {'proposal': self.f.ref(second), 'decision': 'approved', 'source': 'controlled-new-owner-only-approval', 'text': 'Approve only the new independent domain.', 'reason': 'Initial meaning remains approved.'}]}))
        self.f.plan.update({'task_id': tasks[1]['id'], 'definition_digest': tasks[1]['definition_digest']})
        apply_knowledge(self.root, self.f.application_request(second, decision['decisions'][0]['decision_event_id'], True))
        self.f.plan.update({'task_id': tasks[0]['id'], 'definition_digest': tasks[0]['definition_digest']})
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        whole = self.f.verify_change(whole=True); self.assertEqual(whole['status'], 'passed')
        self.assertEqual(archive(self.root, self.f.change_request({'verification_id': whole['verification_id']}, whole=True))['outcome'], 'archived')
        self.assertEqual(self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?', (first['proposal_id'],))[0]['approved_event_id'], approval)
        result = json.loads(self.f.rows('SELECT result_json FROM tasks WHERE id=?', (tasks[0]['id'],))[0]['result_json'])
        self.assertEqual(result['implementation_source'], 'owner:init')
        self.assertEqual((self.root / 'guide.md').read_text(), content)
        self.assertEqual(self.f.rows('SELECT source_run_id FROM spec_applications WHERE id=?', (initial['application_id'],))[0]['source_run_id'], initial['run_id'])

    def test_real_initial_candidate_metadata_commit_recovers_without_new_candidate_or_file(self):
        request = self.f.request({'path': 'guide.md', 'expected_digest': None, 'content': fixture.CANDIDATE, 'topic': 'initial-guide', 'reason': 'Initial formal meaning.',
            'presentation': {'source': 'controlled-initial-candidate', 'text': fixture.CANDIDATE}, 'acceptance': [{'key': 'term', 'text': 'Numeric sum meaning.'}]})
        code = """import os,json,sys
sys.path.insert(0,sys.argv[1])
from evolve_core.knowledge import propose_baseline
from evolve_core.store import Store
original=Store.finish
def finish(self,run_id,*args,**kwargs):
 row=self.one('SELECT action,method FROM phase_runs WHERE id=?',(run_id,))
 if row['action']=='init' and row['method']=='baseline.propose': os._exit(57)
 return original(self,run_id,*args,**kwargs)
Store.finish=finish
propose_baseline(sys.argv[2],json.load(sys.stdin))
"""
        process = subprocess.run([sys.executable, '-B', '-c', code, str(fixture.ROOT / 'runtime'), str(self.root)], input=json.dumps(request), text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, 57, process.stderr)
        item = self.f.rows("SELECT * FROM knowledge_proposals WHERE target_path='guide.md'")[0]
        self.assertTrue(current_state(self.root, item['id'])['knowledge_proposals'][0]['source_pending'])
        result = recover(self.root, self.f.request({'run_id': item['created_run_id']})); self.assertTrue(result['original_facts_committed'])
        self.assertFalse((self.root / 'guide.md').exists()); self.assertEqual(len(self.f.rows("SELECT * FROM knowledge_proposals WHERE target_path='guide.md'")), 1)
        self.assertFalse(current_state(self.root, item['id'])['knowledge_proposals'][0]['source_pending'])

    def test_init_then_sync_file_history_preserves_narrow_initial_meaning(self):
        original = '# 术语\n\n总额：计数。\n'
        (self.root / 'guide.md').write_text(original); start = original.encode().index('计数。'.encode())
        first_text = original.replace('计数。', '数值之和。')
        item = self.candidate(content=first_text, edits=[{'start': start, 'end': start + len('计数。'.encode()),
            'before': '计数。', 'after': '数值之和。', 'semantic_target': 'definition'}])
        approval = self.f.approve(item); first = self.apply(item, approval)
        base = (self.root / 'guide.md').read_bytes(); content = base.decode() + '\n仅限数值输入。\n'
        second = propose_knowledge(self.root, self.f.request({'path': 'guide.md', 'expected_digest': digest(base), 'content': content,
            'topic': 'domain', 'reason': 'Add only the independent input domain.', 'presentation': {'source': 'controlled-next-owner-content', 'text': content},
            'acceptance': [{'key': 'term', 'text': 'Input domain is numeric.'}],
            'edits': [{'start': len(base), 'end': len(base), 'before': '', 'after': '\n仅限数值输入。\n', 'semantic_target': 'domain'}]}))
        second_approval = self.f.approve(second); apply_knowledge(self.root, self.f.application_request(second, second_approval))
        self.assertEqual(verify_knowledge(self.root, self.f.request({'application_id': first['application_id'], 'observations': self.f.observations()}))['status'], 'passed')
        view = current_state(self.root, item['proposal_id'])['knowledge_proposals'][0]
        self.assertEqual(view['owner_skill'], 'evolve-init'); self.assertTrue(view['application']['effect_state']['preserved'])
        self.assertEqual(self.f.rows('SELECT owner_skill FROM knowledge_proposals WHERE id IN (?,?) ORDER BY rowid', (item['proposal_id'], second['proposal_id'])),
            [{'owner_skill': 'evolve-init'}, {'owner_skill': 'evolve-archive'}])

    def test_real_initial_file_commit_recovers_through_common_application_path(self):
        self.plan(); item = self.candidate(required=True); approval = self.f.approve(item); request = self.f.application_request(item, approval, True)
        code = """import os,json,sys
sys.path.insert(0,sys.argv[1])
from evolve_core import formal
from evolve_core.knowledge import apply_baseline
def stop(*args,**kwargs): os._exit(56)
formal._commit_application=stop
apply_baseline(sys.argv[2],json.load(sys.stdin))
"""
        process = subprocess.run([sys.executable, '-B', '-c', code, str(fixture.ROOT / 'runtime'), str(self.root)], input=json.dumps(request), text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, 56, process.stderr)
        run = self.f.rows('SELECT id FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]['id']
        before = (self.root / 'guide.md').read_bytes(); recovered = recover(self.root, self.f.request({'run_id': run}))
        self.assertFalse(recovered['business_commands_run']); self.assertEqual((self.root / 'guide.md').read_bytes(), before)
        self.assertEqual(self.f.verify_change()['status'], 'passed')
        self.assertEqual(len(self.f.rows('SELECT * FROM spec_applications')), 1)

    def test_preserved_alpha9_writer_rejects_required_init_protocol_without_writes(self):
        package = self.root / 'old-alpha9'
        with zipfile.ZipFile(fixture.ROOT / 'docs/evidence/imp007/patch-package-alpha9.zip') as a: a.extractall(package)
        before = (self.root / 'evolve/history.db').read_bytes()
        result = subprocess.run([sys.executable, '-B', str(package / 'package/runtime/evolve.py'), '--project', str(self.root), 'init', '--method', 'baseline.apply', '--request', '-'],
            input=json.dumps({'authorization': self.f.auth, 'input': {}}), text=True, capture_output=True, timeout=15)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'SCHEMA_VERSION')
        self.assertEqual((self.root / 'evolve/history.db').read_bytes(), before)
