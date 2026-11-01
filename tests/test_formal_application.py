"""Actual formal target applications, required document Tasks and process recovery."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'runtime'))
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.formal import apply_knowledge, verify_knowledge
from evolve_core.knowledge import apply_baseline, propose_baseline
from evolve_core.knowledge_proposals import check_candidate, propose_knowledge, review_candidates
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.reading import current_state
from evolve_core.recover import recover
from evolve_core.verify import verify
from evolve_core.archive import archive
from evolve_core.apply import implement
from evolve_core.work import fingerprint
from evolve_core.store import Store

BASE = '# 术语\n\n总额：计数。\n'
CANDIDATE = '# 术语\n\n总额：输入数值之和。\n'


class FormalApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-formal-application-')
        self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name).resolve()
        self.auth = {'source': 'controlled-formal-application-fixture', 'text': 'Apply only the exact approved temporary documents and inspect actual results.',
                     'effect_kinds': ['project_records', 'knowledge'], 'paths': ['terms.md', 'guide.md', 'evolve/project.md']}
        self.project = connect(self.root, {'authorization': self.auth, 'input': {}})
        self.baseline('terms.md'); self.plan = None

    def request(self, data):
        return {'request_id': str(uuid.uuid4()), 'project_id': self.project['project_id'],
                'expected_workspace_epoch': self.project['workspace_epoch'], 'authorization': copy.deepcopy(self.auth), 'input': data}

    def rows(self, sql, args=()):
        with sqlite3.connect(self.root / 'evolve/history.db') as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute(sql, args)]

    def baseline(self, path):
        item = propose_baseline(self.root, self.request({'path': path, 'content': BASE, 'expected_digest': None,
            'presentation': {'source': 'controlled-baseline', 'text': BASE}}))
        apply_baseline(self.root, self.request({'proposal_id': item['proposal_id'], 'approval': {
            **{k: item[k] for k in ('proposal_version', 'candidate_digest', 'expected_digest')},
            'source': 'controlled-exact-baseline', 'text': 'Approve this actual temporary baseline.'}}))

    def document_plan(self, paths=None):
        text = 'Correct only the declared formal definition through sync and inspect the applied wording.'
        self.plan = propose(self.root, self.request({'title': '修订正式术语', 'plan': text, 'completion': '正式总额定义表达数值之和。',
            'scope': paths or ['terms.md'], 'required_checks': [], 'responsible_action': 'sync',
            'acceptance': ['正式总额定义表达输入数值之和。'], 'presentation': {'source': 'controlled-document-plan', 'text': text}}))
        return self.plan

    def proposal(self, path='terms.md', content=CANDIDATE, required=False, delivery=None, basis=None):
        data = {'path': path, 'expected_digest': digest((self.root / path).read_bytes()), 'content': content,
            'presentation': {'source': 'controlled-presented-document', 'text': content}, 'topic': '总额定义',
            'reason': 'Align the actual formal term with its declared meaning.', 'acceptance': [{'key': 'term', 'text': '总额表达数值之和。'}]}
        if required:
            data['delivery'] = {'role': 'required', **{k: self.plan[k] for k in ('change_id', 'revision_id', 'task_id', 'definition_digest')},
                                'acceptance_ids': [self.plan['acceptance'][0]['id']]}
        elif delivery:
            data['delivery'] = delivery
        if basis:
            data['implementation_basis'] = basis
        return propose_knowledge(self.root, self.request(data))

    def ref(self, item):
        return {k: item[k] for k in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}

    def observations(self, status='passed'):
        return [{'criterion_key': 'term', 'status': status, 'observer': 'controlled-content-observer',
                 'basis': 'Read the exact UTF-8 wording against the declared numeric-sum condition.'}]

    def approve(self, item):
        check_candidate(self.root, self.request({'proposal': self.ref(item), 'observations': self.observations()}))
        result = review_candidates(self.root, self.request({'decisions': [{'proposal': self.ref(item), 'decision': 'approved',
            'source': 'controlled-exact-decision', 'text': 'Approve this presented full text and baseline.', 'reason': 'Actual content inspection.'}]}))
        return result['decisions'][0]['decision_event_id']

    def change_request(self, data, whole=False):
        change = self.rows('SELECT * FROM changes WHERE id=?', (self.plan['change_id'],))[0]
        tasks = self.rows('SELECT * FROM tasks WHERE change_id=? AND revision_id=?', (change['id'], change['current_revision']))
        task = next((t for t in tasks if t['id'] == data.get('task_id', self.plan['task_id'])), tasks[0])
        revision = self.rows('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],))[0]
        result = self.request({**data, 'change_id': change['id'], 'revision_id': change['current_revision'],
            'definition_digest': revision['definition_digest'] if whole else task['definition_digest']})
        if change['complexity'] == 'complex':
            result['input']['task_id'] = None if whole else task['id']
            result['expected_versions'] = {'change': change['row_version'], 'tasks': {t['id']: t['row_version'] for t in tasks}}
        else:
            result['expected_versions'] = {'change': change['row_version'], 'task': task['row_version']}
        return result

    def application_request(self, item, approval, required=False):
        data = {'proposal': self.ref(item), 'approved_event_id': approval}
        if required:
            data['accepted_plan_digest'] = self.plan['plan_digest']
            return self.change_request(data)
        return self.request(data)

    def verify_change(self, *, finding=None, whole=False):
        request = self.change_request({}, whole)
        task = self.rows('SELECT * FROM tasks WHERE id=?', (self.plan['task_id'],))[0]
        definition = json.loads(task['definition_json'])
        if whole:
            from evolve_core.structured import whole_definition
            with sqlite3.connect(self.root / 'evolve/history.db') as connection:
                connection.row_factory = sqlite3.Row
                revision = connection.execute('SELECT * FROM plan_revisions WHERE id=?', (request['input']['revision_id'],)).fetchone()
                peers = connection.execute('SELECT * FROM tasks WHERE revision_id=?', (revision['id'],)).fetchall()
                definition = whole_definition(revision, peers)
        snapshot = fingerprint(self.root, definition)
        reviews = [{'axis': axis, 'observer': 'controlled-actual-document-observer', 'summary': 'Inspected actual formal content and document structure.',
            'fingerprint_digest': snapshot['digest'], 'findings': []} for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': a['id'], 'status': 'passed', 'basis': 'Actual target text matches the sum definition.'} for a in definition['acceptance']]
        if finding:
            reviews[1]['findings'] = [finding]
        request['input']['reviews'] = reviews
        return verify(self.root, request)

    def structured_plan(self, condition='verification_passed'):
        (self.root / 'note.txt').write_text('pending\n')
        self.auth['paths'].append('note.txt'); self.auth['effect_kinds'].append('business_files')
        data = {'complexity': 'complex', 'title': 'Formal definition and dependent note', 'plan': 'Apply and verify the formal definition before producing the dependent note.',
            'completion': 'Both actual outputs match their conditions.', 'scope': ['terms.md', 'note.txt'], 'required_checks': [],
            'acceptance': [{'key': 'DOC', 'text': 'Formal term expresses numeric sum.'}, {'key': 'NOTE', 'text': 'Note records that sum definition was inspected.'}],
            'spec': {'problem': 'Formal term and dependent note are incomplete.', 'goals': ['Correct both real outputs.'], 'non_goals': [],
                'behavior': ['The note uses the verified formal definition.'], 'constraints': ['Only declared files.'], 'tradeoffs': [],
                'test_decisions': ['Inspect actual text without inventing an executable test.'], 'open_questions': []}, 'tasks': []}
        for key, path, owner in [('DOC', 'terms.md', 'sync'), ('NOTE', 'note.txt', 'apply')]:
            data['tasks'].append({'local_key': key, 'title': key, 'completion': data['acceptance'][len(data['tasks'])]['text'], 'validation': 'Inspect actual target text.',
                'scope': [path], 'required_checks': [], 'responsible_action': owner, 'acceptance': [key], 'context_paths': [], 'exclusions': [],
                'test_decision_refs': ['spec.test_decisions/0'], 'dependencies': [] if key == 'DOC' else [{'upstream_task': 'DOC', 'condition_kind': condition, 'basis': 'Dependent note needs actual formal result.'}]})
        from evolve_core.structured import document
        data['presentation'] = {'source': 'controlled-structured-document-plan', 'document': document(data)}
        self.plan = propose(self.root, self.request(data))
        self.plan.update({'task_id': self.plan['tasks'][0]['id'], 'definition_digest': self.plan['tasks'][0]['definition_digest']})
        return self.plan['tasks'][1]['id']

    def implement_note(self, task_id):
        return implement(self.root, self.change_request({'task_id': task_id, 'accepted_plan_digest': self.plan['plan_digest'],
            'files': [{'path': 'note.txt', 'expected_digest': digest((self.root / 'note.txt').read_bytes()), 'content': 'Numeric sum definition inspected.\n'}]}))

    def test_standalone_application_and_actual_verification_are_separate_from_candidate(self):
        item = self.proposal(); approval = self.approve(item)
        self.assertEqual(self.rows('SELECT * FROM verifications'), [])
        applied = apply_knowledge(self.root, self.application_request(item, approval))
        self.assertEqual((self.root / 'terms.md').read_text(), CANDIDATE)
        self.assertEqual(applied['overall_verification'], 'not_run')
        self.assertEqual(self.rows('SELECT * FROM verifications'), [])
        result = verify_knowledge(self.root, self.request({'application_id': applied['application_id'], 'observations': self.observations()}))
        self.assertEqual(result['status'], 'passed'); self.assertEqual(result['subject_kind'], 'applied')
        row = self.rows('SELECT * FROM verifications')[0]
        self.assertIsNone(row['change_id']); self.assertIsNone(row['revision_id'])
        self.assertEqual(json.loads(row['fingerprint_json'])['actual_digest'], digest(CANDIDATE.encode()))
        self.assertEqual(self.rows('SELECT * FROM tasks'), [])

    def test_application_requires_exact_finalized_approval_and_latest_content_check(self):
        item = self.proposal()
        with self.assertRaises(EvolveError) as caught:
            apply_knowledge(self.root, self.application_request(item, 'missing'))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_APPROVAL')
        approval = self.approve(item)
        check_candidate(self.root, self.request({'proposal': self.ref(item), 'observations': self.observations('failed')}))
        with self.assertRaises(EvolveError) as caught:
            apply_knowledge(self.root, self.application_request(item, approval))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_CHECK')
        self.assertEqual((self.root / 'terms.md').read_text(), BASE)

    def test_external_formal_change_and_missing_knowledge_authority_are_not_overwritten(self):
        item = self.proposal(); approval = self.approve(item)
        request = self.application_request(item, approval); request['authorization']['paths'] = []
        with self.assertRaises(EvolveError) as caught: apply_knowledge(self.root, request)
        self.assertEqual(caught.exception.code, 'AUTHORIZATION')
        (self.root / 'terms.md').write_text(BASE + '外部正文。\n')
        with self.assertRaises(EvolveError) as caught: apply_knowledge(self.root, self.application_request(item, approval))
        self.assertEqual(caught.exception.code, 'FILE_CONFLICT')
        self.assertIn('外部正文', (self.root / 'terms.md').read_text())

    def test_retry_and_later_old_application_never_replay_the_document(self):
        item = self.proposal(); approval = self.approve(item); request = self.application_request(item, approval)
        first = apply_knowledge(self.root, request)
        (self.root / 'terms.md').write_text(CANDIDATE + '外部后续含义。\n')
        self.assertEqual(apply_knowledge(self.root, request), first)
        later = apply_knowledge(self.root, self.application_request(item, approval))
        self.assertEqual(later['application_id'], first['application_id']); self.assertFalse(later['current_matches'])
        self.assertIn('外部后续含义', (self.root / 'terms.md').read_text())
        self.assertEqual(len(self.rows('SELECT * FROM spec_applications')), 1)

    def test_new_successor_delta_does_not_replay_old_content_or_transfer_approval(self):
        first = self.proposal(); approved = self.approve(first)
        apply_knowledge(self.root, self.application_request(first, approved))
        second = self.proposal(content=CANDIDATE + '\n仅限声明的数值范围。\n')
        self.assertNotEqual(first['delta_id'], second['delta_id'])
        self.assertEqual(self.rows('SELECT predecessor_id FROM delta_items WHERE id=?', (second['delta_id'],))[0]['predecessor_id'], first['delta_id'])
        self.assertIsNone(self.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?', (second['proposal_id'],))[0]['approved_event_id'])

    def test_required_document_cannot_close_before_application_and_actual_acceptance(self):
        self.document_plan(); item = self.proposal(required=True); approval = self.approve(item)
        with self.assertRaises(EvolveError) as caught: self.verify_change()
        self.assertEqual(caught.exception.code, 'PLAN_ACCEPTANCE')
        with self.assertRaises(EvolveError) as caught: archive(self.root, self.change_request({'verification_id': 'candidate-is-not-applied'}))
        self.assertEqual(caught.exception.code, 'INCOMPLETE_TASK')
        applied = apply_knowledge(self.root, self.application_request(item, approval, required=True))
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'done')
        with self.assertRaises(EvolveError) as caught: archive(self.root, self.change_request({'verification_id': 'not-verified'}))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_VERIFICATION')
        verified = self.verify_change(); self.assertEqual(verified['status'], 'passed')
        self.assertEqual(self.rows('SELECT verification_id FROM spec_applications')[0]['verification_id'], verified['verification_id'])
        self.assertEqual(archive(self.root, self.change_request({'verification_id': verified['verification_id']}))['outcome'], 'archived')
        self.assertEqual(applied['overall_verification'], 'not_run')

    def test_multiple_required_documents_only_complete_after_all_actual_outputs(self):
        self.baseline('guide.md'); self.document_plan(['terms.md', 'guide.md'])
        first = self.proposal(required=True); second = self.proposal(path='guide.md', required=True)
        a = self.approve(first); b = self.approve(second)
        apply_knowledge(self.root, self.application_request(first, a, required=True))
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        apply_knowledge(self.root, self.application_request(second, b, required=True))
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'done')
        self.assertEqual(self.verify_change()['status'], 'passed')

    def test_formal_document_inside_records_directory_has_actual_scoped_fingerprint(self):
        self.baseline('evolve/project.md'); self.document_plan(['evolve/project.md'])
        item = self.proposal(path='evolve/project.md', required=True); approval = self.approve(item)
        apply_knowledge(self.root, self.application_request(item, approval, required=True))
        self.assertEqual(self.verify_change()['status'], 'passed')
        self.assertEqual((self.root / 'evolve/project.md').read_text(), CANDIDATE)

    def test_business_apply_cannot_complete_a_sync_task_even_without_files(self):
        self.document_plan()
        request = self.change_request({'accepted_plan_digest': self.plan['plan_digest'], 'files': []})
        request['authorization']['effect_kinds'].append('business_files')
        with self.assertRaises(EvolveError) as caught: implement(self.root, request)
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_OWNER')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'todo')

    def test_actual_verification_after_external_edit_is_blocked_and_preserves_prior_pass(self):
        item = self.proposal(); approval = self.approve(item)
        applied = apply_knowledge(self.root, self.application_request(item, approval))
        request = {'application_id': applied['application_id'], 'observations': self.observations()}
        old = verify_knowledge(self.root, self.request(request))
        (self.root / 'terms.md').write_text('外部回退。\n')
        new = verify_knowledge(self.root, self.request(request))
        self.assertEqual(old['status'], 'passed'); self.assertEqual(new['status'], 'blocked')
        self.assertEqual(self.rows('SELECT status FROM verifications WHERE id=?', (old['verification_id'],))[0]['status'], 'passed')
        self.assertEqual((self.root / 'terms.md').read_text(), '外部回退。\n')

    def test_formal_record_file_can_have_a_real_blocking_review_finding(self):
        self.baseline('evolve/project.md'); self.document_plan(['evolve/project.md'])
        item = self.proposal(path='evolve/project.md', required=True); approval = self.approve(item)
        apply_knowledge(self.root, self.application_request(item, approval, required=True))
        result = self.verify_change(finding={'id': 'DOC-WORDING', 'path': 'evolve/project.md', 'basis': 'Actual formal wording still needs a declared input limit.',
            'impact': 'Current required wording is incomplete.', 'blocking': True})
        self.assertEqual(result['status'], 'failed')

    def test_new_actual_document_failure_blocks_older_whole_change_pass(self):
        self.document_plan(); item = self.proposal(required=True); approval = self.approve(item)
        applied = apply_knowledge(self.root, self.application_request(item, approval, required=True))
        whole = self.verify_change(); self.assertEqual(whole['status'], 'passed')
        failed = verify_knowledge(self.root, self.request({'application_id': applied['application_id'], 'observations': self.observations('failed')}))
        self.assertEqual(failed['status'], 'failed')
        with self.assertRaises(EvolveError) as caught: archive(self.root, self.change_request({'verification_id': whole['verification_id']}))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_VERIFICATION')

    def test_structured_document_actual_task_verification_precedes_dependent_business_task(self):
        note = self.structured_plan(); item = self.proposal(required=True); approval = self.approve(item)
        apply_knowledge(self.root, self.application_request(item, approval, required=True))
        with self.assertRaises(EvolveError) as caught: self.implement_note(note)
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        self.assertEqual(self.verify_change()['status'], 'passed')
        self.implement_note(note)
        whole = self.verify_change(whole=True); self.assertEqual(whole['status'], 'passed')
        self.assertEqual(archive(self.root, self.change_request({'verification_id': whole['verification_id']}, whole=True))['outcome'], 'archived')
        self.assertEqual((self.root / 'note.txt').read_text(), 'Numeric sum definition inspected.\n')

    def test_unfinalized_document_application_cannot_satisfy_completed_dependency(self):
        note = self.structured_plan('task_completed'); item = self.proposal(required=True); approval = self.approve(item)
        original = Store.finish
        def fail_receipt(store, run_id, *args, **kwargs):
            row = store.one('SELECT action,method FROM phase_runs WHERE id=?', (run_id,))
            if row['action'] == 'sync' and row['method'] == 'apply':
                raise EvolveError('NEEDS_RECOVERY', 'Controlled receipt interruption after actual facts', exit_code=4)
            return original(store, run_id, *args, **kwargs)
        with patch.object(Store, 'finish', fail_receipt), self.assertRaises(EvolveError):
            apply_knowledge(self.root, self.application_request(item, approval, required=True))
        with self.assertRaises(EvolveError) as caught: self.implement_note(note)
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        self.assertEqual((self.root / 'note.txt').read_text(), 'pending\n')

    def test_format_revision_reuses_actual_document_application_without_new_delta_or_write(self):
        self.document_plan(['terms.md']); item = self.proposal(required=True); approval = self.approve(item)
        applied = apply_knowledge(self.root, self.application_request(item, approval, required=True))
        self.verify_change()
        original = self.rows('SELECT * FROM tasks')[0]; definition = json.loads(original['definition_json'])
        proposal = {'title': '更清楚的正式术语标题', 'plan': 'Keep the exact accepted formal term; clarify only the title.',
            'completion': definition['completion'], 'scope': definition['scope'], 'acceptance': [a['text'] for a in definition['acceptance']],
            'required_checks': [], 'responsible_action': 'sync'}
        proposal['presentation'] = {'source': 'controlled-format-document-revision', 'text': proposal['plan']}
        from evolve_core.revisions import revise
        result = revise(self.root, self.change_request({'proposal': proposal, 'reason': 'Display wording only.'}))
        self.assertTrue(result['tasks'][0]['result_reused'])
        current = self.rows('SELECT * FROM tasks WHERE id=?', (result['tasks'][0]['id'],))[0]
        self.assertEqual(current['state'], 'done')
        self.assertEqual(current['result_json'], original['result_json'])
        self.assertEqual(len(self.rows('SELECT * FROM delta_items')), 1)
        self.assertEqual(self.rows('SELECT id FROM spec_applications')[0]['id'], applied['application_id'])
        self.assertEqual((self.root / 'terms.md').read_text(), CANDIDATE)

    def test_business_spec_sync_needs_actual_implementation_and_rechecks_changed_outputs(self):
        note = self.structured_plan()
        with self.assertRaises(EvolveError) as caught:
            self.proposal(delivery={'role': 'followup', 'change_id': self.plan['change_id']})
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_BASIS')
        document = self.proposal(required=True); approved = self.approve(document)
        apply_knowledge(self.root, self.application_request(document, approved, required=True)); self.verify_change(); self.implement_note(note)
        verified = self.verify_change(whole=True); self.assertEqual(verified['status'], 'passed')
        item = self.proposal(content=CANDIDATE + '\n依赖的说明已实现。\n', delivery={'role': 'followup', 'change_id': self.plan['change_id']},
            basis={'verification_id': verified['verification_id'], 'purpose': 'Reflect the actual completed dependent note.'})
        approval = self.approve(item)
        (self.root / 'note.txt').write_text('external regression\n')
        with self.assertRaises(EvolveError) as caught: apply_knowledge(self.root, self.application_request(item, approval))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_BASIS')
        self.assertEqual((self.root / 'terms.md').read_text(), CANDIDATE)

    def test_approved_followup_spec_applies_after_archive_without_reopening_frozen_work(self):
        note = self.structured_plan(); document = self.proposal(required=True); approval = self.approve(document)
        apply_knowledge(self.root, self.application_request(document, approval, required=True)); self.verify_change(); self.implement_note(note)
        verified = self.verify_change(whole=True)
        archive(self.root, self.change_request({'verification_id': verified['verification_id']}, whole=True))
        before = self.rows('SELECT * FROM tasks')
        item = self.proposal(content=CANDIDATE + '\n依赖的说明已实现。\n', delivery={'role': 'followup', 'change_id': self.plan['change_id']},
            basis={'verification_id': verified['verification_id'], 'purpose': 'Reflect the actually verified dependent note.'})
        approval = self.approve(item); applied = apply_knowledge(self.root, self.application_request(item, approval))
        self.assertTrue(applied['applied']); self.assertEqual(self.rows('SELECT * FROM tasks'), before)
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'archived')

    def interrupted_application(self, point, required=False, prepared_item=None):
        if required: self.document_plan()
        item = prepared_item or self.proposal(required=required); approved = self.approve(item)
        request = self.application_request(item, approved, required)
        code = """import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core import formal
