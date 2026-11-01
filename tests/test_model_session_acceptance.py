"""The model runner's parent checks use actual workflow facts; no model is called."""
import json
import io
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'runtime'))
from model_session_checks import SessionChecks, scope_for
from model_acceptance import original_fixture
import model_acceptance as model_runner
import test_diagnostic_workflow as diagnostics
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.connect import connect
from evolve_core.learning import learn, search
from evolve_core.package import check_package, digest
from evolve_core.plans import propose
from evolve_core.privacy import redact
from evolve_core.verify import verify


class ModelSessionChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-session-parent-test-')
        self.addCleanup(self.temp.cleanup)
        self.lab = Path(self.temp.name).resolve()
        self.root = self.lab / 'business'
        self.root.mkdir()
        self.evidence = self.lab / 'evidence'
        self.evidence.mkdir()
        self.first = {'total.py': 'def total(values):\n    return len(values)\n',
            'test_total.py': 'import unittest\nfrom total import total\nclass Totals(unittest.TestCase):\n'
            '    def test_values(self):\n        self.assertEqual(total([2,3]),5)\n'
            '        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n'}
        for name, content in self.first.items():
            (self.root / name).write_text(content)
        self.scope = scope_for(check_package(), 'codex', None, self.first, ROOT / 'scripts/model_acceptance.py')
        self.checker = SessionChecks(self.root, self.scope, self.evidence)
        # Reuse real diagnostic request helpers without running their test methods.
        self.fixture = diagnostics.DiagnosticWorkflowTests()
        self.fixture.root = self.root
        self.fixture.auth = {'source': 'controlled model-parent-check fixture', 'text': 'Repair and check only the two local fixture files',
                             'effect_kinds': ['project_records', 'business_files', 'checks'], 'paths': list(self.first)}
        self.fixture.checks = [{'id': 'unit', 'argv': [sys.executable, '-B', '-m', 'unittest', 'discover', '-v'], 'cwd': '.', 'timeout': 10}]

    def ref(self, run_id):
        row = self.fixture.rows('SELECT * FROM phase_runs WHERE id=?', (run_id,))[0]
        return {'run_id': run_id, 'result_digest': row['result_digest'],
                'evidence_ids': [e['id'] for e in self.fixture.rows('SELECT id FROM evidence WHERE source_run_id=?', (run_id,))]}

    def partial(self):
        self.checker.before('pause')
        f = self.fixture
        f.project = connect(self.root, {'authorization': f.auth, 'input': {'checks': f.checks}})
        f.investigate_symptom()
        f.plan = f.diagnostic_plan()
        request = f.apply_request()
        request['input']['pause'] = {'completed': ['Saved actual sum candidate'], 'remaining': ['Original checks and verification'],
                                     'next_steps': ['Continue from original record'], 'reason': 'Controlled normal pause'}
        result = implement(self.root, request)
        self.checker.after('pause')
        return result

    def continued(self):
        paused = self.partial()
        self.checker.before('continue')
        f = self.fixture
        request = f.apply_request()
        request['input']['continuation'] = {k: v for k, v in self.ref(paused['run_id']).items() if k != 'evidence_ids'}
        applied = implement(self.root, request)
        checked = verify(self.root, f.observed_verification())
        archive(self.root, f.request({'verification_id': checked['verification_id']}))
        learn(self.root, {**f.identity(), 'request_id': str(uuid.uuid4()), 'authorization': f.auth,
            'input': {'experience': {'topic': 'Integer sum fixture', 'problem': 'Count implementation did not match independent sums',
                'cause': {'statement': 'Actual count instead of sum observed in the local fixture', 'confidence': 'observed'},
                'advice': 'Compare the sum contract with literal expectations', 'applicability': 'Local integer total examples',
                'version_context': 'controlled fixture', 'observer': 'actual local check observer', 'scope': ['local integer totals'],
                'exclusions': ['Unobserved production data'], 'tags': ['sum'], 'limitations': ['Only local examples']},
                'sources': [self.ref(applied['run_id'])]}}, method='record')
        return self.checker.after('continue')

    def test_immediate_answer_keeps_bytes_and_has_no_record_facilities(self):
        self.checker.before('inspect')
        observed = self.checker.after('inspect')
        self.assertFalse(observed['records_created'])
        (self.root / '.evolve-local').mkdir()
        with self.assertRaisesRegex(AssertionError, 'initialized record facilities'):
            self.checker.after('inspect')

    def test_read_only_change_is_rejected_even_if_the_model_claims_success(self):
        self.checker.before('inspect')
        (self.root / 'total.py').write_text('def total(values): return sum(values)\n')
        with self.assertRaisesRegex(AssertionError, 'Read-only scenario'):
            self.checker.after('inspect')

    def test_real_partial_then_fresh_continuation_passes_parent_facts(self):
        observed = self.continued()
        self.assertTrue(observed['closed'])
        self.assertTrue(observed['produced_experiences'])
        self.assertTrue(observed['pause_run_unchanged'])

    def test_completed_task_cannot_be_reported_as_a_normal_precheck_pause(self):
        self.checker.before('pause')
        f = self.fixture
        f.project = connect(self.root, {'authorization': f.auth, 'input': {'checks': f.checks}})
        f.investigate_symptom()
        f.plan = f.diagnostic_plan()
        implement(self.root, f.apply_request())
        with self.assertRaisesRegex(AssertionError, 'Normal pause'):
            self.checker.after('pause')

    def test_parent_independent_assertions_reject_modified_literal_expectations(self):
        self.continued()
        path = self.root / 'test_total.py'
        path.write_text(path.read_text().replace('total([2,3]),5', 'total([2,3]),99'))
        with self.assertRaisesRegex(AssertionError, 'original independent literal'):
            self.checker.independent(self.first, 'tampered')

    def second(self, consume):
        self.continued()
        self.checker.before('similar')
        f = self.fixture
        first_plan = f.plan
        scope = list(self.scope['second_files'])
        f.auth = {**f.auth, 'paths': scope}
        text = 'Return sum for the second fixture and preserve independent examples'
        f.plan = propose(self.root, {**f.identity(), 'request_id': str(uuid.uuid4()), 'authorization': f.auth, 'input': {
            'title': 'Second integer-total fixture', 'plan': text, 'completion': 'Second literal examples pass', 'scope': scope,
            'required_checks': ['unit'], 'acceptance': ['Examples total 12,0,7'],
            'presentation': {'source': 'controlled fixture presentation', 'text': text}}})
        if consume:
            found = search(self.root, 'Integer')
            item = found['results'][0]
            decided = learn(self.root, {**f.identity(), 'request_id': str(uuid.uuid4()), 'authorization': f.auth,
                'input': {'kind': 'decision', 'experience_ref': item['experience_ref'], 'search_ref': found['search_ref'],
                    'decision': 'adopted', 'change_id': f.plan['change_id'], 'revision_id': f.plan['revision_id'],
                    'definition_digest': f.plan['definition_digest'],
                    'observed_files': {name: digest((self.root / name).read_bytes()) for name in scope},
                    'applicability_basis': 'The second integer fixture has the same count/sum mismatch and independent literal expectations.',
                    'limitations': ['Only these local integer examples are observed.']}}, method='review')
        source = self.root / 'arithmetic_second.py'
        applied = implement(self.root, f.request({'accepted_plan_digest': f.plan['plan_digest'],
            'files': [{'path': source.name, 'expected_digest': digest(source.read_bytes()), 'content': 'def total(values):\n    return sum(values)\n'}]}))
        checked = verify(self.root, f.verification_request())
        archive(self.root, f.request({'verification_id': checked['verification_id']}))
        if consume:
            learn(self.root, {**f.identity(), 'request_id': str(uuid.uuid4()), 'authorization': f.auth,
                'input': {'kind': 'feedback', 'decision_ref': self.ref(decided['run_id']), 'outcome': 'unknown',
                    'result_source': self.ref(checked['run_id']),
                    'basis': 'Actual second-task verification passed; its independent contribution cannot be separated.',
                    'limitations': ['No causal benefit is claimed.']}}, method='review')
        self.assertNotEqual(first_plan['change_id'], applied['change_id'])

    def test_second_task_cannot_pass_without_saved_experience_decision_and_feedback(self):
        self.second(consume=False)
        with self.assertRaisesRegex(AssertionError, 'consume a prior experience'):
            self.checker.after('similar')

    def test_actual_two_tasks_with_learning_and_read_only_reverification_pass(self):
        self.second(consume=True)
        observed = self.checker.after('similar')
        self.assertTrue(observed['closed'])
        self.assertTrue(observed['experience_applications'])
        self.checker.before('verify', missing_tests=True)
        verify(self.root, self.fixture.verification_request())
        observed = self.checker.after('verify')
        self.assertTrue(observed['business_files_unchanged'])
        self.assertTrue(observed['historical_work_unchanged'])
        self.assertTrue(observed['new_verifications'])


