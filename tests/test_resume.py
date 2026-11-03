"""Normal pause and fresh-process continuation preserve scope and actual work."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
from evolve_core.plans import propose
from evolve_core.resume import resume_view
from evolve_core.store import Store


class ResumeTests(WorkflowFixture):
    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def pause(self, *, authorize_checks=True):
        request = self.apply_request()
        request['input']['pause'] = {'completed': ['Wrote the sum candidate'],
            'remaining': ['Run original tests, review and verify'], 'next_steps': ['Re-read current files and run original checks'],
            'reason': 'Explicit normal conversation pause before checks'}
        if not authorize_checks:
            request['authorization'] = {**self.auth, 'effect_kinds': ['project_records', 'business_files']}
        with patch('evolve_core.check_reuse.run_check', side_effect=AssertionError('Pause must not execute checks')):
            result = implement(self.root, request)
        row = self.rows('SELECT * FROM phase_runs WHERE id=?', (result['run_id'],))[0]
        return result, {'run_id': row['id'], 'result_digest': row['result_digest']}

    def test_pause_completes_only_the_run_and_releases_safe_claims_without_checks(self):
        result, ref = self.pause(authorize_checks=False)
        self.assertEqual(result['outcome'], 'partial')
        self.assertEqual(result['checks'], 'not_run')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (ref['run_id'],))[0]['status'], 'completed')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)
        self.assertIn('sum(values)', (self.root / 'total.py').read_text())

    def test_resume_restores_original_plan_progress_authorization_without_writes(self):
        result, ref = self.pause()
        before = self.snapshot()
        view = resume_view(self.root)
        self.assertEqual(view['selection'], 'selected')
        self.assertEqual(view['task_result']['progress'], result['progress'])
        self.assertEqual(view['project']['changes'][0]['plan']['digest'], self.plan['plan_digest'])
        self.assertEqual(view['runs'][-1]['authorization']['text'], self.auth['text'])
        self.assertEqual(view['runs'][-1]['result_digest'], ref['result_digest'])
        self.assertFalse(view['authorization_granted'])
        self.assertEqual(view['suggested_action'], 'apply')
        self.assertEqual(view['workspace_observation']['scope_changes'], [])
        self.assertEqual(self.snapshot(), before)

    def test_fresh_process_continues_with_a_new_run_without_fake_recovery(self):
        result, ref = self.pause()
        before = self.rows('SELECT * FROM phase_runs WHERE id=?', (ref['run_id'],))[0]
        request = self.apply_request()
        request['input']['continuation'] = ref
        code = ('import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                'from evolve_core.apply import implement;print(json.dumps(implement(Path(sys.argv[2]),json.load(sys.stdin))))')
        process = subprocess.run([sys.executable, '-B', '-c', code, str(Path(__file__).resolve().parents[1] / 'runtime'), str(self.root)],
                                 input=json.dumps(request), text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 0, process.stderr)
        continued = json.loads(process.stdout)
        self.assertEqual(continued['outcome'], 'implemented')
        self.assertNotEqual(continued['run_id'], result['run_id'])
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'done')
        self.assertEqual(self.rows('SELECT * FROM phase_runs WHERE id=?', (ref['run_id'],))[0], before)
        self.assertEqual(self.rows('SELECT purpose FROM source_runs WHERE run_id=?', (continued['run_id'],))[0]['purpose'], 'normal_continuation')
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM phase_runs WHERE action='maintain'")[0]['n'], 0)

    def test_continuation_cannot_add_effects_absent_from_the_original_grant(self):
        _, ref = self.pause(authorize_checks=False)
        before = (self.root / 'total.py').read_bytes()
        request = self.apply_request()
        request['input']['continuation'] = ref
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'AUTHORIZATION')
        self.assertEqual((self.root / 'total.py').read_bytes(), before)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)

    def test_revoked_source_grant_is_visible_and_cannot_be_reused(self):
        _, ref = self.pause()
        row = self.rows('SELECT request_id FROM phase_runs WHERE id=?', (ref['run_id'],))[0]
        store = Store(self.root)
        try:
            with store.transaction():
                store.event(ref['run_id'], 'authorization_revoked', {'request_id': row['request_id']})
        finally:
            store.close()
        view = resume_view(self.root, self.plan['change_id'])
        self.assertTrue(view['runs'][-1]['authorization_revoked'])
        request = self.apply_request()
        request['input']['continuation'] = ref
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'AUTHORIZATION')

    def test_resume_reports_external_drift_without_registering_or_overwriting_it(self):
        self.pause()
        (self.root / 'total.py').write_text('user content requiring inspection')
        before = self.snapshot()
        view = resume_view(self.root, self.plan['change_id'])
        self.assertEqual(view['suggested_action'], 'inspect_workspace_change')
        self.assertEqual(view['workspace_observation']['scope_changes'][0]['source'], 'external_or_unknown')
        self.assertEqual(self.snapshot(), before)

    def test_multiple_unfinished_targets_are_not_resolved_by_recency(self):
        input_data = json.loads(self.rows("SELECT input_json FROM phase_runs WHERE action='propose'")[0]['input_json'])['request']['input']
        input_data['title'] = 'A second explicit work item'
        propose(self.root, self.request(input_data))
        before = self.snapshot()
        view = resume_view(self.root)
        self.assertEqual(view['selection'], 'required')
        self.assertEqual(len(view['candidates']), 2)
        self.assertEqual(self.snapshot(), before)

    def test_explicit_change_still_exposes_global_unfinished_configuration(self):
        store = Store(self.root)
        try:
            run_id, _ = store.start(self.request({}), action='init', method='connect', owner='evolve-init')
        finally:
            store.close()
        before = self.snapshot()
        view = resume_view(self.root, self.plan['change_id'])
        self.assertEqual(view['suggested_action'], 'inspect_original_owner')
        self.assertIn(run_id, [r['id'] for r in view['project']['pending_runs']])
        self.assertEqual(self.snapshot(), before)

    def test_resume_keeps_real_failed_checks_and_their_evidence(self):
        failed = implement(self.root, self.apply_request('def total(values):\n    return 0\n'))
        self.assertEqual(failed['outcome'], 'checks_not_passed')
        before = self.snapshot()
        view = resume_view(self.root, self.plan['change_id'])
        last = view['runs'][-1]
        self.assertEqual(last['result']['task_checks'][0]['status'], 'failed')
        self.assertTrue(last['evidence'])
        self.assertEqual(self.snapshot(), before)

    def test_tampered_sealed_result_is_reported_without_repairing_it(self):
        _, ref = self.pause()
        store = Store(self.root)
        try:
            with store.transaction() as connection:
                connection.execute('UPDATE phase_runs SET result_json=? WHERE id=?', ('{}', ref['run_id']))
        finally:
            store.close()
        before = self.snapshot()
        with self.assertRaises(EvolveError) as caught:
            resume_view(self.root, self.plan['change_id'])
        self.assertEqual(caught.exception.code, 'RUN_RESULT_INVALID')
        self.assertEqual(self.snapshot(), before)

    def test_public_resume_in_a_fresh_process_is_a_pure_query(self):
        self.pause()
        before = self.snapshot()
        runtime = Path(__file__).resolve().parents[1] / 'runtime/evolve.py'
        for action in ('resume', 'next'):
            result = subprocess.run([sys.executable, '-B', str(runtime), '--project', str(self.root), action,
                                     self.plan['change_id'], '--owner', 'evolve-workflow'],
                                    text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            response = json.loads(result.stdout)
            self.assertFalse(response['data']['committed'])
            self.assertEqual(response['data']['context']['selection'], 'selected')
            self.assertEqual(self.snapshot(), before)

    def test_analysis_resume_keeps_source_authority_and_unfinished_questions(self):
        from test_analysis import InvestigationTests
        from evolve_core.analysis import investigate
        fixture = InvestigationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.connected()
        result = investigate(fixture.root, fixture.payload())
        before = {p.relative_to(fixture.root).as_posix(): p.read_bytes() for p in fixture.root.rglob('*') if p.is_file()}
        view = resume_view(fixture.root, result['run_id'])
        self.assertEqual(view['target_kind'], 'analysis')
        self.assertEqual(view['runs'][0]['authorization']['text'], fixture.auth['text'])
        self.assertEqual(view['project']['analyses'][0]['analysis']['answer_status'], 'partial')
        self.assertTrue(view['project']['analyses'][0]['analysis']['remaining_questions'])
        self.assertEqual({p.relative_to(fixture.root).as_posix(): p.read_bytes() for p in fixture.root.rglob('*') if p.is_file()}, before)