from evolve_core.store import Store
point=sys.argv[3]
if point=='prepared':
 def die(*args,**kwargs): os._exit(51)
 formal.install_files=die
elif point=='files':
 def die(*args,**kwargs): os._exit(52)
 formal._commit_application=die
else:
 original=Store.finish
 def finish(self,run_id,*args,**kwargs):
  row=self.one('SELECT action,method FROM phase_runs WHERE id=?',(run_id,))
  if row['action']=='sync' and row['method']=='apply': os._exit(53)
  return original(self,run_id,*args,**kwargs)
 Store.finish=finish
formal.apply_knowledge(sys.argv[2],json.load(sys.stdin))
"""
        process = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'), str(self.root), point],
            input=json.dumps(request), text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, {'prepared': 51, 'files': 52, 'facts': 53}[point], process.stderr)
        run = self.rows('SELECT id FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]['id']
        return run

    def test_pending_business_spec_journal_does_not_write_after_implementation_changes(self):
        note = self.structured_plan(); document = self.proposal(required=True); approval = self.approve(document)
        apply_knowledge(self.root, self.application_request(document, approval, required=True)); self.verify_change(); self.implement_note(note)
        verified = self.verify_change(whole=True)
        item = self.proposal(content=CANDIDATE + '\n对应的说明已实现。\n', delivery={'role': 'followup', 'change_id': self.plan['change_id']},
            basis={'verification_id': verified['verification_id'], 'purpose': 'Synchronize the actual dependent implementation.'})
        run = self.interrupted_application('prepared', prepared_item=item)
        (self.root / 'note.txt').write_text('external implementation regression\n')
        with self.assertRaises(EvolveError) as caught: recover(self.root, self.request({'run_id': run}))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_BASIS')
        self.assertEqual((self.root / 'terms.md').read_text(), CANDIDATE)

    def test_applied_spec_verification_blocks_after_its_implementation_basis_changes(self):
        note = self.structured_plan(); document = self.proposal(required=True); approval = self.approve(document)
        apply_knowledge(self.root, self.application_request(document, approval, required=True)); self.verify_change(); self.implement_note(note)
        verified = self.verify_change(whole=True)
        item = self.proposal(content=CANDIDATE + '\n对应的说明已实现。\n', delivery={'role': 'followup', 'change_id': self.plan['change_id']},
            basis={'verification_id': verified['verification_id'], 'purpose': 'Synchronize the actual dependent implementation.'})
        approval = self.approve(item); applied = apply_knowledge(self.root, self.application_request(item, approval))
        (self.root / 'note.txt').write_text('external implementation regression\n')
        result = verify_knowledge(self.root, self.request({'application_id': applied['application_id'], 'observations': self.observations()}))
        self.assertEqual(result['status'], 'blocked')
        saved = self.rows('SELECT items_json FROM verifications WHERE id=?', (result['verification_id'],))[0]
        self.assertEqual(json.loads(saved['items_json'])['implementation_basis_error']['code'], 'KNOWLEDGE_BASIS')

    def test_recovery_from_registered_journal_finishes_only_the_original_approved_write(self):
        run = self.interrupted_application('prepared', required=True)
        self.assertEqual((self.root / 'terms.md').read_text(), BASE)
        recovered = recover(self.root, self.request({'run_id': run}))
        self.assertFalse(recovered['business_commands_run'])
        self.assertEqual((self.root / 'terms.md').read_text(), CANDIDATE)
        self.assertEqual(self.verify_change()['status'], 'passed')

    def test_standalone_actual_verification_committed_before_exit_recovers_without_new_observation(self):
        item = self.proposal(); approval = self.approve(item)
        applied = apply_knowledge(self.root, self.application_request(item, approval))
        request = self.request({'application_id': applied['application_id'], 'observations': self.observations()})
        code = """import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core.formal import verify_knowledge