class ModelScopeDispatchTests(unittest.TestCase):
    def test_headless_bridge_preserves_unconnected_status_and_first_init_and_exact_raw_response(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'business'
            evidence = Path(directory) / 'evidence'
            project.mkdir()
            evidence.mkdir()
            with patch.object(model_runner, 'digest', digest, create=True), patch.object(model_runner, 'redact', redact, create=True):
                bridge, _ = model_runner.prepare_headless_bridge(project, ROOT, evidence)
            status = subprocess.run([sys.executable, '-B', str(bridge), 'status'], capture_output=True, text=True)
            summary = json.loads(status.stdout)
            self.assertTrue(summary['ok'], summary)
            receipt = json.loads(Path(summary['receipt']).read_text())
            self.assertEqual(receipt['response']['data']['project']['state'], 'not_connected')
            self.assertEqual(json.loads(receipt['stdout']), receipt['response'])
            self.assertFalse((project / 'evolve/history.db').exists())
            request = project / '.evolve-local/control/requests/connect.json'
            request.write_text(json.dumps({'authorization': {'source': 'actual isolated controller regression',
                'text': 'Connect this disposable fixture only', 'effect_kinds': ['project_records']}, 'input': {}}))
            connected = subprocess.run([sys.executable, '-B', str(bridge), 'init', '--request', str(request)], capture_output=True, text=True)
            self.assertEqual(connected.returncode, 0, connected.stdout + connected.stderr)
            self.assertTrue((project / 'evolve/history.db').is_file())

    def run_cli(self, *options):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_acceptance.py'), '--host', 'codex',
                               '--package', str(ROOT), '--session-learning', *options],
                              text=True, capture_output=True, timeout=15)

    def test_final_delivery_guides_are_pinned_in_every_bounded_prompt_and_scope_digest(self):
        base = json.loads(self.run_cli('--preflight-only').stdout)['expanded_scope']
        result = self.run_cli('--preflight-only', '--read-user-guide')
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        scope = value['expanded_scope']
        self.assertFalse(value['model_requests_sent'])
        self.assertEqual(scope['offline_user_guides'], ['README.md', 'docs/installation.md', 'docs/usage.md'])
        self.assertNotEqual(scope['scope_digest'], base['scope_digest'])
        self.assertTrue(all(prompt.startswith('本次完整安装与项目启用已由控制侧') for prompt in scope['cases'].values()))
        self.assertEqual(scope['first_files'], base['first_files'])
        self.assertEqual(len(scope['cases']), len(base['cases']))

    def test_headless_safe_io_keeps_business_scope_and_binds_changed_transport_before_dispatch(self):
        command = [sys.executable, '-B', str(ROOT / 'scripts/model_acceptance.py'), '--host', 'claude',
                   '--claude-model', 'MiniMax-M3.1-Flash', '--package', str(ROOT), '--structured', '--read-user-guide']
        base = json.loads(subprocess.run(command + ['--preflight-only'], capture_output=True, text=True, check=True).stdout)['expanded_scope']
        result = subprocess.run(command + ['--headless-safe-io', '--preflight-only'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        safe = value['expanded_scope']
        self.assertFalse(value['model_requests_sent'])
        self.assertFalse(value['host_profile_created'])
        for key in ('first_files', 'second_files', 'business_write_paths', 'maximum_sessions'):
            self.assertEqual(safe[key], base[key])
        self.assertNotEqual(safe['scope_digest'], base['scope_digest'])
        self.assertTrue(all('evolve_bridge.py' in p and 'AskUserQuestion' in p for p in safe['cases'].values()))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'not-created'
            stale = subprocess.run(command + ['--headless-safe-io', '--out', str(out), '--authorization-text', 'test-only-not-a-real-grant',
                                   '--expected-scope-digest', base['scope_digest']], capture_output=True, text=True)
            self.assertEqual(stale.returncode, 2)
            self.assertFalse(out.exists())

    def test_expanded_preflight_lists_five_cases_without_profile_or_model_dispatch(self):
        result = self.run_cli('--preflight-only')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['model_requests_sent'])
        self.assertFalse(data['host_profile_created'])
        self.assertEqual(list(data['expanded_scope']['cases']), ['inspect','pause','continue','similar','verify'])
        self.assertEqual(set(data['expanded_scope']['first_files']), set(original_fixture()))
        self.assertEqual(set(data['expanded_scope']['second_files']), {'arithmetic_second.py','test_arithmetic_second.py'})

    def test_missing_expanded_authorization_is_rejected_before_creating_a_project(self):
        with tempfile.TemporaryDirectory() as temp:
            lab = Path(temp) / 'must-not-exist'
            result = self.run_cli('--out', str(lab))
            self.assertEqual(result.returncode, 2)
            self.assertIn('actual human authorization', result.stderr)
            self.assertFalse(lab.exists())

    def test_missing_test_variant_changes_the_authorized_scope_digest(self):
        base = json.loads(self.run_cli('--preflight-only').stdout)['expanded_scope']
        variant = json.loads(self.run_cli('--preflight-only', '--verify-missing-tests').stdout)['expanded_scope']
        self.assertFalse(base['verify_missing_tests_variant'])
        self.assertTrue(variant['verify_missing_tests_variant'])
        self.assertNotEqual(base['scope_digest'], variant['scope_digest'])

    def test_stale_scope_digest_is_rejected_before_host_setup_or_model_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            lab = Path(temp) / 'must-not-exist'
            result = self.run_cli('--out', str(lab), '--authorization-text', 'Fixture text, not a real dispatch grant',
                                  '--expected-scope-digest', '0' * 64)
            self.assertEqual(result.returncode, 2)
            self.assertIn('scope differs', result.stderr)
            self.assertFalse(lab.exists())

    def test_original_pinned_protocol2_preflight_remains_independent_of_current_checkout(self):
        # The portable alternate-version test is in PackageLifecycleTests; here the
        # preserved real archive proves the original open model gate remains runnable.
        import zipfile
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / 'old-complete-package'
            package.mkdir()
            with zipfile.ZipFile(ROOT / 'docs/evidence/imp003/evolve-alpha3-protocol2.zip') as archive:
                archive.extractall(package)
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_acceptance.py'), '--host','codex',
                '--package',str(package),'--preflight-only'], capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['protocol_version'],2)
            expanded = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_acceptance.py'), '--host','codex',
                '--package',str(package),'--session-learning','--preflight-only'],capture_output=True,text=True,timeout=15)
            self.assertEqual(expanded.returncode,2)
            self.assertIn('requires the complete',expanded.stderr)

    def test_preserved_protocol3_session_preflight_remains_usable_without_model_dispatch(self):
        import zipfile
        with tempfile.TemporaryDirectory() as temp:
            with zipfile.ZipFile(ROOT/'docs/evidence/m1-current-scope-package-alpha4.zip') as archive:
                archive.extractall(temp)
            result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/model_acceptance.py'),'--host','codex',
                '--package',str(Path(temp)/'package'),'--session-learning','--preflight-only'],
                capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data=json.loads(result.stdout)
            self.assertEqual(data['protocol_version'],3)
            self.assertFalse(data['model_requests_sent'])
            self.assertFalse(data['host_profile_created'])


