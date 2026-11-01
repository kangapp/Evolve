"""Real A/B work uses fixed task proofs; unrelated C remains free to progress."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

import test_structured_execution as fixture
from evolve_core.cancellation import cancel_change
from evolve_core.errors import EvolveError
from evolve_core.reading import current_state
from evolve_core.revisions import revise

ROOT = Path(__file__).resolve().parents[1]


class CrossDependencyTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.StructuredExecutionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.a = self.f.plan
        self.f.auth['text'] = 'Complete only the controlled A/B/C work, original checks, and explicitly requested local cancellation.'

    def select(self, plan):
        self.f.plan = plan

    def reference(self, plan, key, condition='verification_passed'):
        self.select(plan)
        change, revision, _, task, _ = self.f.context(key)
        return {'upstream_change_id': change['id'], 'upstream_task_id': task['id'],
            'required_revision_id': revision['id'], 'required_definition_digest': task['definition_digest'],
            'condition_kind': condition, 'basis': 'B consumes the exact bounded, actually verified upstream total interface.'}

    def b_data(self, reference=None):
        ref = reference or self.reference(self.a, 'SUM')
        data = copy.deepcopy(self.f.data)
        data.update(title='Independent report work B', plan='Consume the fixed verified A total, then deliver report B.',
                    scope=['report.py'], required_checks=['report'], acceptance=[data['acceptance'][1]], tasks=[data['tasks'][1]])
        data['tasks'][0]['dependencies'] = []
        data['tasks'][0]['external_dependencies'] = [ref]
        data['tasks'][0]['context_paths'].append('total.py')
        return data

    def make_b(self, reference=None):
        self.b = self.f.propose(self.b_data(reference))
        return self.b

    def ready(self, plan, key):
        state = current_state(self.f.root, plan['change_id'])['changes'][0]
        return next(task['readiness'] for task in state['tasks'] if task['local_key'] == key)

    def finish_a_sum(self):
        self.select(self.a)
        self.assertEqual(self.f.apply('SUM', {'total.py': fixture.SUM})['outcome'], 'implemented')
        self.assertEqual(self.f.verify('SUM')['status'], 'passed')

    def finish_b(self):
        self.select(self.b)
        self.assertEqual(self.f.apply('REPORT', {'report.py': fixture.REPORT})['outcome'], 'implemented')
        self.assertEqual(self.f.verify('REPORT')['status'], 'passed')
        result = self.f.verify()
        self.assertEqual(result['status'], 'passed')
        return result

    def test_done_is_not_verified_and_produced_inputs_are_not_frozen_as_old_context(self):
        self.make_b()
        self.assertFalse(self.ready(self.b, 'REPORT')['ready'])
        self.select(self.a)
        self.f.apply('SUM', {'total.py': fixture.SUM})
        self.assertFalse(self.ready(self.b, 'REPORT')['ready'])
        self.f.verify('SUM')
        self.assertTrue(self.ready(self.b, 'REPORT')['ready'])
        self.select(self.b)
        definition = self.f.context('REPORT')[-1]
        self.assertNotIn('total.py', definition['context'])
        self.assertIn('total.py', definition['dependency_inputs'])
        result = self.finish_b()
        self.assertEqual(self.f.close(result)['outcome'], 'archived')
        self.select(self.a)
        states = {json.loads(row['definition_json'])['local_key']: row['state'] for row in self.f.context()[2]}
        self.assertEqual(states, {'SUM': 'done', 'REPORT': 'todo'})

    def test_upstream_cancellation_invalidates_only_real_downstream_and_preserves_old_results(self):
        self.make_b()
        self.finish_a_sum()
        self.finish_b()
        self.select(self.b)
        saved = self.f.context('REPORT')[3]['result_json']
        old_verifications = self.f.rows('SELECT * FROM verifications')
        self.select(self.a)
        request = self.f.request(extra={'reason': 'Controlled cancellation of upstream A; keep physical effects.'})
        cancel_change(self.f.root, request)
        before = (self.f.root / 'evolve/history.db').read_bytes()
        observed = self.ready(self.b, 'REPORT')
        self.assertTrue(observed['revalidation_required'])
        self.assertTrue(observed['unmet'])
        self.assertEqual((self.f.root / 'evolve/history.db').read_bytes(), before)
        self.select(self.b)
        self.assertEqual(self.f.context('REPORT')[3]['result_json'], saved)
        self.assertEqual(self.f.rows('SELECT * FROM verifications'), old_verifications)
        # C is an independent literal file deliverable, with no fabricated check.
        data = self.b_data(self.reference(self.a, 'SUM'))
        data.update(title='Unrelated C', plan='Write only the literal independent note C.', scope=['c.txt'], required_checks=[])
        data['acceptance'][0]['text'] = 'c.txt contains the independent C literal.'
        data['spec'].update(goals=['Deliver the independent note C.'], behavior=['c.txt contains independent C followed by a newline.'],
                            test_decisions=['Read c.txt and compare the exact declared literal.'])
        task = data['tasks'][0]
        task.update(local_key='OTHER', scope=['c.txt'], required_checks=[], context_paths=[], external_dependencies=[],
                    completion='The independent note exists.', validation='Read c.txt and compare exact declared literal.', test_decision_refs=['spec.test_decisions/0'])
        c = self.f.propose(data)
        self.f.auth['paths'].append('c.txt')
        self.select(c)
        self.assertEqual(self.f.apply('OTHER', {'c.txt': 'independent C\n'})['outcome'], 'implemented')
        self.assertEqual((self.f.root / 'c.txt').read_text(), 'independent C\n')

    def test_changed_upstream_context_blocks_consumer_without_overwriting_external_edit(self):
        self.make_b()
        self.finish_a_sum()
        changed = (self.f.root / 'test_total.py').read_text().replace('([2,3]),5', '([2,3]),77')
        (self.f.root / 'test_total.py').write_text(changed)
        self.assertFalse(self.ready(self.b, 'REPORT')['ready'])
        self.select(self.b)
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('REPORT', {'report.py': fixture.REPORT})
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        self.assertEqual((self.f.root / 'test_total.py').read_text(), changed)
        self.assertFalse((self.f.root / 'report.py').exists())

    def test_unknown_or_changed_fixed_target_is_rejected_before_acceptance(self):
        for field in ('upstream_change_id', 'upstream_task_id', 'required_revision_id', 'required_definition_digest'):
            with self.subTest(field=field):
                ref = self.reference(self.a, 'SUM')
                ref[field] = 'not-the-observed-target'
                with self.assertRaises(EvolveError) as caught:
                    self.make_b(ref)
                self.assertEqual(caught.exception.code, 'DEPENDENCY')
        self.assertEqual(len(self.f.rows('SELECT * FROM changes')), 1)

    def test_cross_change_cycle_is_rejected_by_real_revision_without_rewriting_old_definition(self):
        self.make_b()
        reference = self.reference(self.b, 'REPORT', 'task_completed')
        self.select(self.a)
        proposal = copy.deepcopy(self.f.data)
        proposal['tasks'][0]['external_dependencies'] = [reference]
        proposal['presentation'] = {'source': 'controlled cross-cycle presentation',
            'document': {k: v for k, v in proposal.items() if k != 'complexity'}}
        request = self.f.request(extra={'reason': 'Controlled attempt to add A SUM -> B REPORT -> A SUM cycle.', 'proposal': proposal})
        old = self.f.rows('SELECT * FROM tasks')
        with self.assertRaises(EvolveError) as caught:
            revise(self.f.root, request)
        self.assertEqual(caught.exception.code, 'DEPENDENCY_CYCLE')
        self.assertEqual(self.f.rows('SELECT * FROM tasks'), old)

    def start_blocked_report_check(self):
        path = self.f.root / 'test_report.py'
        path.write_text("from pathlib import Path\nimport time\nPath('.evolve-local/report-ready').write_text('ready')\n"
            "while not Path('.evolve-local/report-release').exists():\n    time.sleep(.02)\n" + path.read_text())
        self.make_b()
        self.finish_a_sum()
        self.select(self.b)
        request = self.f.request('REPORT', {'accepted_plan_digest': self.b['plan_digest'],
            'files': [{'path': 'report.py', 'expected_digest': None, 'content': fixture.REPORT}]})
        code = '''import json,sys
sys.path.insert(0,sys.argv[1])
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
try:
    print(json.dumps(implement(sys.argv[2],json.loads(sys.argv[3]))))
except EvolveError as error:
    print(json.dumps({'error':error.code,'committed':error.committed}))
'''
        process = subprocess.Popen([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'),
            str(self.f.root), json.dumps(request)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: self.stop_report_check(process) if process.poll() is None else None)
        deadline = time.monotonic() + 5
        while not (self.f.root / '.evolve-local/report-ready').exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue((self.f.root / '.evolve-local/report-ready').exists())
        return process

    def stop_report_check(self, process):
        (self.f.root / '.evolve-local/report-release').write_text('release')
        out, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, out + err)
        return json.loads(out)

    def test_real_parallel_claims_allow_unrelated_work_and_reject_mixed_cutoff(self):
        process = self.start_blocked_report_check()
        from evolve_core.package import digest
        self.select(self.b)
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('REPORT', observations={'report.py': digest((self.f.root / 'report.py').read_bytes())})
        self.assertEqual(caught.exception.code, 'CLAIM')
        # A separate Change targeting the same file also cannot steal B's claim.
        data = self.b_data()
        data.update(title='Competing same-file D')
        data['tasks'][0]['external_dependencies'] = []
        d = self.f.propose(data)
        self.select(d)
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('REPORT', {'report.py': fixture.REPORT})
        self.assertEqual(caught.exception.code, 'CLAIM')
        # A disjoint explicit file deliverable does progress while B's check runs.
        data.update(title='Unrelated concurrent C', scope=['c.txt'], required_checks=[])
        data['acceptance'][0]['text'] = 'c.txt contains the concurrent C literal.'
        data['spec'].update(goals=['Deliver the concurrent note C.'], behavior=['c.txt contains concurrent C followed by a newline.'],
                            test_decisions=['Read c.txt and compare the exact declared literal.'])
        data['tasks'][0].update(scope=['c.txt'], context_paths=[], required_checks=[])
        data['tasks'][0].update(completion='The declared literal note exists.', validation='Read c.txt and compare the literal.',
                               test_decision_refs=['spec.test_decisions/0'])
        c = self.f.propose(data)
        self.f.auth['paths'].append('c.txt')
        self.select(c)
        self.assertEqual(self.f.apply('REPORT', {'c.txt': 'concurrent C\n'})['outcome'], 'implemented')
        self.assertIsNone(process.poll())
        result = self.stop_report_check(process)
        self.assertEqual(result['error'], 'WORKSPACE_CHANGED')
        self.assertEqual((self.f.root / 'report.py').read_text(), fixture.REPORT)
        self.select(self.b)
        self.assertEqual(self.f.apply('REPORT')['outcome'], 'implemented')
        checked = self.f.verify('REPORT')
        self.assertEqual(checked['status'], 'passed')
        context = checked['verification_context']
        self.assertEqual(context['independent_isolation'], 'not_asserted')
        self.assertIn(c['change_id'], {row['change_id'] for row in context['workspace_work']})
        self.assertTrue(context['required_dependency_basis'])

    def test_upstream_cancel_during_real_consumer_check_cannot_commit_done(self):
        process = self.start_blocked_report_check()
        self.select(self.a)
        cancel_change(self.f.root, self.f.request(extra={'reason': 'Cancel A while B is checking; preserve all physical effects.'}))
        result = self.stop_report_check(process)
        self.assertEqual(result['error'], 'DEPENDENCY_CHANGED')
        self.select(self.b)
        self.assertEqual(self.f.context('REPORT')[3]['state'], 'in_progress')
        self.assertTrue(self.ready(self.b, 'REPORT')['unmet'])
        self.assertEqual((self.f.root / 'report.py').read_text(), fixture.REPORT)
        self.assertEqual(self.f.rows('SELECT * FROM resource_claims'), [])

    def test_task_completed_and_artifact_conditions_do_not_require_or_invent_verification(self):
        completed = self.reference(self.a, 'SUM', 'task_completed')
        self.make_b(completed)
        completed_plan = self.b
        self.select(self.a)
        self.f.apply('SUM', {'total.py': fixture.SUM})
        self.assertTrue(self.ready(completed_plan, 'REPORT')['ready'])
        artifact = self.reference(self.a, 'SUM', 'artifact_available')
        artifact['condition_ref'] = 'total.py'
        self.make_b(artifact)
        self.assertTrue(self.ready(self.b, 'REPORT')['ready'])
        self.assertEqual(self.f.rows('SELECT * FROM verifications'), [])
        (self.f.root / 'total.py').unlink()
        self.assertFalse(self.ready(self.b, 'REPORT')['ready'])
        self.assertFalse(self.ready(completed_plan, 'REPORT')['ready'])

    def test_real_upstream_revision_requires_rebinding_instead_of_silently_following_latest(self):
        self.make_b()
        b = self.b
        self.finish_a_sum()
        self.assertTrue(self.ready(b, 'REPORT')['ready'])
        self.select(self.a)
        proposal = copy.deepcopy(self.f.data)
        proposal['title'] = 'Display-only renamed upstream A'
        proposal['presentation'] = {'source': 'controlled real cosmetic upstream revision',
            'document': {key: value for key, value in proposal.items() if key != 'complexity'}}
        old = self.f.rows('SELECT * FROM verifications')
        result = revise(self.f.root, self.f.request(extra={'reason': 'Rename the presentation only.', 'proposal': proposal}))
        self.assertNotEqual(result['revision_id'], self.a['revision_id'])
        self.assertFalse(self.ready(b, 'REPORT')['ready'])
        self.assertEqual(self.f.rows('SELECT * FROM verifications'), old)

    def test_new_actual_upstream_failure_invalidates_consumer_without_erasing_old_pass(self):
        self.make_b()
        self.finish_a_sum()
        self.finish_b()
        old = self.f.rows('SELECT * FROM verifications')
        (self.f.root / 'total.py').write_text('def total(values):\n    return len(values)\n')
        self.select(self.a)
        failed = self.f.verify('SUM', failed_ac='sum')
        self.assertIn(failed['status'], ('failed', 'blocked'))
        self.assertTrue(self.ready(self.b, 'REPORT')['revalidation_required'])
        current = {row['id']: row for row in self.f.rows('SELECT * FROM verifications')}
        self.assertTrue(all(current[row['id']] == row for row in old))
        self.assertEqual((self.f.root / 'report.py').read_text(), fixture.REPORT)

    def test_malformed_conditions_and_unowned_paths_do_not_become_dependencies(self):
        original = self.reference(self.a, 'SUM')
        cases = [{**original, 'condition_kind': 'run_arbitrary_expression'},
                 {**original, 'condition_ref': {}}, {**original, 'unknown_meaning': 'ignored'},
                 {**original, 'condition_kind': 'artifact_available', 'condition_ref': 'other.py'}]
        for reference in cases:
            with self.subTest(reference=reference):
                with self.assertRaises(EvolveError) as caught:
                    self.make_b(reference)
                self.assertEqual(caught.exception.code, 'DEPENDENCY')
        self.assertEqual(len(self.f.rows('SELECT * FROM changes')), 1)

    def test_paused_consumer_rebinds_after_cancel_to_a_new_observed_producer_and_finishes(self):
        self.make_b()
        self.finish_a_sum()
        self.select(self.b)
        paused = self.f.apply('REPORT', {'report.py': fixture.REPORT}, pause={
            'reason': 'Controlled safe pause before report checks.', 'completed': ['Report file written.'],
            'remaining': ['Run original report checks and acceptance.'], 'next_steps': ['Continue after confirming the exact upstream.']})
        self.assertEqual(paused['outcome'], 'partial')
        self.select(self.a)
        cancel_change(self.f.root, self.f.request(extra={'reason': 'Explicitly transfer the producer responsibility to C.'}))
        data = copy.deepcopy(self.f.data)
        data.update(title='Replacement producer C', scope=['total.py'], acceptance=[data['acceptance'][0]],
                    tasks=[data['tasks'][0]])
        c = self.f.propose(data)
        self.select(c)
        source = (self.f.root / 'total.py').read_bytes()
        adopted = self.f.apply('SUM')
        self.assertEqual(adopted['outcome'], 'implemented')
        self.assertEqual((self.f.root / 'total.py').read_bytes(), source)
        self.assertEqual(self.f.verify('SUM')['status'], 'passed')
        reference = self.reference(c, 'SUM')
        proposal = self.b_data(reference)
        proposal['presentation'] = {'source': 'controlled exact consumer rebinding',
            'document': {key: value for key, value in proposal.items() if key != 'complexity'}}
        self.select(self.b)
        revised = revise(self.f.root, self.f.request(extra={'reason': 'Replace only cancelled A with verified C.', 'proposal': proposal}))
        self.assertEqual(revised['outcome'], 'revised')
        self.b.update({key: revised[key] for key in ('revision_id', 'plan_digest', 'definition_digest')})
        accepted = revise(self.f.root, self.f.request(extra={'reason': 'Accept the exact presented C prerequisite.',
            'proposal': proposal, 'approval': {'candidate_digest': revised['candidate_digest'],
                'source': 'controlled concrete rebinding confirmation', 'text': 'Accept only the fixed C reference; retain original report behavior and tests.'}}))
        self.assertEqual(accepted['outcome'], 'accepted')
        self.assertEqual(self.f.apply('REPORT')['outcome'], 'implemented')
        self.assertEqual(self.f.verify('REPORT')['status'], 'passed')
        verified = self.f.verify()
        self.assertEqual(verified['status'], 'passed')
        self.assertEqual(self.f.close(verified)['outcome'], 'archived')
        self.select(c)
        verified = self.f.verify()
        self.assertEqual(verified['status'], 'passed')
        self.assertEqual(self.f.close(verified)['outcome'], 'archived')