from evolve_core.store import Store
original=Store.finish
def finish(self,run_id,*args,**kwargs):
 row=self.one('SELECT action,method FROM phase_runs WHERE id=?',(run_id,))
 if row['action']=='verify' and row['method']=='knowledge': os._exit(54)
 return original(self,run_id,*args,**kwargs)
Store.finish=finish
verify_knowledge(sys.argv[2],json.load(sys.stdin))
"""
        process = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'), str(self.root)], input=json.dumps(request), text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, 54, process.stderr)
        run = self.rows('SELECT id FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]['id']
        before = self.rows('SELECT * FROM verifications')
        result = recover(self.root, self.request({'run_id': run}))
        self.assertTrue(result['original_facts_committed']); self.assertFalse(result['business_commands_run'])
        self.assertEqual(self.rows('SELECT * FROM verifications'), before)

    def test_recovery_after_real_file_commit_records_application_without_repeating_checks(self):
        run = self.interrupted_application('files', required=True)
        self.assertEqual((self.root / 'terms.md').read_text(), CANDIDATE)
        self.assertEqual(self.rows('SELECT * FROM spec_applications'), [])
        recovered = recover(self.root, self.request({'run_id': run}))
        self.assertFalse(recovered['business_commands_run'])
        self.assertEqual(len(self.rows('SELECT * FROM spec_applications')), 1)
        self.assertEqual(self.verify_change()['status'], 'passed')
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (run,))[0]['status'], 'interrupted')

    def test_recovery_of_committed_facts_does_not_duplicate_artifact_or_task_completion(self):
        run = self.interrupted_application('facts', required=True)
        before = self.rows('SELECT * FROM spec_applications'); task = self.rows('SELECT * FROM tasks')[0]
        with self.assertRaises(EvolveError) as caught: self.verify_change()
        self.assertEqual(caught.exception.code, 'WRITER_ACTIVE')
        self.assertTrue(current_state(self.root, self.rows('SELECT proposal_id FROM spec_applications')[0]['proposal_id'])['knowledge_proposals'][0]['application']['source_pending'])
        recovered = recover(self.root, self.request({'run_id': run}))
        self.assertFalse(recovered['facts_created'])
        after = self.rows('SELECT * FROM spec_applications')
        self.assertEqual(before, after)
        self.assertEqual(task, self.rows('SELECT * FROM tasks')[0])
        self.assertEqual(self.verify_change()['status'], 'passed')

    def test_recovery_preserves_third_party_formal_bytes(self):
        run = self.interrupted_application('files')
        (self.root / 'terms.md').write_text('第三方新含义。\n')
        result = recover(self.root, self.request({'run_id': run}))
        self.assertEqual(result['outcome'], 'needs_recovery')
        self.assertEqual((self.root / 'terms.md').read_text(), '第三方新含义。\n')
        self.assertEqual(self.rows('SELECT * FROM spec_applications'), [])

    def test_preserved_alpha7_writer_rejects_new_document_protocol_without_writes(self):
        self.document_plan(); package = self.root / 'old-complete-package'
        with zipfile.ZipFile(ROOT / 'tests/fixtures/candidate-package-alpha7.zip') as a: a.extractall(package)
        before = (self.root / 'evolve/history.db').read_bytes()
        result = subprocess.run([sys.executable, '-B', str(package / 'package/runtime/evolve.py'), '--project', str(self.root),
            'archive', '--request', '-'], input=json.dumps({'authorization': self.auth, 'input': {'change_id': self.plan['change_id']}}), text=True, capture_output=True, timeout=15)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'SCHEMA_VERSION')
        self.assertEqual((self.root / 'evolve/history.db').read_bytes(), before)
        self.assertEqual((self.root / 'terms.md').read_text(), BASE)
