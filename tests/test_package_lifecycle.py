"""Real complete-package replacement around a live writer and preserved project data."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

from workflow_fixture import WorkflowFixture
from test_crash_points import CHILD
from evolve_core.backup import protect_before_write
from evolve_core.errors import EvolveError
from evolve_core.store import Store

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_lifecycle import compatible_fixture, project_files, reconnect_protection_current


PAUSED_CHILD = '''
import importlib,json,sys,time
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
app=importlib.import_module('evolve_core.apply')
from evolve_core.errors import EvolveError
ready,release=Path(sys.argv[3]),Path(sys.argv[4])
original=app.install_files
def paused(*a,**k):
    ready.write_text('journal prepared; no business bytes installed')
    deadline=time.monotonic()+15
    while not release.exists():
        if time.monotonic()>deadline: raise TimeoutError('parent did not release fixture')
        time.sleep(.01)
    return original(*a,**k)
try:
    with patch.object(app,'install_files',side_effect=paused):
        app.implement(Path(sys.argv[2]),json.load(sys.stdin))
except EvolveError as error:
    print(json.dumps({'error':error.code}),flush=True)
    sys.exit(error.exit_code)
'''


class PackageLifecycleTests(WorkflowFixture):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='evolve-lifecycle-build-')
        cls.distribution = Path(cls.build.name) / 'distribution'
        subprocess.run([sys.executable, str(ROOT / 'scripts/build_package.py'), '--out', str(cls.distribution)],
                       capture_output=True, check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        super().setUp()
        self.installation = tempfile.TemporaryDirectory(prefix='evolve-lifecycle-install-')
        self.addCleanup(self.installation.cleanup)
        self.install_root = Path(self.installation.name)
        self.package = self.install_root / '安装 space 中文'
        shutil.copytree(self.distribution, self.package)
        self.update = self.install_root / 'compatible'
        self.new_manifest = compatible_fixture(self.package, self.update)

    def cli(self, package, action, payload=None, *, method=None, expected=0):
        argv = [sys.executable, '-B', str(package / 'runtime/evolve.py'), '--project', str(self.root), action]
        if method:
            argv += ['--method', method]
        if payload is not None:
            argv += ['--request', '-']
        result = subprocess.run(argv, input=json.dumps(payload) if payload is not None else None,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def replace_live_package(self, replacement, expected_error):
        ready, release = self.install_root / 'ready', self.install_root / 'release'
        before = (self.root / 'total.py').read_bytes()
        request = self.apply_request()
        process = subprocess.Popen([sys.executable, '-B', '-c', PAUSED_CHILD, str(self.package / 'runtime'),
                                    str(self.root), str(ready), str(release)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            process.stdin.write(json.dumps(request))
            process.stdin.close()
            process.stdin = None
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(.01)
            self.assertTrue(ready.exists(), 'Child did not reach the actual prepared journal boundary')
            original = self.install_root / 'previous-complete-package'
            self.package.rename(original)
            replacement.rename(self.package)
            release.write_text('release original child, no new worker')
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 2 if expected_error == 'PACKAGE_VERSION' else 3, stdout + stderr)
            self.assertEqual(json.loads(stdout)['error'], expected_error)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        self.assertEqual((self.root / 'total.py').read_bytes(), before)
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)
        run = self.rows('SELECT * FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]
        self.assertEqual(run['status'], 'started')
        self.assertNotEqual(run['package_digest'], json.loads((self.package / 'evolve-package.json').read_text())['content_digest'])
        operation = self.rows('SELECT * FROM operations WHERE run_id=?', (run['id'],))[0]
        self.assertEqual(operation['state'], 'needs_recovery')
        return original, run, operation

    def test_lifecycle_reconnect_guard_does_not_accept_self_consistent_unregistered_metadata(self):
        self.assertTrue(reconnect_protection_current(self.root))
        path = self.root / '.evolve-local/control/managed.json'
        value = json.loads(path.read_text())
        value['files'].append({'path': 'unregistered.md', 'kind': 'knowledge', 'digest': 'f' * 64})
        encoded = json.dumps(value, sort_keys=True).encode()
        path.write_bytes(encoded)
        guard_path = self.root / '.evolve-local/control/guard.json'
        guard = json.loads(guard_path.read_text())
        guard['managed_index_digest'] = hashlib.sha256(encoded).hexdigest()
        guard_path.write_text(json.dumps(guard))
        self.assertFalse(reconnect_protection_current(self.root))

    def test_live_writer_cannot_install_business_bytes_after_whole_package_replacement(self):
        original, run, operation = self.replace_live_package(self.update, 'PACKAGE_VERSION')
        # A different, explicit recovery run uses the preserved complete original package.
        result = self.cli(original, 'maintain', self.request({'operation_id': operation['id']}), method='recover')['data']
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertFalse(result['business_commands_run'])
        self.assertEqual(result['checks'], 'not_run')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        sealed = self.rows('SELECT * FROM phase_runs WHERE id=?', (run['id'],))[0]
        self.assertEqual(sealed['package_digest'], run['package_digest'])
        self.assertEqual(sealed['status'], 'interrupted')
        self.assertEqual(json.loads(sealed['result_json'])['finalized_by'], result['run_id'])
        # The compatible package observes the existing identity without modifying any bytes.
        snapshot = project_files(self.root)
        status = self.cli(self.package, 'status')['data']['project']
        self.assertEqual(status['project_id'], self.project['project_id'])
        self.assertEqual(status['workspace_epoch'], self.project['workspace_epoch'])
        self.assertEqual(project_files(self.root), snapshot)

    def test_same_version_complete_content_replacement_cannot_continue_the_old_run(self):
        replacement = self.install_root / 'same-version-different-content'
        shutil.copytree(self.package, replacement)
        path = replacement / 'README.md'
        path.write_text(path.read_text() + '\nControlled same-version complete-content replacement.\n')
        inventory = replacement / 'evolve-package.json'
        metadata = json.loads(inventory.read_text())
        metadata['files'] = {name: hashlib.sha256((replacement / name).read_bytes()).hexdigest() for name in metadata['files']}
        metadata['content_digest'] = hashlib.sha256(json.dumps(metadata['files'], ensure_ascii=False, sort_keys=True,
                                                             separators=(',', ':')).encode()).hexdigest()
        inventory.write_text(json.dumps(metadata))
        original, run, operation = self.replace_live_package(replacement, 'EXECUTION_CHANGED')
        self.assertEqual(run['package_version'], metadata['package_version'])
        self.assertTrue(original.is_dir())
        self.assertEqual(operation['state'], 'needs_recovery')

    def test_compatible_package_does_not_adopt_external_bytes_as_task_completion(self):
        external = 'def total(values):\n    return sum(values)  # external editor\n'
        (self.root / 'total.py').write_text(external)
        task = self.rows('SELECT * FROM tasks')[0]
        before = project_files(self.root)
        state = self.cli(self.update, 'status')['data']['project']
        self.assertEqual(state['changes'][0]['tasks'][0]['state'], 'todo')
        self.assertEqual(project_files(self.root), before)
        result = self.cli(self.update, 'apply', self.apply_request(), expected=3)
        self.assertEqual(result['error']['code'], 'FILE_CONFLICT')
        self.assertEqual((self.root / 'total.py').read_text(), external)
        self.assertEqual(self.rows('SELECT * FROM tasks')[0], task)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)

    def test_full_existing_archive_with_unknown_schema_is_not_reinitialized_by_update(self):
        database = self.root / 'evolve/history.db'
        connection = sqlite3.connect(database)
        try:
            connection.execute("UPDATE project_meta SET value='999' WHERE key='schema_version'")
            connection.commit()
        finally:
            connection.close()
        before = project_files(self.root)
        for action, payload in [('status', None), ('init', {'authorization': self.auth, 'input': {}})]:
            with self.subTest(action=action):
                result = self.cli(self.update, action, payload, expected=2)
                self.assertEqual(result['error']['code'], 'SCHEMA_VERSION')
                self.assertEqual(project_files(self.root), before)
        self.assertEqual(self.rows("SELECT value FROM project_meta WHERE key='project_id'")[0]['value'], self.project['project_id'])

    def crash_original(self, point):
        request = self.apply_request()
        result = subprocess.run([sys.executable, '-B', '-c', CHILD, str(self.package / 'runtime'), str(self.root), point],
                                input=json.dumps(request), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 35, result.stdout + result.stderr)
        return self.rows('SELECT * FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]

    def test_new_compatible_recovery_preserves_no_operation_external_work_without_claiming_done(self):
        original = self.crash_original('before-operation')
        external = 'def total(values):\n    return sum(values)  # unregistered external work\n'
        (self.root / 'total.py').write_text(external)
        result = self.cli(self.update, 'maintain', self.request({'run_id': original['id']}), method='recover')['data']
        self.assertEqual(result['outcome'], 'recovered_registration')
        self.assertFalse(result['implementation_completed'])
        self.assertFalse(result['business_commands_run'])
        self.assertEqual((self.root / 'total.py').read_text(), external)
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'todo')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)
        sealed = self.rows('SELECT * FROM phase_runs WHERE id=?', (original['id'],))[0]
        recovery = self.rows('SELECT * FROM phase_runs WHERE id=?', (result['run_id'],))[0]
        self.assertEqual(sealed['status'], 'interrupted')
        self.assertEqual(sealed['package_digest'], original['package_digest'])
        self.assertEqual(recovery['package_digest'], self.new_manifest['content_digest'])
        self.assertNotEqual(recovery['package_digest'], sealed['package_digest'])
        folder = self.root / result['protection']
        manifest = json.loads((folder / 'manifest.json').read_text())
        self.assertFalse(manifest['consistent_restore_package'])
        self.assertTrue(any(p.read_bytes() == external.encode() for p in folder.glob('observed-*')))

    def test_third_value_after_real_exit_blocks_backup_and_keeps_conflict_across_update(self):
        original = self.crash_original('after-files')
        operation = self.rows('SELECT * FROM operations WHERE run_id=?', (original['id'],))[0]
        third = 'external content: do not overwrite'
        (self.root / 'total.py').write_text(third)
        # Existing daily protection cannot hide the newly unfinished file journal.
        backup_before = project_files(self.root / '.evolve-local/backups')
        plan = self.rows("SELECT input_json FROM phase_runs WHERE action='propose'")[0]
        request = json.loads(plan['input_json'])['request']
        blocked = self.cli(self.update, 'propose', request, expected=3)
        self.assertEqual(blocked['error']['code'], 'WRITER_ACTIVE')
        store = Store(self.root)
        try:
            with self.assertRaises(EvolveError) as caught:
                protect_before_write(store, 'after-real-crash')
            self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        finally:
            store.close()
        self.assertEqual(project_files(self.root / '.evolve-local/backups'), backup_before)
        result = self.cli(self.update, 'maintain', self.request({'operation_id': operation['id']}), method='recover')['data']
        self.assertEqual(result['outcome'], 'needs_recovery')
        self.assertEqual(result['conflicts'], ['total.py'])
        self.assertEqual((self.root / 'total.py').read_text(), third)
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        self.assertGreater(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (original['id'],))[0]['status'], 'started')

    def test_model_controller_preflight_uses_the_selected_version_without_creating_profile(self):
        lab = self.install_root / 'must-not-be-created'
        process = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_acceptance.py'),
                                  '--host', 'claude', '--package', str(self.update), '--out', str(lab),
                                  '--claude-model', 'MiniMax-M3.1-Flash', '--preflight-only'],
                                 text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        observed = json.loads(process.stdout)
        self.assertEqual(observed['package_version'], self.new_manifest['package_version'])
        self.assertEqual(observed['content_digest'], self.new_manifest['content_digest'])
        self.assertFalse(observed['model_requests_sent'])
        self.assertFalse(observed['host_profile_created'])
        self.assertFalse(lab.exists())
