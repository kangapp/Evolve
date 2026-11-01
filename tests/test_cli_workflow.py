"""A complete public-CLI workflow from an independently built and relocated package."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-cli-workflow-')
        self.addCleanup(self.temp.cleanup)
        self.lab = Path(self.temp.name).resolve()
        self.package = self.lab / 'installed 中文 space'
        subprocess.run([sys.executable, str(ROOT / 'scripts/build_package.py'), '--out', str(self.package)],
                       check=True, capture_output=True)
        self.project = self.lab / 'business'
        self.project.mkdir()
        (self.project / 'calc.py').write_text('def total(values): return len(values)\n')
        (self.project / 'test_calc.py').write_text('import unittest\nfrom calc import total\n'
            'class Arithmetic(unittest.TestCase):\n'
            '    def test_sum(self): self.assertEqual(total([4,7]),11)\n')
        self.auth = {'source': 'public-cli-isolated-fixture', 'text': 'Fix the total and test it through completion',
                     'effect_kinds': ['project_records', 'business_files', 'checks'],
                     'paths': ['calc.py', 'test_calc.py']}

    def cli(self, action='status', *, method=None, payload=None, target=None, expected=0):
        command = [sys.executable, str(self.package / 'runtime/evolve.py'), '--project', str(self.project), action]
        if target:
            command.append(target)
        if method:
            command += ['--method', method]
        if payload is not None:
            command += ['--request', '-']
        result = subprocess.run(command, cwd=self.lab, text=True, capture_output=True,
                                input=json.dumps(payload) if payload is not None else None)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return json.loads(result.stdout)

    def test_full_small_change_through_public_interface_with_system_generated_identifiers(self):
        self.assertEqual(self.cli()['data']['project']['state'], 'not_connected')
        connected = self.cli('init', payload={'authorization': self.auth, 'input': {'checks': [
            {'id': 'unit', 'argv': [sys.executable, '-B', '-m', 'unittest', 'discover', '-v'], 'timeout': 10}]}})
        self.assertTrue(connected['data']['project_id'])
        plan_text = 'Add the input values and retain the arithmetic expectation of eleven.'
        planned = self.cli('propose', payload={'authorization': self.auth, 'input': {
            'title': 'Correct total', 'plan': plan_text, 'completion': 'The arithmetic test passes.',
            'scope': ['calc.py', 'test_calc.py'], 'required_checks': ['unit'], 'acceptance': ['[4,7] totals eleven'],
            'presentation': {'source': 'fixture-assistant-message', 'text': plan_text}}})['data']
        status = self.cli(target='Correct total')['data']['project']
        self.assertEqual(status['changes'][0]['id'], planned['change_id'])
        self.assertEqual(status['changes'][0]['plan']['text'], plan_text)
        self.assertEqual(status['changes'][0]['tasks'][0]['definition']['required_checks'], ['unit'])
        applied = self.cli('apply', target='Correct total', payload={'authorization': self.auth, 'input': {'files': [
            {'path': 'calc.py', 'expected_digest': hashlib.sha256((self.project / 'calc.py').read_bytes()).hexdigest(),
             'content': 'def total(values): return sum(values)\n'}]}})['data']
        self.assertEqual(applied['outcome'], 'implemented')
        self.assertEqual(applied['overall_verification'], 'not_run')
        reviews = [{'axis': axis, 'observer': 'public-cli-fixture-observer',
                    'summary': 'Inspected calc.py and the independent expected result in test_calc.py',
                    'fingerprint_digest': applied['fingerprint']['digest'], 'findings': []}
                   for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': planned['acceptance'][0]['id'], 'status': 'passed',
                                            'basis': 'The independent literal expectation in test_calc.py'}]
        verified = self.cli('verify', target='Correct total', payload={'authorization': self.auth,
                            'input': {'reviews': reviews}})['data']
        self.assertEqual(verified['status'], 'passed')
        archived = self.cli('archive', target='Correct total', payload={'authorization': self.auth,
                            'input': {'verification_id': verified['verification_id']}})['data']
        self.assertEqual(archived['outcome'], 'archived')
        self.assertEqual(self.cli()['data']['project']['changes'][0]['state'], 'archived')
        self.assertFalse((self.project / 'evolve/project.md').exists())

    def test_prepared_retries_cannot_silently_adopt_a_new_epoch(self):
        self.cli('init', payload={'authorization': self.auth, 'input': {}})
        result = self.cli('propose', payload={'request_id': 'old-incomplete-request', 'authorization': self.auth,
                          'input': {}}, expected=2)
        self.assertEqual(result['error']['code'], 'INPUT')

    def test_initial_connection_receipt_can_be_replayed_with_complete_generated_context(self):
        payload = {'authorization': self.auth, 'input': {}}
        first = self.cli('init', payload=payload)['data']
        retried = self.cli('init', payload={**payload, **first['request_context']})['data']
        self.assertEqual(retried['project_id'], first['project_id'])
        self.assertEqual(retried['run_id'], first['run_id'])

    def test_first_init_accepts_a_request_file_in_its_own_project_control_directory(self):
        staged = self.project / '.evolve-local/control/requests/first-unique.json'
        staged.parent.mkdir(parents=True)
        original = json.dumps({'authorization': self.auth, 'input': {}})
        staged.write_text(original)
        result = subprocess.run([sys.executable, str(self.package / 'runtime/evolve.py'),
            '--project', str(self.project), 'init', '--request', str(staged)],
            cwd=self.project, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['data']['outcome'], 'connected')
        self.assertEqual(staged.read_text(), original)

    def test_malformed_json_is_a_structured_input_error(self):
        command = [sys.executable, str(self.package / 'runtime/evolve.py'), '--project', str(self.project),
                   'init', '--request', '-']
        result = subprocess.run(command, input='not-json', text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'INPUT')
        self.assertFalse((self.project / '.evolve-local').exists())

    def test_original_symptom_pipeline_runs_from_the_independently_built_package(self):
        project = self.lab / 'diagnostic-business'
        project.mkdir()
        evidence = self.lab / 'diagnostic-evidence'
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/workflow_smoke.py'),
            '--runtime', str(self.package / 'runtime/evolve.py'), '--project', str(project),
            '--out', str(evidence), '--diagnostic'], text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertTrue(summary['passed'])
        self.assertFalse(summary['investigation']['answer_only_created_records'])
        self.assertTrue(summary['investigation']['original_red_saved'])
        self.assertEqual(summary['investigation']['post_repair_original_criterion'], 'passed')
