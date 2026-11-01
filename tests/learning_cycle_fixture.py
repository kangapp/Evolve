"""Actual owner calls for the bounded list-to-iterator learning cycle."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'runtime'), str(ROOT / 'scripts')]
from learning_fixture import FILES, BASE, FINAL, CORRECT, ITERATOR_BUG, IMPROVED, CHECKS
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.connect import connect
from evolve_core.formal import verify_knowledge
from evolve_core.knowledge import propose_baseline, apply_baseline
from evolve_core.knowledge_proposals import check_candidate, review_candidates
from evolve_core.learning import learn, search
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.resume import resume_view
from evolve_core.revisions import revise
from evolve_core.structured import document, whole_definition
from evolve_core.verify import verify
from evolve_core.work import fingerprint


class LearningCycleFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-learning-cycle-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name, content in FILES.items():
            (self.root / name).write_text(content)
        self.auth = {'source': 'controlled-actual-learning-cycle',
            'text': 'Only this temporary list/iterator experiment, exact guide text and original checks; no CI or hook changes.',
            'effect_kinds': ['project_records', 'business_files', 'checks', 'knowledge'],
            'paths': ['total.py', 'test_total.py', 'guide.md']}
        self.checks = copy.deepcopy(CHECKS)
        self.project = connect(self.root, {'authorization': self.auth, 'input': {'checks': self.checks}})
        self.original_guard = ((self.root / 'guard.py').read_bytes(), (self.root / 'guard.py').stat().st_mtime_ns)

    def rows(self, sql, args=()):
        with sqlite3.connect(self.root / 'evolve/history.db') as c:
            c.row_factory = sqlite3.Row
            return [dict(row) for row in c.execute(sql, args)]

    def project_request(self, data):
        return {'request_id': str(uuid.uuid4()), 'project_id': self.project['project_id'],
            'expected_workspace_epoch': self.project['workspace_epoch'], 'authorization': copy.deepcopy(self.auth), 'input': data}

    def select(self, plan, key=None):
        self.selected = (plan['change_id'], key)

    def context(self, whole=False):
        change = self.rows('SELECT * FROM changes WHERE id=?', (self.selected[0],))[0]
        revision = self.rows('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],))[0]
        tasks = self.rows('SELECT * FROM tasks WHERE revision_id=?', (revision['id'],))
        task = next(t for t in tasks if self.selected[1] is None or json.loads(t['definition_json'])['local_key'] == self.selected[1])
        definition = whole_definition(revision, tasks) if whole and change['complexity'] == 'complex' else json.loads(task['definition_json'])
        return change, revision, task, tasks, definition

    def request(self, data=None, whole=False):
        change, revision, task, tasks, _ = self.context(whole)
        complex_work = change['complexity'] == 'complex'
        request = self.project_request({'change_id': change['id'], 'revision_id': revision['id'],
            'definition_digest': revision['definition_digest'] if whole and complex_work else task['definition_digest'], **(data or {})})
        if complex_work:
            request['input']['task_id'] = None if whole else task['id']
            request['expected_versions'] = {'change': change['row_version'], 'tasks': {t['id']: t['row_version'] for t in tasks}}
        else:
            request['expected_versions'] = {'change': change['row_version'], 'task': task['row_version']}
        return request

    def ref(self, run_id, *, evidence=False):
        row = self.rows('SELECT * FROM phase_runs WHERE id=?', (run_id,))[0]
        result = {'run_id': run_id, 'result_digest': row['result_digest']}
        if evidence:
            result['evidence_ids'] = [r['id'] for r in self.rows('SELECT id FROM evidence WHERE source_run_id=?', (run_id,))]
        return result

    def simple(self, title, scope, checks, acceptance, owner='apply'):
        text = 'Deliver only ' + title + ' with the declared independent observations.'
        return propose(self.root, self.project_request({'title': title, 'plan': text, 'completion': title,
            'scope': scope, 'required_checks': checks, 'responsible_action': owner, 'acceptance': acceptance,
            'presentation': {'source': 'controlled-complete-plan', 'text': text}}))

    def run_check(self, name):
        check = next(c for c in self.checks if c['id'] == name)
        return subprocess.run(check['argv'], cwd=self.root, capture_output=True, text=True, timeout=40)

    def apply_files(self, files):
        _, revision, _, _, _ = self.context()
        return implement(self.root, self.request({'accepted_plan_digest': revision['plan_digest'], 'files': [
            {'path': name, 'expected_digest': digest((self.root / name).read_bytes()), 'content': content}
            for name, content in files.items()]}))

    def verify_work(self, *, whole=False, failed_generator=False):
        _, _, _, _, definition = self.context(whole)
        observed = fingerprint(self.root, definition)
        basis = 'Read the actual scoped files and original literals. '
        if failed_generator:
            result = subprocess.run([sys.executable, '-B', '-c', 'from total import total; assert total(iter([5,-2])) == 3'],
                cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            basis += 'Actual generator assertion failed: ' + result.stdout + result.stderr
        else:
            for check in definition['required_checks']:
                result = self.run_check(check)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                basis += check + ': ' + result.stdout + result.stderr
        reviews = [{'axis': axis, 'observer': 'controlled-actual-cycle-observer', 'summary': basis,
                    'fingerprint_digest': observed['digest'], 'findings': []} for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': a['id'],
            'status': 'failed' if failed_generator and 'iterator' in a['text'] else 'passed', 'basis': basis}
            for a in definition['acceptance']]
        return verify(self.root, self.request({'reviews': reviews}, whole))

    def close(self, verification, whole=False):
        return archive(self.root, self.request({'verification_id': verification['verification_id']}, whole))

    def entry(self, reference):
        return next(e for e in search(self.root, 'sum')['results'] if e['experience_ref']['run_id'] == reference['run_id'])

    def record_experience(self, source, *, iterator=False):
        item = {'topic': 'sum iterator coverage' if iterator else 'sum list literals',
            'problem': 'The original list examples omit a one-time iterator' if iterator else 'Count differs from the independent list sums',
            'cause': {'confidence': 'observed', 'statement': 'The actual fixed checks exposed this bounded list/iterator distinction.'},
            'advice': 'Add an independent iterator literal while preserving the original assertions' if iterator else 'Recheck the original list literals and the new input domain before reuse',
            'applicability': 'This temporary integer sum fixture; input domain must be inspected',
            'version_context': sys.version.split()[0], 'observer': 'controlled-actual-cycle-observer',
            'scope': ['local integer iterator checks' if iterator else 'local integer list checks'],
            'exclusions': ['No exhaustive numeric or production guarantee'], 'tags': ['sum', 'iterator' if iterator else 'lists'],
            'limitations': ['Only the supplied literal observations; success counts do not establish general causal benefit.']}
        result = learn(self.root, self.project_request({'experience': item, 'sources': source if isinstance(source, list) else [source]}), method='record')
        return self.ref(result['run_id'])

    def decision(self, reference, decision='adopted'):
        change, revision, task, _, definition = self.context()
        result = learn(self.root, self.project_request({'kind': 'decision', 'experience_ref': reference,
            'search_ref': search(self.root, 'sum')['search_ref'], 'decision': decision,
            'change_id': change['id'], 'revision_id': revision['id'], 'task_id': task['id'], 'definition_digest': task['definition_digest'],
            'observed_files': {p: digest((self.root / p).read_bytes()) for p in definition['scope']},
            'applicability_basis': 'Read this actual definition and current file; old list evidence is not iterator proof.',
            'limitations': ['A suggestion neither authorizes modification nor establishes a universal rule.']}), method='review')
        return self.ref(result['run_id'])

    def feedback(self, decision, source, outcome):
        return learn(self.root, self.project_request({'kind': 'feedback', 'decision_ref': decision,
            'result_source': source, 'outcome': outcome,
            'basis': 'Actual same-definition post-decision check observations support only this bounded assessment.',
            'limitations': ['No attribution to every citation or general quality claim.']}), method='review')

    def rule_observation(self):
        return verify_knowledge(self.root, self.project_request({'application_id': self.rule_application['application_id'],
            'observations': [{'criterion_key': 'RULE', 'status': 'passed', 'observer': 'controlled-actual-rule-reader',
                'basis': 'Read the whole guide; exact bounded rule wording remains: ' + (self.root / 'guide.md').read_text()}]}))

    def seed(self):
        self.a = self.simple('列表求和 A', ['total.py'], ['unit'], ['Original list literals return their independent sums.'])
        self.select(self.a)
        failed = self.apply_files({})
        self.assertEqual(failed['outcome'], 'checks_not_passed')
        failed_source = self.ref(failed['run_id'], evidence=True)
        self.apply_files({'total.py': CORRECT})
        accepted = self.verify_work()
        self.assertEqual(accepted['status'], 'passed')
        self.close(accepted)
        self.old_support = self.ref(accepted['run_id'], evidence=True)
        self.old_experience = self.record_experience([failed_source, self.old_support])
        base = propose_baseline(self.root, self.project_request({'path': 'guide.md', 'content': BASE,
            'expected_digest': digest(BASE.encode()), 'presentation': {'source': 'controlled-exact-baseline', 'text': BASE}}))
        apply_baseline(self.root, self.project_request({'proposal_id': base['proposal_id'], 'approval': {
            **{k: base[k] for k in ('proposal_version', 'candidate_digest', 'expected_digest')},
            'source': 'controlled-specific-baseline-approval', 'text': 'Approve only the existing temporary guide bytes.'}}))
        self.r = self.simple('列表审查规则 R', ['guide.md'], [], ['The exact scoped review rule exists.'], 'learn')
        self.select(self.r)
        entry = self.entry(self.old_experience)
        data = {'stage': 'propose', 'path': 'guide.md', 'expected_digest': digest(BASE.encode()), 'content': FINAL,
            'presentation': {'source': 'controlled-exact-rule', 'text': FINAL}, 'topic': 'literal-review-rule',
            'reason': 'Deliver only the specifically approved bounded text.', 'acceptance': [{'key': 'RULE', 'text': 'The exact scoped review clause is present.'}],
            'rule_scope': ['本临时项目整数列表求和审查'], 'rule_sources': [{'experience_ref': self.old_experience,
                'state_ref': entry['state_ref'], 'counterexamples': [], 'basis': 'Actual original list checks, with iterator coverage explicitly unobserved.'}],
            'delivery': {'role': 'required', 'change_id': self.r['change_id'], 'revision_id': self.r['revision_id'],
                'task_id': self.r['task_id'], 'definition_digest': self.r['definition_digest'], 'acceptance_ids': [self.r['acceptance'][0]['id']]}}
        candidate = learn(self.root, self.project_request(data), method='promote')
        self.rule_ref = {k: candidate[k] for k in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}
        observation = {'criterion_key': 'RULE', 'status': 'passed', 'observer': 'controlled-exact-rule-reader',
            'basis': 'Read the complete requested clause and its actual bounded list sources; no iterator guarantee is claimed.'}
        check_candidate(self.root, self.project_request({'proposal': self.rule_ref, 'observations': [observation]}))
        approval = review_candidates(self.root, self.project_request({'decisions': [{'proposal': self.rule_ref,
            'decision': 'approved', 'source': 'controlled-specific-rule-approval', 'text': 'Approve only the exact presented temporary rule.',
            'reason': 'Read the full text and bounded sources.'}]}))['decisions'][0]['decision_event_id']
        self.rule_application = learn(self.root, self.request({'stage': 'apply', 'proposal': self.rule_ref,
            'approved_event_id': approval, 'accepted_plan_digest': self.r['plan_digest']}), method='promote')
        self.assertEqual(self.rule_observation()['status'], 'passed')
        accepted = self.verify_work()
        self.assertEqual(accepted['status'], 'passed')
        self.close(accepted)
        self.guide_after_seed = ((self.root / 'guide.md').read_bytes(), (self.root / 'guide.md').stat().st_mtime_ns)
        self.c = self.pending_plan()
        self.select(self.c, 'LISTS')
        self.pending_decision = self.decision(self.old_experience)

    def pending_plan(self):
        data = {'complexity': 'complex', 'title': '待执行列表复查 C', 'plan': 'Inspect the original list behavior later.',
            'completion': 'Original list scope is independently checked.', 'scope': ['total.py'], 'required_checks': ['unit'],
            'acceptance': [{'key': 'LISTS', 'text': 'Original list sums remain correct.'}],
            'spec': {'problem': 'A later list review is pending.', 'goals': ['Retain the list contract.'], 'non_goals': ['No iterator claim.'],
                'behavior': ['Original list literals remain.'], 'constraints': ['Do not execute this pending plan in this experiment.'],
                'tradeoffs': [], 'test_decisions': ['Reinspect the original literals and current suggestion before execution.'], 'open_questions': []},
            'tasks': [{'local_key': 'LISTS', 'title': 'Later list review', 'completion': 'The declared list review is done.',
                'validation': 'Run original unit after a fresh applicability decision.', 'scope': ['total.py'], 'acceptance': ['LISTS'],
                'required_checks': ['unit'], 'context_paths': ['test_total.py', 'guard.py'], 'test_decision_refs': ['spec.test_decisions/0'],
                'exclusions': ['Iterator behavior'], 'dependencies': []}]}
        data['presentation'] = {'source': 'controlled-full-pending-plan', 'document': document(data)}
        return propose(self.root, self.project_request(data))

    def counterexample(self, *, inject=True):
        if inject:
            (self.root / 'total.py').write_text(ITERATOR_BUG)
        self.b = self.simple('迭代器求和 B', ['total.py'], ['unit', 'guard'],
            ['Original list sums remain correct.', 'A one-time iterator [5,-2] returns the literal 3.'])
        self.select(self.b)
        self.old_decision = self.decision(self.old_experience, 'rejected')
        self.assertEqual(self.run_check('unit').returncode, 0)
        self.assertEqual(self.run_check('guard').returncode, 1)
        failed = self.apply_files({})
        self.assertEqual(failed['outcome'], 'checks_not_passed')
        self.counter_source = self.ref(failed['run_id'], evidence=True)
        actual = self.verify_work(failed_generator=True)
        self.assertIn(actual['status'], ('failed', 'blocked'))
        self.counter_feedback = self.feedback(self.old_decision, self.counter_source, 'counterexample')
        self.assertEqual(self.entry(self.old_experience)['state'], 'needs_review')
        self.assertEqual(self.rule_observation()['status'], 'blocked')
        view = resume_view(self.root, self.c['change_id'])
        adopted = view['learning_context']['applications'][0]
        self.assertTrue(adopted['state_changed_since_decision'])
        self.assertFalse(adopted['recommendation_allowed'])

    def check_plan(self):
        data = {'complexity': 'complex', 'title': '迭代器求和 B',
            'plan': 'First improve the existing literal test through apply, then repair the public function.',
            'completion': 'Preserved list and iterator behavior pass unit and the independent guard.',
            'scope': ['test_total.py', 'total.py'], 'required_checks': ['unit', 'guard'],
            'acceptance': [{'key': 'LISTS', 'text': 'Original list sums remain correct.'},
                {'key': 'ITERATOR', 'text': 'A one-time iterator [5,-2] returns the literal 3.'},
                {'key': 'COVERAGE', 'text': 'Preserve original literals and detect both fixed wrong variants.'}],
            'spec': {'problem': 'Original list tests pass despite the real iterator counterexample.',
                'goals': ['Catch the observed coverage gap and repair the actual function.'],
                'non_goals': ['No CI, hook, guard or formal-rule changes.'],
                'behavior': ['Original positive, empty and negative lists remain correct.', 'One-time iterator [5,-2] returns 3.'],
                'constraints': ['Do not remove or change original literal assertions.', 'Learn records proposals; apply owns test and source changes.'],
                'tradeoffs': ['One new independent literal test instead of another test framework.'],
                'test_decisions': ['Protected guard must reject count and iterator-zero variants and accept sum; unit observes the real current source.'],
                'open_questions': []},
            'tasks': [{'local_key': 'CHECK', 'title': 'Close the missing iterator test case',
                'completion': 'Existing literal method is preserved and the iterator literal catches both wrong variants.',
                'validation': 'Run the actual protected guard; do not call its success a pass for the still-broken current source.',
                'scope': ['test_total.py'], 'acceptance': ['COVERAGE'], 'required_checks': ['guard'],
                'context_paths': ['guard.py'], 'test_decision_refs': ['spec.test_decisions/0'],
                'exclusions': ['Source and formal-rule changes'], 'dependencies': []},
                {'local_key': 'FIX', 'title': 'Restore actual integer iterator sums', 'completion': 'Original list and iterator literals pass.',
                'validation': 'Run the unchanged unit and guard definitions on the actual final scene.',
                'scope': ['total.py'], 'acceptance': ['LISTS', 'ITERATOR'], 'required_checks': ['unit', 'guard'],
                'context_paths': ['test_total.py', 'guard.py'], 'test_decision_refs': ['spec.test_decisions/0'],
                'exclusions': ['Test, guard and formal-rule changes'],
                'dependencies': [{'upstream_task': 'CHECK', 'condition_kind': 'verification_passed',
                    'basis': 'Repair follows the actual coverage Task acceptance, not merely its done state.'}]}]}
        data['presentation'] = {'source': 'controlled-complete-check-improvement', 'document': document(data)}
        return data

    def propose_check(self):
        self.assertEqual(self.run_check('guard').returncode, 1)
        self.new_experience = self.record_experience(self.counter_source, iterator=True)
        self.new_plan = self.check_plan()
        self.select(self.b)
        self.preview = revise(self.root, self.request({'proposal': self.new_plan,
            'reason': 'The actual second task exposed missing iterator coverage; present the smallest original-owner test improvement.'}, whole=True))
        self.assertIn(self.preview['outcome'], ('revised', 'scope_confirmation_required'))
        self.assertFalse(self.preview.get('accepted', False))
        self.assertEqual((self.root / 'test_total.py').read_text(), FILES['test_total.py'])

    def implement_check(self):
        self.select(self.b)
        accepted = revise(self.root, self.request({'proposal': self.new_plan,
            'reason': 'Specifically accept the exact presented CHECK/FIX scope and original acceptance.',
            'approval': {'candidate_digest': self.preview['candidate_digest'],
                'source': 'controlled-specific-check-fix-approval', 'text': 'Accept only this exact complete revision.'}}, whole=True))
        self.assertTrue(accepted['accepted'])
        self.select(self.b, 'CHECK')
        self.new_decision = self.decision(self.new_experience)
        before = ((self.root / 'total.py').read_bytes(), (self.root / 'total.py').stat().st_mtime_ns)
        self.assertEqual(self.apply_files({'test_total.py': IMPROVED})['outcome'], 'implemented')
        accepted = self.verify_work()
        self.assertEqual(accepted['status'], 'passed')
        self.check_source = self.ref(accepted['run_id'], evidence=True)
        self.assertEqual(((self.root / 'total.py').read_bytes(), (self.root / 'total.py').stat().st_mtime_ns), before)
        self.assertEqual(self.run_check('unit').returncode, 1)

    def fix_and_archive(self):
        self.select(self.b, 'FIX')
        self.assertEqual(self.apply_files({'total.py': CORRECT})['outcome'], 'implemented')
        self.assertEqual(self.verify_work()['status'], 'passed')
        whole = self.verify_work(whole=True)
        self.assertEqual(whole['status'], 'passed')
        self.assertEqual(self.close(whole, whole=True)['outcome'], 'archived')

    def feedback_and_resume(self):
        observed = self.feedback(self.new_decision, self.check_source, 'helped')
        self.assertEqual(observed['attribution'], 'observer_assessment_not_inferred_from_task_status')
        self.assertEqual(self.entry(self.new_experience)['state'], 'candidate')
        self.assertEqual(self.entry(self.old_experience)['state'], 'needs_review')
        self.assertEqual(self.rule_observation()['status'], 'blocked')
        pending = resume_view(self.root, self.c['change_id'])
        decision = pending['learning_context']['applications'][0]
        self.assertTrue(decision['state_changed_since_decision'])
        self.assertEqual(decision['decision']['effect'], 'unknown')
        task = self.rows('SELECT * FROM tasks WHERE change_id=?', (self.c['change_id'],))[0]
        self.assertEqual(task['state'], 'todo')
        self.assertIsNone(task['result_json'])
        self.assertEqual(((self.root / 'guide.md').read_bytes(), (self.root / 'guide.md').stat().st_mtime_ns), self.guide_after_seed)
        self.assertEqual(((self.root / 'guard.py').read_bytes(), (self.root / 'guard.py').stat().st_mtime_ns), self.original_guard)
        self.assertFalse(self.rows("SELECT id FROM phase_runs WHERE status='started'"))
        self.assertFalse(self.rows('SELECT * FROM resource_claims'))
