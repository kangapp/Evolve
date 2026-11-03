"""Actual failed/successful work produces experience; later tasks consume it."""
import json
from pathlib import Path
import subprocess
import sys
import uuid
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
from evolve_core.learning import learn, learning_status, search
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.reading import history_snapshot
from evolve_core.resume import resume_view
from evolve_core.store import Store


class LearningTests(WorkflowFixture):
    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def ref(self, run_id, *, evidence=False):
        row = self.rows('SELECT * FROM phase_runs WHERE id=?', (run_id,))[0]
        result = {'run_id': run_id, 'result_digest': row['result_digest']}
        if evidence:
            result['evidence_ids'] = [r['id'] for r in self.rows('SELECT id FROM evidence WHERE source_run_id=?', (run_id,))]
        return result

    def request_learning(self, data):
        return {**self.identity(), 'request_id': str(uuid.uuid4()),
                'authorization': {'source': 'controlled learning fixture', 'text': 'Record project-local learning only',
                                  'effect_kinds': ['project_records']}, 'input': data}

    def write(self, data, method='record'):
        return learn(self.root, self.request_learning(data), method=method)

    def produce(self, confidence='observed'):
        failed = implement(self.root, self.apply_request('def total(values):\n    return 0\n'))
        self.assertEqual(failed['outcome'], 'checks_not_passed')
        successful = implement(self.root, self.apply_request())
        self.assertEqual(successful['outcome'], 'implemented')
        self.failed, self.successful = self.ref(failed['run_id'], evidence=True), self.ref(successful['run_id'], evidence=True)
        data = {'experience': {'topic': 'Arithmetic total regression', 'problem': 'Constant or count results differ from independent sums',
                'cause': {'statement': 'Observed fixture implementations counted values or returned zero instead of summing', 'confidence': confidence},
                'advice': 'Compare sum behavior against unchanged independent literal examples before closing the task',
                'applicability': 'Integer sum functions in the local Python fixture', 'version_context': sys.version.split()[0] + '; controlled local fixture',
                'observer': 'controlled source and actual check observer', 'scope': ['local integer arithmetic'],
                'exclusions': ['Not a production data rule or proof for all numeric types'], 'tags': ['arithmetic', 'sum'],
                'limitations': ['Evidence covers only the existing three independent literal examples']},
                'sources': [self.failed, self.successful]}
        self.record_request = self.request_learning(data)
        result = learn(self.root, self.record_request, method='record')
        self.experience_ref = self.ref(result['run_id'])
        return result

    def second_task(self):
        # This is a new real regression; prior Task and source run stay complete.
        (self.root / 'total.py').write_text('def total(values):\n    return len(values)\n')
        plan = json.loads(self.rows("SELECT input_json FROM phase_runs WHERE action='propose' ORDER BY started_at LIMIT 1")[0]['input_json'])['request']['input']
        plan['title'] = 'Second similar arithmetic regression'
        self.plan = propose(self.root, {**self.identity(), 'request_id': str(uuid.uuid4()), 'authorization': self.auth, 'input': plan})

    def decide(self, decision='adopted', observation=None, influence=None):
        result = self.write({'kind': 'decision', 'experience_ref': self.experience_ref,
            'search_ref': observation or search(self.root, 'arithmetic')['search_ref'], 'decision': decision,
            'change_id': self.plan['change_id'], 'revision_id': self.plan['revision_id'], 'definition_digest': self.plan['definition_digest'],
            'observed_files': {'total.py': digest((self.root / 'total.py').read_bytes())},
            **({'influence': influence} if influence is not None else {}),
            'applicability_basis': 'Read the new count implementation and unchanged literal expectations; the narrow fixture scope matches',
            'limitations': ['Still a project-local suggestion, not formal authority']}, 'review')
        return self.ref(result['run_id'])

    def give_feedback(self, decision, outcome='unknown', source=None):
        if source is None:
            applied = implement(self.root, self.apply_request())
            source = self.ref(applied['run_id'], evidence=True)
        return self.write({'kind': 'feedback', 'decision_ref': decision, 'outcome': outcome, 'result_source': source,
                           'basis': 'Actual current check result is linked; any benefit is a bounded observer assessment',
                           'limitations': ['Task success alone does not prove causal benefit for every cited suggestion']}, 'review')

    def state(self, target='active', **extra):
        current = search(self.root, 'arithmetic')['results'][0]
        return self.write({'kind': 'state', 'experience_ref': self.experience_ref, 'expected_state_ref': current['state_ref'],
                           'state': target, 'basis': 'Reviewed the recorded local conditions, raw evidence and explicit limitations',
                           'sources': [self.successful], 'reviewed_counterexamples': [], **extra}, 'review')

    def test_actual_prior_work_produces_a_candidate_without_formal_or_business_writes(self):
        result = self.produce()
        self.assertEqual(result['experience']['state'], 'candidate')
        before = self.snapshot()
        found = search(self.root, 'arithmetic')['results'][0]
        self.assertEqual(found['experience_ref'], self.experience_ref)
        self.assertEqual(found['state'], 'candidate')
        self.assertFalse(found['formal_rule'])
        self.assertFalse(found['modification_authorization'])
        self.assertEqual(len(found['sources']), 2)
        self.assertTrue(found['sources'][0]['evidence'])
        self.assertFalse((self.root / 'evolve/project.md').exists())
        self.assertEqual(self.snapshot(), before)

    def test_new_task_records_retrieval_adoption_and_actual_unknown_effect_separately(self):
        self.produce()
        self.second_task()
        decision = self.decide()
        current = search(self.root, 'arithmetic')['results'][0]
        self.assertEqual(current['applications'][0]['effect'], 'unknown')
        self.assertNotIn('feedback', current['applications'][0])
        feedback = self.give_feedback(decision)
        current = search(self.root, 'arithmetic')['results'][0]
        self.assertEqual(current['applications'][0]['feedback']['outcome'], 'unknown')
        self.assertEqual(current['state'], 'candidate')
        self.assertEqual(feedback['attribution'], 'observer_assessment_not_inferred_from_task_status')

    def test_repeated_decisions_and_passed_tasks_do_not_promote_candidate(self):
        self.produce()
        self.second_task()
        first = self.decide()
        self.decide('not_used')
        self.give_feedback(first, 'helped')
        current = search(self.root, 'arithmetic')['results'][0]
        self.assertEqual(len(current['applications']), 2)
        self.assertEqual(current['state'], 'candidate')

    def test_rejected_retrieval_cannot_claim_adoption_benefit(self):
        self.produce()
        self.second_task()
        decision = self.decide('rejected')
        with self.assertRaises(EvolveError) as caught:
            self.give_feedback(decision, 'helped')
        self.assertEqual(caught.exception.code, 'LEARNING_FEEDBACK')
        self.assertEqual(search(self.root, 'arithmetic')['results'][0]['applications'][0]['decision'], 'rejected')

    def test_exact_old_result_replay_remains_idempotent_after_state_review(self):
        original = self.produce()
        self.state()
        count = self.rows('SELECT COUNT(*) n FROM phase_runs')[0]['n']
        self.assertEqual(learn(self.root, self.record_request, method='record'), original)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM phase_runs')[0]['n'], count)

    def test_hypothesis_is_not_activated_by_references_or_positive_test_evidence(self):
        self.produce(confidence='hypothesis')
        with self.assertRaises(EvolveError) as caught:
            self.state()
        self.assertEqual(caught.exception.code, 'LEARNING_REVIEW_REQUIRED')
        self.assertEqual(search(self.root, 'arithmetic')['results'][0]['state'], 'candidate')

    def test_state_review_preserves_the_original_content_version(self):
        self.produce()
        self.state()
        found = search(self.root, 'arithmetic')['results'][0]
        self.assertEqual(found['state'], 'active')
        self.assertEqual(found['experience_ref'], self.experience_ref)
        self.assertNotEqual(found['state_ref'], self.experience_ref)
        self.assertFalse(found['formal_rule'])

    def test_counterexample_requires_review_and_old_green_cannot_resolve_it(self):
        self.produce()
        self.state()
        self.second_task()
        decision = self.decide()
        failed = implement(self.root, self.apply_request('def total(values):\n    return 0\n'))
        feedback = self.give_feedback(decision, 'counterexample', self.ref(failed['run_id'], evidence=True))
        found = search(self.root, 'arithmetic')['results'][0]
        self.assertEqual(found['state'], 'needs_review')
        self.assertTrue(found['pending_counterexamples'])
        with self.assertRaises(EvolveError) as caught:
            self.decide()
        self.assertEqual(caught.exception.code, 'LEARNING_REVIEW_REQUIRED')
        with self.assertRaises(EvolveError) as caught:
            self.state(reviewed_counterexamples=[feedback['run_id']])
        self.assertEqual(caught.exception.code, 'LEARNING_REVIEW_REQUIRED')
        new = implement(self.root, self.apply_request())
        self.state(reviewed_counterexamples=[feedback['run_id']], sources=[self.ref(new['run_id'], evidence=True)])
        self.assertEqual(search(self.root, 'arithmetic')['results'][0]['state'], 'active')

    def test_stale_search_is_not_silently_used_after_state_change(self):
        self.produce()
        observation = search(self.root, 'arithmetic')['search_ref']
        self.state()
        self.second_task()
        with self.assertRaises(EvolveError) as caught:
            self.decide(observation=observation)
        self.assertEqual(caught.exception.code, 'LEARNING_RETRIEVAL')

    def test_feedback_cannot_point_to_a_different_work_or_predecision_outcome(self):
        self.produce()
        self.second_task()
        decision = self.decide()
        with self.assertRaises(EvolveError) as caught:
            self.give_feedback(decision, source=self.successful)
        self.assertEqual(caught.exception.code, 'LEARNING_FEEDBACK')

    def test_second_feedback_cannot_overwrite_the_first_observation(self):
        self.produce()
        self.second_task()
        decision = self.decide()
        first = self.give_feedback(decision)
        with self.assertRaises(EvolveError) as caught:
            self.give_feedback(decision, 'helped', first['result_source'])
        self.assertEqual(caught.exception.code, 'LEARNING_FEEDBACK')
        self.assertEqual(search(self.root, 'arithmetic')['results'][0]['applications'][0]['feedback']['run_id'], first['run_id'])

    def test_no_new_learning_requires_actual_review_and_does_not_create_experience(self):
        applied = implement(self.root, self.apply_request())
        ref = self.ref(applied['run_id'])
        with history_snapshot(self.root) as (connection, _):
            self.assertEqual(learning_status(connection, ref['run_id'])['status'], 'pending')
        self.write({'source': ref, 'checked_basis': 'Read the actual narrow output and found no reusable new finding',
                    'observer': 'controlled reviewer'}, 'retro')
        with history_snapshot(self.root) as (connection, _):
            self.assertEqual(learning_status(connection, ref['run_id'])['status'], 'no_new_learning')
        self.assertEqual(search(self.root, 'arithmetic')['outcome'], 'no_match')

    def test_missing_source_is_an_error_not_a_genuine_empty_search(self):
        self.produce()
        store = Store(self.root)
        try:
            with store.transaction() as connection:
                connection.execute('UPDATE phase_runs SET result_json=? WHERE id=?', ('{}', self.failed['run_id']))
        finally:
            store.close()
        before = self.snapshot()
        with self.assertRaises(EvolveError) as caught:
            search(self.root, 'arithmetic')
        self.assertEqual(caught.exception.code, 'LEARNING_SOURCE')
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_optional_experience_does_not_hide_main_resume_or_formal_context(self):
        result = self.produce()
        store = Store(self.root)
        try:
            with store.transaction() as connection:
                connection.execute('UPDATE phase_runs SET result_json=? WHERE id=?', ('{}', result['run_id']))
        finally:
            store.close()
        before = self.snapshot()
        view = resume_view(self.root, self.plan['change_id'])
        self.assertEqual(view['selection'], 'selected')
        self.assertEqual(view['runs'][-1]['learning']['status'], 'unavailable')
        self.assertTrue(view['project']['changes'][0]['plan']['text'])
        self.assertEqual(self.snapshot(), before)

    def test_pure_search_in_a_fresh_cli_process_does_not_write_or_default_to_record(self):
        self.produce()
        before = self.snapshot()
        runtime = Path(__file__).resolve().parents[1] / 'runtime/evolve.py'
        process = subprocess.run([sys.executable, '-B', str(runtime), '--project', str(self.root), 'learn', 'arithmetic',
                                  '--method', 'search', '--owner', 'evolve-learn'], text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout)
        self.assertFalse(result['data']['committed'])
        self.assertEqual(result['data']['outcome'], 'matched')
        self.assertEqual(self.snapshot(), before)

    def test_learning_does_not_supply_missing_business_authorization(self):
        self.produce()
        self.second_task()
        self.decide()
        request = self.apply_request()
        request['authorization'] = self.request_learning({})['authorization']
        before = (self.root / 'total.py').read_bytes()
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'AUTHORIZATION')
        self.assertEqual((self.root / 'total.py').read_bytes(), before)

    def test_state_chain_uses_explicit_predecessors_instead_of_wall_clock_order(self):
        self.produce()
        changed = self.state()
        store = Store(self.root)
        try:
            with store.transaction() as connection:
                connection.execute('UPDATE phase_runs SET started_at=? WHERE id=?', ('1900-01-01T00:00:00+00:00', changed['run_id']))
        finally:
            store.close()
        self.assertEqual(search(self.root, 'arithmetic')['results'][0]['state'], 'active')

    def test_actual_verification_result_can_support_feedback_for_the_same_definition(self):
        from evolve_core.verify import verify
        self.produce()
        self.second_task()
        decision = self.decide()
        implement(self.root, self.apply_request())
        verified = verify(self.root, self.verification_request())
        feedback = self.give_feedback(decision, 'helped', self.ref(verified['run_id'], evidence=True))
        self.assertEqual(feedback['outcome'], 'helped')

    def test_same_work_result_observed_before_the_adoption_is_not_postadoption_feedback(self):
        self.produce()
        self.second_task()
        before = implement(self.root, self.apply_request('def total(values):\n    return 0\n'))
        decision = self.decide()
        with self.assertRaises(EvolveError) as caught:
            self.give_feedback(decision, source=self.ref(before['run_id'], evidence=True))
        self.assertEqual(caught.exception.code, 'LEARNING_FEEDBACK')

    def test_foreign_evidence_id_does_not_become_source_support(self):
        self.produce()
        bad = json.loads(json.dumps(self.record_request['input']))
        bad['sources'][0]['evidence_ids'] = self.successful['evidence_ids']
        with self.assertRaises(EvolveError) as caught:
            self.write(bad)
        self.assertEqual(caught.exception.code, 'LEARNING_SOURCE')
        self.assertEqual(search(self.root, 'arithmetic')['matched_count'], 1)

    def test_retired_content_and_feedback_remain_readable_without_being_recommended(self):
        self.produce()
        found = search(self.root, 'arithmetic')['results'][0]
        self.write({'experience_ref': self.experience_ref, 'expected_state_ref': found['state_ref'],
                    'basis': 'Retire this narrow suggestion while preserving its history', 'sources': [self.successful]}, 'disable')
        found = search(self.root, 'arithmetic')['results'][0]
        self.assertEqual(found['state'], 'retired')
        self.assertFalse(found['recommendation_allowed'])
        self.assertEqual(found['experience_ref'], self.experience_ref)
        self.second_task()
        with self.assertRaises(EvolveError) as caught:
            self.decide()
        self.assertEqual(caught.exception.code, 'LEARNING_REVIEW_REQUIRED')

    def test_no_new_learning_cannot_stand_for_an_unexamined_result(self):
        applied = implement(self.root, self.apply_request())
        with self.assertRaises(EvolveError) as caught:
            self.write({'source': self.ref(applied['run_id']), 'observer': 'controlled reviewer'}, 'retro')
        self.assertEqual(caught.exception.code, 'LEARNING_INPUT')
        with history_snapshot(self.root) as (connection, _):
            self.assertEqual(learning_status(connection, applied['run_id'])['status'], 'pending')

    def test_formal_knowledge_is_not_hidden_by_experience_rank_or_query(self):
        from evolve_core.knowledge import propose_baseline, apply_baseline
        self.produce()
        content = '# Local rules\n\nPreserve independent test expectations.\n'
        proposal = propose_baseline(self.root, self.request({'path': 'RULES.md', 'expected_digest': None, 'content': content,
            'presentation': {'source': 'controlled explicit baseline presentation', 'text': content}}))
        request = self.request({'proposal_id': proposal['proposal_id'], 'approval': {
            'proposal_version': proposal['proposal_version'], 'candidate_digest': proposal['candidate_digest'],
            'expected_digest': proposal['expected_digest'], 'source': 'controlled specific approval', 'text': 'Approve precisely the presented local rule fixture'}})
        request['authorization'] = {'source': 'controlled explicit knowledge approval', 'text': 'Apply exactly the approved local rule fixture',
                                    'effect_kinds': ['project_records', 'knowledge'], 'paths': ['RULES.md']}
        apply_baseline(self.root, request)
        before = self.snapshot()
        found = search(self.root, 'zzzxq_missing_context_987')
        self.assertEqual(found['outcome'], 'no_match')
        self.assertEqual(found['formal_context'][0]['path'], 'RULES.md')
        self.assertEqual(found['formal_context'][0]['confirmation'], 'approved_version')
        self.assertEqual(self.snapshot(), before)

    def test_identical_new_request_does_not_reactivate_a_retired_experience(self):
        self.produce()
        found = search(self.root, 'arithmetic')['results'][0]
        self.write({'experience_ref': self.experience_ref, 'expected_state_ref': found['state_ref'],
                    'basis': 'Retired controlled fixture', 'sources': [self.successful]}, 'disable')
        with self.assertRaises(EvolveError) as caught:
            self.write(self.record_request['input'])
        self.assertEqual(caught.exception.code, 'LEARNING_DUPLICATE')
        self.assertEqual(search(self.root, 'arithmetic')['matched_count'], 1)
        self.assertEqual(search(self.root, 'arithmetic')['results'][0]['state'], 'retired')

    def test_committed_result_survives_a_lost_receipt_and_exact_retry(self):
        self.produce()
        data = json.loads(json.dumps(self.record_request['input']))
        data['experience']['topic'] = 'Receipt continuity observation'
        request = self.request_learning(data)
        original = Store.finish
        def fail_receipt(store, *args, **kwargs):
            original(store, *args, **kwargs)
            raise OSError('controlled lost receipt after committed result')
        with patch.object(Store, 'finish', fail_receipt):
            with self.assertRaises(EvolveError) as caught:
                learn(self.root, request, method='record')
        self.assertEqual(caught.exception.code, 'LEARNING_INCOMPLETE')
        self.assertTrue(caught.exception.committed)
        count = self.rows('SELECT COUNT(*) n FROM phase_runs')[0]['n']
        replay = learn(self.root, request, method='record')
        self.assertEqual(replay['outcome'], 'experience_recorded')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM phase_runs')[0]['n'], count)

    def test_real_exit_preserves_draft_and_recovery_does_not_create_experience(self):
        from evolve_core.recover import recover
        self.produce()
        data = json.loads(json.dumps(self.record_request['input']))
        data['experience']['topic'] = 'pending-marker-abc'
        request = self.request_learning(data)
        child = ("import os,sys,json;from pathlib import Path;from unittest.mock import patch;"
                 "sys.path.insert(0,sys.argv[1]);from evolve_core.learning import learn;from evolve_core.store import Store;"
                 "context=patch.object(Store,'finish',side_effect=lambda *a,**k:os._exit(37));context.start();"
                 "learn(Path(sys.argv[2]),json.load(sys.stdin),method='record')")
        process = subprocess.run([sys.executable, '-B', '-c', child, str(Path(__file__).resolve().parents[1] / 'runtime'), str(self.root)],
                                 input=json.dumps(request), text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 37, process.stdout + process.stderr)
        original = self.rows('SELECT * FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]
        self.assertEqual(original['status'], 'started')
        found = search(self.root, 'pending-marker-abc')
        self.assertEqual(found['outcome'], 'incomplete')
        self.assertIn(original['id'], [r['run_id'] for r in found['incomplete_records']])
        result = recover(self.root, self.request({'run_id': original['id']}))
        self.assertFalse(result['business_commands_run'])
        found = search(self.root, 'pending-marker-abc')
        self.assertEqual(found['outcome'], 'incomplete')
        self.assertEqual(found['results'], [])
        self.assertEqual(found['incomplete_records'][0]['run_status'], 'interrupted')

    def test_fresh_resume_restores_adopted_version_and_decision_without_claiming_new_learning(self):
        self.produce()
        self.second_task()
        decision = self.decide()
        request = self.apply_request()
        request['input']['pause'] = {'completed': ['Saved sum candidate'], 'remaining': ['Run checks'],
                                     'next_steps': ['Read facts in new conversation'], 'reason': 'Controlled normal pause'}
        implement(self.root, request)
        before = self.snapshot()
        view = resume_view(self.root, self.plan['change_id'])
        adopted = view['learning_context']['applications'][0]
        self.assertEqual(adopted['experience_ref'], self.experience_ref)
        self.assertEqual(adopted['decision']['decision_ref'], decision)
        self.assertEqual(adopted['decision']['decision'], 'adopted')
        self.assertEqual(adopted['decision']['effect'], 'unknown')
        self.assertEqual(view['runs'][-1]['learning']['status'], 'pending')
        self.assertEqual(self.snapshot(), before)

    def test_new_archive_time_cannot_turn_old_observation_into_fresh_counterexample_support(self):
        from evolve_core.analysis import investigate
        self.produce()
        self.state()
        self.second_task()
        decision = self.decide()
        failed = implement(self.root, self.apply_request('def total(values):\n    return 0\n'))
        counter = self.give_feedback(decision, 'counterexample', self.ref(failed['run_id'], evidence=True))
        old = self.rows('SELECT * FROM evidence WHERE source_run_id=?', (self.successful['run_id'],))[0]
        raw = self.rows('SELECT content FROM blobs WHERE digest=?', (old['content_digest'],))[0]['content'].decode()
        observation = investigate(self.root, {**self.identity(), 'request_id': str(uuid.uuid4()),
            'authorization': self.request_learning({})['authorization'], 'input': {
                'question': 'What did the old saved check report?', 'scope': ['total.py'],
                'business_effect': 'read_only', 'record_intent': 'record', 'sources': [{
                    'id': 'OLD', 'kind': 'observation', 'object': 'Historical check output', 'version': self.successful['result_digest'],
                    'observer': old['observer'], 'method': old['method'], 'observed_at': old['observed_at'],
                    'content': raw, 'limitations': ['Historical observation before the counterexample; not a new execution']}],
                'analysis': {'observations': [{'local_key': 'F1', 'statement': 'The old saved command passed at its original time', 'sources': ['OLD']}],
                    'hypotheses': [], 'answer_status': 'answered', 'conclusion': 'Only the historical check is known here',
                    'coverage': ['One historical output'], 'limitations': ['No current recheck'], 'remaining_questions': [], 'next_steps': []}}})
        with self.assertRaises(EvolveError) as caught:
            self.state(reviewed_counterexamples=[counter['run_id']], sources=[self.ref(observation['run_id'], evidence=True)])
        self.assertEqual(caught.exception.code, 'LEARNING_REVIEW_REQUIRED')
        self.assertEqual(search(self.root, 'arithmetic')['results'][0]['state'], 'needs_review')

    def test_adoption_summary_preserves_specific_influence_and_pending_feedback(self):
        from evolve_core.learning import work_learning
        self.produce()
        self.second_task()
        influence = {'description': 'Keep the three literal sum examples as the acceptance oracle.',
                     'affected_items': ['unit', 'test_total.py:test_values']}
        decision = self.decide(influence=influence)
        store = Store(self.root)
        try:
            before = work_learning(store.connection, self.plan['change_id'])
        finally:
            store.close()
        self.assertEqual(before['consumption']['feedback_pending'], [decision['run_id']])
        self.assertEqual(before['applications'][0]['decision']['influence'], influence)
        self.give_feedback(decision, 'unknown')
        store = Store(self.root)
        try:
            after = work_learning(store.connection, self.plan['change_id'])
        finally:
            store.close()
        self.assertFalse(after['consumption']['feedback_pending'])
        self.assertEqual(after['consumption']['feedback'][0]['outcome'], 'unknown')
        self.assertEqual(after['consumption']['feedback'][0]['influence'], influence)

    def test_legacy_decision_has_no_fabricated_plan_influence(self):
        from evolve_core.learning import work_learning
        self.produce()
        self.second_task()
        decision = self.decide()
        store = Store(self.root)
        try:
            context = work_learning(store.connection, self.plan['change_id'])
        finally:
            store.close()
        self.assertEqual(context['consumption']['influence_not_recorded'], [decision['run_id']])
        self.assertNotIn('influence', context['applications'][0]['decision'])

    def test_adoption_with_explicit_but_empty_affected_items_is_rejected(self):
        self.produce()
        self.second_task()
        with self.assertRaises(EvolveError) as caught:
            self.decide(influence={'description': 'Claimed adoption without identifying any effect.', 'affected_items': []})
        self.assertEqual(caught.exception.code, 'LEARNING_INPUT')
