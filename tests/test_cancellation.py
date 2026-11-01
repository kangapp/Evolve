"""Cancellation records intent without undoing physical effects or stealing claims."""
import json
import io
from pathlib import Path
import subprocess
import sys
import time
import unittest
import zipfile
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.verify import verify

ROOT = Path(__file__).resolve().parents[1]


class CancellationTests(unittest.TestCase):
    def setUp(self):
        self.f = WorkflowFixture()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def cancel(self, request):
        from evolve_core.cancellation import cancel_change
        return cancel_change(self.f.root, request)

    def request(self):
        request = self.f.request({'reason': 'Stop this disposable work; preserve all observed effects.'})
        request['authorization'] = {'source': 'explicit-controlled-stop',
            'text': 'Cancel this exact disposable Change, preserving existing files and evidence.',
            'effect_kinds': ['project_records']}
        return request

    def test_safe_cancel_is_idempotent_and_keeps_source_bytes(self):
        before = {p.name: p.read_bytes() for p in self.f.root.glob('*.py')}
        request = self.request()
        result = self.cancel(request)
        self.assertEqual(result['outcome'], 'cancelled')
        self.assertEqual(self.cancel(request), result)
        self.assertEqual(self.f.rows('SELECT state FROM changes')[0]['state'], 'cancelled')
        self.assertEqual(self.f.rows('SELECT state FROM tasks')[0]['state'], 'cancelled')
        self.assertEqual({p.name: p.read_bytes() for p in self.f.root.glob('*.py')}, before)
        self.assertEqual(self.f.rows("SELECT count(*) AS n FROM phase_runs WHERE method='cancel'")[0]['n'], 1)

    def test_completed_implementation_and_passed_verification_survive_cancel(self):
        implement(self.f.root, self.f.apply_request())
        checked = verify(self.f.root, self.f.verification_request())
        before = self.f.rows('SELECT * FROM verifications')
        source = (self.f.root / 'total.py').read_bytes()
        self.cancel(self.request())
        self.assertEqual(self.f.rows('SELECT state FROM tasks')[0]['state'], 'done')
        self.assertEqual(self.f.rows('SELECT * FROM verifications'), before)
        self.assertEqual(checked['status'], 'passed')
        self.assertEqual((self.f.root / 'total.py').read_bytes(), source)

    def test_cancel_rejects_stale_versions_and_archived_change(self):
        stale = self.request()
        implement(self.f.root, self.f.apply_request())
        with self.assertRaises(EvolveError) as caught:
            self.cancel(stale)
        self.assertEqual(caught.exception.code, 'VERSION')
        checked = verify(self.f.root, self.f.verification_request())
        archive(self.f.root, self.f.request({'verification_id': checked['verification_id']}))
        with self.assertRaises(EvolveError) as caught:
            self.cancel(self.request())
        self.assertEqual(caught.exception.code, 'TERMINAL_CHANGE')

    def test_cancel_does_not_steal_a_real_running_check_or_release_its_claims(self):
        test = self.f.root / 'test_total.py'
        original = test.read_text()
        test.write_text("from pathlib import Path\nimport time\nPath('.evolve-local/ready').write_text('ready')\n"
            "while not Path('.evolve-local/release').exists():\n    time.sleep(.02)\n" + original)
        from evolve_core.package import digest
        request = self.f.apply_request()
        request['input']['observations'] = {'test_total.py': digest(test.read_bytes())}
        code = '''import json,sys
sys.path.insert(0,sys.argv[1])
from evolve_core.apply import implement
print(json.dumps(implement(sys.argv[2],json.loads(sys.argv[3]))))
'''
        process = subprocess.Popen([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'),
            str(self.f.root), json.dumps(request)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (self.f.root / '.evolve-local/ready').exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((self.f.root / '.evolve-local/ready').exists())
            claims = self.f.rows('SELECT * FROM resource_claims')
            self.assertTrue(claims)
            with self.assertRaises(EvolveError) as caught:
                self.cancel(self.request())
            self.assertEqual(caught.exception.code, 'CLAIM')
            self.assertEqual(self.f.rows('SELECT * FROM resource_claims'), claims)
            self.assertIsNone(process.poll())
        finally:
            (self.f.root / '.evolve-local/release').write_text('release')
            out, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, out + err)
        self.assertEqual(json.loads(out)['outcome'], 'implemented')
        self.assertEqual(self.cancel(self.request())['outcome'], 'cancelled')

    def test_real_exit_after_cancel_commit_recovers_metadata_without_undo(self):
        request = self.request()
        code = '''import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core.cancellation import cancel_change
from evolve_core.store import Store
def stop(self,run_id,result,**kwargs):
    os._exit(27)
Store.finish=stop
cancel_change(sys.argv[2],json.loads(sys.argv[3]))
'''
        process = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'),
            str(self.f.root), json.dumps(request)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 27, process.stderr)
        self.assertEqual(self.f.rows('SELECT state FROM changes')[0]['state'], 'cancelled')
        pending = self.f.rows("SELECT id FROM phase_runs WHERE status='started'")[0]['id']
        from evolve_core.recover import recover
        result = recover(self.f.root, {**self.f.identity(), 'authorization': self.f.auth, 'input': {'run_id': pending}})
        self.assertEqual(result['outcome'], 'recovered_metadata')
        self.assertTrue(result['original_facts_committed'])
        self.assertEqual(self.f.rows('SELECT state FROM changes')[0]['state'], 'cancelled')
        self.assertEqual(self.f.rows('SELECT * FROM resource_claims'), [])

    def test_finish_error_keeps_committed_cancel_available_for_recovery(self):
        request = self.request()
        code = '''import json,sys
sys.path.insert(0,sys.argv[1])
from evolve_core.cancellation import cancel_change
from evolve_core.store import Store
from evolve_core.errors import EvolveError
def lost(self,run_id,result,**kwargs):
    raise EvolveError('LOST_RECEIPT','Controlled caller failure after cancellation committed')
Store.finish=lost
try:
    cancel_change(sys.argv[2],json.loads(sys.argv[3]))
except EvolveError as error:
    print(json.dumps({'code':error.code,'committed':error.committed}))
'''
        process = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'),
            str(self.f.root), json.dumps(request)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout), {'code': 'LOST_RECEIPT', 'committed': True})
        operation = self.f.rows("SELECT o.* FROM operations o JOIN phase_runs r ON r.id=o.run_id "
                                "WHERE o.state='committed' AND r.action='maintain' AND r.method='cancel'")[0]
        self.assertEqual(json.loads(operation['result_json'])['outcome'], 'cancelled')
        from evolve_core.recover import recover
        recovered = recover(self.f.root, {**self.f.identity(), 'authorization': self.f.auth,
            'input': {'operation_id': operation['id']}})
        self.assertTrue(recovered['original_facts_committed'])

    def test_public_cli_resolves_a_unique_title_and_preserves_cancel_bindings(self):
        from evolve_core.cli import main
        request = {'authorization': self.request()['authorization'], 'input': {'reason': 'Explicit stop at this local cutoff.'}}
        path = self.f.root / '.evolve-local/request-cancel.json'
        path.write_text(json.dumps(request))
        output = io.StringIO()
        with patch('sys.stdout', output):
            code = main(['--project', str(self.f.root), 'maintain', self.f.plan['title'] if 'title' in self.f.plan else 'Correct arithmetic total',
                '--method', 'cancel', '--owner', 'evolve-maintain', '--request', str(path)])
        self.assertEqual(code, 0, output.getvalue())
        response = json.loads(output.getvalue())['data']
        self.assertEqual(response['outcome'], 'cancelled')
        self.assertEqual(response['input_bindings']['change_id'], self.f.plan['change_id'])
        self.assertEqual(response['request_context']['project_id'], self.f.project['project_id'])

    def test_complete_old_alpha15_writer_rejects_protocol13_without_database_write(self):
        old = self.f.root / '.evolve-local/old-alpha15'
        with zipfile.ZipFile(ROOT / 'tests/fixtures/runtime-package-alpha15.zip') as archive:
            archive.extractall(old)
        database = self.f.root / 'evolve/history.db'
        before = database.read_bytes()
        result = subprocess.run([sys.executable, '-B', str(old / 'package/runtime/evolve.py'),
            '--project', str(self.f.root), 'apply', '--request', '-'],
            input=json.dumps(self.f.apply_request()), capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'SCHEMA_VERSION')
        self.assertEqual(database.read_bytes(), before)