class ModelTransportTests(unittest.TestCase):
    def test_codex_approval_request_stops_batch_instead_of_continuing_after_denial(self):
        event={'id':9,'method':'item/commandExecution/requestApproval','params':{}}
        process=subprocess.Popen([sys.executable,'-B','-c','import sys; print(' + repr(json.dumps(event)) + ',flush=True); sys.stdin.readline()'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        session=model_runner.CodexSession.__new__(model_runner.CodexSession)
        session.process=process;session.messages=[];session.buffer=b'';session.log=io.StringIO()
        session.selector=selectors.DefaultSelector();session.selector.register(process.stdout,selectors.EVENT_READ)
        try:
            with patch.object(model_runner,'redact',redact,create=True):
                with self.assertRaisesRegex(RuntimeError,'permission or user-input boundary'):
                    session.wait(lambda message: False)
            self.assertIn('requestApproval',session.log.getvalue())
        finally:
            process.kill();process.wait();session.selector.close();process.stdin.close();process.stdout.close();session.log.close()

    def test_permission_denial_stops_live_transport_before_later_file_effect(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); marker = root / 'should-not-exist'; log = root / 'denied.json'
            event = {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'is_error': True,
                'content': "ls was blocked. For security, Claude Code may only list files in the allowed working directories."}]}}
            child = 'import pathlib,time; time.sleep(.8); pathlib.Path(' + repr(str(marker)) + ').write_text("unexpected")'
            code = 'import json,subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); print(' + repr(json.dumps(event)) + ',flush=True); time.sleep(3)'
            with patch.object(model_runner, 'redact', redact, create=True):
                with self.assertRaisesRegex(RuntimeError, 'permission'):
                    model_runner.claude_case([sys.executable,'-B','-c',code], '', env=os.environ.copy(), project=root, log=log)
            subprocess.run([sys.executable,'-c','import time; time.sleep(1)'],check=True)
            self.assertFalse(marker.exists())
            self.assertEqual(json.loads(log.read_text())['transport_stop']['kind'],'permission')

    def test_zero_exit_with_permission_denials_is_not_success(self):
        self.native_result({'type':'result','subtype':'success','is_error':False,
            'permission_denials':[{'tool_name':'Bash'}]}, 'permission')

    def test_native_requires_approval_tool_error_stops_before_final_result(self):
        self.native_result({'type':'user','message':{'content':[{'type':'tool_result','is_error':True,
            'content':'This command requires approval','tool_use_id':'controlled-shasum-denial'}]}}, 'permission')

    def test_zero_exit_with_native_quota_error_is_not_success(self):
        self.native_result({'type':'result','subtype':'error_during_execution','is_error':True,
            'result':'API Error 429 / 2056: quota exhausted'}, 'native_error')

    def test_native_assistant_quota_error_stops_before_final_result(self):
        self.native_result({'type':'assistant','error':'rate_limit','message':{'content':[
            {'type':'text','text':'API Error: Request rejected (429), Token Plan quota (2056)'}]}}, 'native_error')

    def test_first_native_rate_limit_retry_stops_before_next_request(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); marker=root/'second-request'; log=root/'rate-limit.json'
            event={'type':'system','subtype':'api_retry','attempt':1,'max_retries':10,
                'retry_delay_ms':510.61238448483977,'error_status':429,'error':'rate_limit'}
            code='import pathlib,time; print(' + repr(json.dumps(event)) + ',flush=True); time.sleep(.8); pathlib.Path(' + repr(str(marker)) + ').write_text("retried")'
            with patch.object(model_runner,'redact',redact,create=True):
                with self.assertRaisesRegex(RuntimeError,'native_error'):
                    model_runner.claude_case([sys.executable,'-B','-c',code], '', env=os.environ.copy(), project=root, log=log)
            self.assertFalse(marker.exists())
            saved=json.loads(log.read_text())
            self.assertEqual(saved['transport_stop']['basis']['error_status'],429)
            self.assertEqual(saved['transport_stop']['basis']['attempt'],1)

    def test_non_quota_native_retry_can_complete_normally(self):
        with tempfile.TemporaryDirectory() as temp:
            events=[{'type':'system','subtype':'api_retry','attempt':1,'error_status':500,'error':'server_error'},
                {'type':'result','subtype':'success','is_error':False,'permission_denials':[]}]
            code='print(' + repr('\n'.join(json.dumps(e) for e in events)) + ',flush=True)'
            with patch.object(model_runner,'redact',redact,create=True):
                result=model_runner.claude_case([sys.executable,'-B','-c',code], '', env=os.environ.copy(), project=Path(temp), log=Path(temp)/'native.json')
            self.assertEqual(result['exit_code'],0)

    def native_result(self, event, blocked):
        with tempfile.TemporaryDirectory() as temp:
            log=Path(temp)/'native.json'
            code='print(' + repr(json.dumps(event)) + ',flush=True)'
            with patch.object(model_runner, 'redact', redact, create=True):
                with self.assertRaisesRegex(RuntimeError, blocked):
                    model_runner.claude_case([sys.executable,'-B','-c',code], '', env=os.environ.copy(), project=Path(temp), log=log)
            self.assertEqual(json.loads(log.read_text())['transport_stop']['kind'],blocked)

    def test_failed_business_check_does_not_impersonate_permission_or_model_error(self):
        with tempfile.TemporaryDirectory() as temp:
            events=[{'type':'user','message':{'content':[{'type':'tool_result','is_error':True,'content':'Ran 1 test; FAILED (failures=1)'}]}},
                {'type':'result','subtype':'success','is_error':False,'permission_denials':[]}]
            code='print(' + repr('\n'.join(json.dumps(e) for e in events)) + ',flush=True)'
            with patch.object(model_runner, 'redact', redact, create=True):
                result=model_runner.claude_case([sys.executable,'-B','-c',code], '', env=os.environ.copy(), project=Path(temp), log=Path(temp)/'native.json')
            self.assertEqual(result['exit_code'],0)

    def test_actual_timeout_keeps_partial_native_output_and_redacts_credentials(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'EVOLVE_TEST_SECRET': 'controlled-fixture-only-secret'}):
            log = Path(temp) / 'partial-model.json'
            argv = [sys.executable, '-B', '-c',
                'import os,sys,time; print("actual partial " + os.environ["EVOLVE_TEST_SECRET"],flush=True); '
                'print("actual stderr before timeout",file=sys.stderr,flush=True); time.sleep(3)']
            with patch.object(model_runner, 'redact', redact, create=True):
                with self.assertRaises(subprocess.TimeoutExpired):
                    model_runner.claude_case(argv, '', env=os.environ.copy(), project=Path(temp), log=log, timeout=.7)
            saved = json.loads(log.read_text())
            self.assertTrue(saved['timed_out'])
            self.assertIsNone(saved['exit_code'])
            self.assertIn('actual partial [REDACTED]', saved['stdout'])
            self.assertIn('actual stderr before timeout', saved['stderr'])
            self.assertNotIn(os.environ['EVOLVE_TEST_SECRET'], log.read_text())
