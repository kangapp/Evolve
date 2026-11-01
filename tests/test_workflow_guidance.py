"""Public CLI readiness, phase handoff and repair over real temporary project records."""
import json
from pathlib import Path
import subprocess
import sys

from workflow_fixture import WorkflowFixture

ROOT = Path(__file__).resolve().parents[1]


class WorkflowGuidanceTests(WorkflowFixture):
    def cli(self, action='status', method=None, data=None, *, ok=True, extra=(), target=None):
        argv = [sys.executable, '-B', str(ROOT / 'runtime/evolve.py'), '--project', str(self.root), action]
        if method:
            argv += ['--method', method]
        if target:
            argv += [target]
        argv += list(extra)
        payload = None
        if data is not None:
            argv += ['--request', '-']
            payload = json.dumps({'authorization': self.auth, 'input': data})
        process = subprocess.run(argv, input=payload, capture_output=True, text=True, timeout=30)
        response = json.loads(process.stdout)
        self.assertEqual(response['ok'], ok, response)
        return response

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def test_missing_check_index_is_visible_without_any_query_writes(self):
        (self.root / '.evolve-local/control/checks.json').unlink()
        before = self.snapshot()
        result = self.cli()
        checks = result['data']['readiness']['actions']['checks']
        self.assertEqual(checks['status'], 'blocked')
        self.assertIn('checks.json', json.dumps(checks))
        self.assertEqual(result['workflow']['next_steps'][0]['owner_skill'], 'evolve-maintain')
        self.assertEqual(self.snapshot(), before)

    def test_implementation_preflight_preserves_task_state_when_protection_is_missing(self):
        (self.root / '.evolve-local/control/checks.json').unlink()
        before = self.snapshot()
        result = self.cli('apply', 'implement', {'change_id': self.plan['change_id'],
            'accepted_plan_digest': self.plan['plan_digest'], 'files': []}, ok=False)
        self.assertEqual(result['error']['code'], 'PROTECTION_UNKNOWN')
        self.assertTrue(result['error']['next_steps'])
        self.assertEqual(result['workflow']['phase_status'], 'blocked')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'todo')

    def test_wrong_session_package_is_rejected_before_writes(self):
        before = self.snapshot()
        response = self.cli('propose', 'create', {}, ok=False,
                            extra=['--session-package-digest', '0' * 64])
        self.assertEqual(response['error']['code'], 'SESSION_PACKAGE_MISMATCH')
        self.assertEqual(response['workflow']['next_steps'][0]['owner_skill'], 'evolve-workflow')
        self.assertEqual(self.snapshot(), before)

    def test_healthy_query_reports_activation_observation_separately(self):
        manifest = json.loads((ROOT / 'evolve-package.json').read_text())
        result = self.cli(extra=['--session-package-digest', manifest['content_digest']])
        self.assertEqual(result['data']['activation']['session_status'], 'matching_package')
        self.assertEqual(result['data']['activation']['host_enablement'], 'not_observed')
        self.assertEqual(result['workflow']['phase_status'], 'observed')
        self.assertFalse(result['workflow']['goal_complete'])

    def test_query_and_unavailable_method_have_actionable_handoff(self):
        before = self.snapshot()
        response = self.cli('verify', 'record', ok=False)
        self.assertEqual(response['error']['code'], 'UNAVAILABLE')
        self.assertTrue(response['workflow']['next_steps'][0]['prompt'])
        self.assertFalse(response['workflow']['next_steps'][0]['authorization_granted'])
        self.assertEqual(self.snapshot(), before)

    def repair_plan(self):
        return self.cli('maintain', 'repair', {'stage': 'plan'})['data']

    def test_real_change_has_distinct_implementation_verification_and_archive_handoffs(self):
        response = self.cli('apply', 'implement', self.apply_request()['input'])
        self.assertEqual(response['workflow']['phase_status'], 'completed')
        self.assertFalse(response['workflow']['goal_complete'])
        self.assertEqual(response['workflow']['next_steps'][0]['owner_skill'], 'evolve-verify')
        verified = self.cli('verify', 'run', self.verification_request()['input'])
        self.assertEqual(verified['data']['status'], 'passed')
        self.assertEqual(verified['workflow']['next_steps'][0]['owner_skill'], 'evolve-archive')
        response = self.cli('archive', 'close', {'change_id': self.plan['change_id'],
            'verification_id': verified['data']['verification_id']})
        self.assertTrue(response['workflow']['goal_complete'])
        self.assertEqual(response['workflow']['evidence']['change_id'], self.plan['change_id'])

    def test_normal_pause_has_resume_instruction_and_keeps_goal_unfinished(self):
        request = self.apply_request()['input']
        request['pause'] = {'completed': ['Prepared sum implementation'], 'remaining': ['Run original checks'],
                            'next_steps': ['Continue original checks'], 'reason': 'Explicit fixture pause'}
        response = self.cli('apply', 'implement', request)
        self.assertEqual(response['workflow']['phase_status'], 'paused')
        self.assertFalse(response['workflow']['goal_complete'])
        self.assertEqual(response['workflow']['next_steps'][0]['action'], 'resume')
        before = self.snapshot()
        response = self.cli('resume', target=self.plan['change_id'])
        self.assertEqual(response['workflow']['next_steps'][0]['owner_skill'], 'evolve-apply')
        self.assertEqual(self.snapshot(), before)

    def test_candidate_query_and_cancel_do_not_claim_goal_completion(self):
        self.auth['effect_kinds'].append('knowledge')
        self.auth['paths'].append('evolve/notes.md')
        content = '# Exact candidate\n\nTemporary local guide.\n'
        response = self.cli('init', 'baseline.propose', {'path': 'evolve/notes.md', 'expected_digest': None,
            'content': content, 'presentation': {'source': 'literal fixture', 'text': content}})
        self.assertEqual(response['workflow']['phase_status'], 'waiting_confirmation')
        self.assertFalse((self.root / 'evolve/notes.md').exists())
        response = self.cli('maintain', 'cancel', {'change_id': self.plan['change_id'], 'reason': 'Stop this disposable change'})
        self.assertEqual(response['workflow']['phase_status'], 'cancelled')
        self.assertFalse(response['workflow']['goal_complete'])

    def test_candidate_release_inspection_is_separate_from_installation(self):
        before = self.snapshot()
        response = self.cli('maintain', 'doctor', extra=['--candidate-package', str(ROOT)])
        self.assertEqual(response['data']['update_check']['archive_compatibility'], 'compatible')
        self.assertEqual(response['data']['update_check']['installation'], 'not_performed')
        self.assertEqual(response['data']['activation']['session_status'], 'not_observed')
        self.assertEqual(self.snapshot(), before)

    def test_doctor_remains_read_only_when_history_is_damaged(self):
        (self.root / 'evolve/history.db').write_bytes(b'controlled corrupt archive')
        before = self.snapshot()
        response = self.cli('maintain', 'doctor')
        self.assertEqual(response['data']['project']['state'], 'unavailable')
        self.assertEqual(response['data']['readiness']['actions']['business_files']['status'], 'blocked')
        self.assertEqual(response['workflow']['next_steps'][0]['owner_skill'], 'evolve-maintain')
        failed = self.cli(ok=False)
        self.assertEqual(failed['workflow']['next_steps'][0]['owner_skill'], 'evolve-maintain')
        self.assertEqual(self.snapshot(), before)

    def test_invalid_control_json_shape_is_diagnosed_and_never_replaced(self):
        path = self.root / '.evolve-local/control/checks.json'
        path.write_text('[]')
        before = self.snapshot()
        response = self.cli('maintain', 'doctor')
        self.assertEqual(response['data']['readiness']['actions']['checks']['status'], 'blocked')
        self.assertEqual(self.snapshot(), before)
        self.cli('maintain', 'repair', {'stage': 'plan'}, ok=False)
        self.assertEqual(path.read_text(), '[]')

    def test_missing_initialization_blocks_record_writes_consistently(self):
        (self.root / '.evolve-local/control/init.json').unlink()
        before = self.snapshot()
        original = self.rows("SELECT input_json FROM phase_runs WHERE action='propose'")[0]
        data = json.loads(original['input_json'])['request']['input']
        response = self.cli('propose', 'create', {**data, 'title': 'must not be saved'}, ok=False)
        self.assertEqual(response['error']['code'], 'PROTECTION_UNKNOWN')
        self.assertEqual(self.snapshot(), before)

    def test_active_maintenance_routes_to_original_maintenance_instead_of_initialization(self):
        path = self.root / '.evolve-local/control/maintenance.json'
        path.write_text(json.dumps({'state': 'active', 'request_id': 'original-maintenance', 'plan_id': 'original-plan'}))
        before = self.snapshot()
        response = self.cli()
        self.assertEqual(response['data']['readiness']['actions']['business_files']['status'], 'blocked')
        self.assertEqual(response['workflow']['next_steps'][0]['owner_skill'], 'evolve-maintain')
        self.assertEqual(self.snapshot(), before)

    def test_normal_pause_survives_repair_with_fresh_bindings_and_original_grant(self):
        from evolve_core.apply import implement
        from evolve_core.errors import EvolveError
        old = self.apply_request()
        old['input']['pause'] = {'completed': ['Wrote exact sum'], 'remaining': ['Run original checks'],
            'next_steps': ['Continue checks and acceptance'], 'reason': 'Explicit pause before maintenance'}
        implement(self.root, old)
        (self.root / '.evolve-local/control/checks.json').unlink()
        plan = self.repair_plan()
        repaired = self.cli('maintain', 'repair', {'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']})['data']
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, old)
        self.assertEqual(caught.exception.code, 'WORKSPACE_EPOCH')
        self.project['workspace_epoch'] = repaired['workspace_epoch']
        request = self.apply_request()
        request['input']['files'] = []
        continued = implement(self.root, request)
        self.assertEqual(continued['outcome'], 'implemented')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'done')

    def test_self_consistent_but_incomplete_candidate_inventory_is_rejected(self):
        import shutil
        from evolve_core.package import canonical, digest
        candidate = self.root / 'candidate-package'
        shutil.copytree(ROOT / 'runtime', candidate / 'runtime')
        manifest = json.loads((ROOT / 'evolve-package.json').read_text())
        for name in manifest['files']:
            if not name.startswith('runtime/'):
                target = candidate / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
        (candidate / 'runtime/evolve_core/cli.py').unlink()
        del manifest['files']['runtime/evolve_core/cli.py']
        manifest['content_digest'] = digest(canonical(manifest['files']))
        (candidate / 'evolve-package.json').write_text(json.dumps(manifest))
        response = self.cli('maintain', 'doctor', extra=['--candidate-package', str(candidate)], ok=False)
        self.assertEqual(response['error']['code'], 'PACKAGE_INCOMPLETE')

    def test_repair_missing_unused_indexes_then_run_real_original_checks(self):
        from evolve_core.apply import implement
        for name in ('checks.json', 'external.json', 'init.json'):
            (self.root / '.evolve-local/control' / name).unlink()
        old_runs = self.rows('SELECT * FROM phase_runs')
        old_tasks = self.rows('SELECT * FROM tasks')
        plan = self.repair_plan()
        self.assertFalse((self.root / '.evolve-local/control/checks.json').exists())
        response = self.cli('maintain', 'repair', {'stage': 'apply', 'plan_id': plan['plan']['plan_id'],
            'plan_digest': plan['plan_digest']})
        self.assertEqual(response['data']['outcome'], 'repaired')
        self.assertEqual(self.rows('SELECT * FROM phase_runs'), old_runs)
        self.assertEqual(self.rows('SELECT * FROM tasks'), old_tasks)
        self.assertEqual(self.cli()['data']['readiness']['actions']['checks']['status'], 'ready')
        self.project['workspace_epoch'] = response['data']['workspace_epoch']
        result = implement(self.root, self.apply_request())
        self.assertEqual(result['outcome'], 'implemented')

    def test_repair_refuses_unknown_execution_and_retains_original_bytes(self):
        from evolve_core.store import Store
        from evolve_core.workspace import writer_lock
        request = self.request({})
        with writer_lock(self.root):
            store = Store(self.root)
            try:
                store.start(request, action='verify', method='run', owner='evolve-verify')
            finally:
                store.close()
        (self.root / '.evolve-local/control/checks.json').unlink()
        before = (self.root / 'evolve/history.db').read_bytes()
        response = self.cli('maintain', 'repair', {'stage': 'plan'}, ok=False)
        self.assertEqual(response['error']['code'], 'REPAIR_UNSAFE')
        self.assertEqual((self.root / 'evolve/history.db').read_bytes(), before)
        self.assertFalse((self.root / '.evolve-local/control/checks.json').exists())

    def test_repair_rechecks_files_that_were_absent_when_presented(self):
        path = self.root / '.evolve-local/control/checks.json'
        original = path.read_bytes()
        path.unlink()
        plan = self.repair_plan()
        path.write_bytes(original)
        response = self.cli('maintain', 'repair', {'stage': 'apply', 'plan_id': plan['plan']['plan_id'],
            'plan_digest': plan['plan_digest']}, ok=False)
        self.assertEqual(response['error']['code'], 'RESTORE_CHANGED')
        self.assertEqual(path.read_bytes(), original)

    def test_repair_abrupt_swap_resumes_only_the_original_apply_request(self):
        from evolve_core import maintenance
        (self.root / '.evolve-local/control/checks.json').unlink()
        plan = self.repair_plan()
        request = {**self.identity(), 'request_id': 'original-repair-after-crash', 'authorization': self.auth,
            'input': {'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']}}
        code = '''import json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from evolve_core import maintenance
def crash(name):
    if name == 'after:evolve/history.db': os._exit(73)
maintenance.fault_point = crash
maintenance.repair(Path(sys.argv[2]),json.loads(sys.stdin.read()))
'''
        old = self.rows('SELECT * FROM phase_runs')
        child = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'), str(self.root)],
            input=json.dumps(request), capture_output=True, text=True, timeout=40)
        self.assertEqual(child.returncode, 73, child.stderr)
        self.assertEqual(self.cli()['data']['project']['state'], 'maintenance')
        repaired = maintenance.repair(self.root, request)
        self.assertEqual(repaired['outcome'], 'repaired')
        self.assertEqual(maintenance.repair(self.root, request), repaired)
        self.assertEqual(self.rows('SELECT * FROM phase_runs'), old)
        self.assertEqual(self.cli()['data']['readiness']['actions']['checks']['status'], 'ready')
