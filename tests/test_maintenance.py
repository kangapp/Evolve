"""Actual offline swaps, process drains and abrupt-exit resumes in temporary projects."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from evolve_core import PROTOCOL_VERSION
from evolve_core import maintenance
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.knowledge import propose_baseline, apply_baseline
from evolve_core.package import canonical, digest
from evolve_core.protection import protected_identity
from evolve_core.reading import current_state
from evolve_core.store import Store
from evolve_core.workspace import writer_lock


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-maintenance-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.auth = {'source': 'actual-uniform-user-authorization-controlled-temporary-plan',
            'text': 'In this temporary fixture only, register exact Terms and Extra knowledge, back up, corrupt and restore archive; never restore business code.',
            'effect_kinds': ['project_records', 'knowledge'], 'paths': ['terms.md', 'extra.md']}
        result = connect(self.root, {'authorization': self.auth, 'input': {}})
        self.identity = {'project_id': result['project_id'], 'expected_workspace_epoch': result['workspace_epoch']}
        self.register('terms.md', '# Terms\n\nTotal means sum.\n')
        (self.root / 'business.py').write_text('answer = 42\n')

    def request(self, data=None, request_id=None):
        value = {**self.identity, 'authorization': self.auth, 'input': data or {}}
        if request_id:
            value['request_id'] = request_id
        return value

    def register(self, path, text):
        item = propose_baseline(self.root, self.request({'path': path, 'expected_digest': None, 'content': text,
            'presentation': {'source': 'exact-controlled-fixture', 'text': text}}))
        return apply_baseline(self.root, self.request({'proposal_id': item['proposal_id'], 'approval': {
            'proposal_version': item['proposal_version'], 'candidate_digest': item['candidate_digest'],
            'expected_digest': None, 'source': 'uniform-human-authorization-and-specific-temporary-fixture',
            'text': 'Apply exactly the presented temporary document.'}}))

    def backup(self, request_id='selected-backup'):
        return maintenance.backup(self.root, self.request(request_id=request_id))

    def plan(self, saved, request_id='restore-plan'):
        return maintenance.restore(self.root, self.request({'stage': 'plan', 'bundle': saved['path'],
            'manifest_digest': saved['manifest_digest']}, request_id))

    def apply(self, plan, request_id='restore-apply'):
        return self.request({'stage': 'apply', 'plan_id': plan['plan']['plan_id'],
            'plan_digest': plan['plan_digest']}, request_id)

    def assert_error(self, code, function, *args):
        with self.assertRaises(EvolveError) as error:
            function(*args)
        self.assertEqual(error.exception.code, code)

    def corrupt(self):
        (self.root / 'evolve/history.db').write_bytes(b'actual damaged SQLite bytes\x00\xff')

    def test_corrupt_restore_protects_raw_database_sidecar_extra_managed_and_unknown_files(self):
        saved = self.backup()
        self.register('extra.md', '# Extra\n\nLater approved fact.\n')
        external = 'Unapproved current Terms from another editor.\n'
        (self.root / 'terms.md').write_text(external)
        (self.root / 'unknown.md').write_text('Keep user file.\n')
        self.corrupt()
        sidecar = self.root / 'evolve/history.db-wal'
        sidecar.write_bytes(b'actual damaged sidecar')
        plan = self.plan(saved)
        self.assertEqual(plan['plan']['quarantined_managed'], ['extra.md'])
        request = self.apply(plan)
        result = maintenance.restore(self.root, request)
        self.assertEqual(result['outcome'], 'restored')
        self.assertNotEqual(result['workspace_epoch'], self.identity['expected_workspace_epoch'])
        self.assertEqual((self.root / 'terms.md').read_text(), '# Terms\n\nTotal means sum.\n')
        self.assertFalse((self.root / 'extra.md').exists())
        self.assertFalse(sidecar.exists())
        self.assertEqual((self.root / 'unknown.md').read_text(), 'Keep user file.\n')
        self.assertEqual((self.root / 'business.py').read_text(), 'answer = 42\n')
        protected = Path(result['protection'])
        self.assertEqual((protected / 'evolve/history.db').read_bytes(), b'actual damaged SQLite bytes\x00\xff')
        self.assertEqual((protected / 'evolve/history.db-wal').read_bytes(), b'actual damaged sidecar')
        self.assertEqual((protected / 'terms.md').read_text(), external)
        self.assertEqual((protected / 'extra.md').read_text(), '# Extra\n\nLater approved fact.\n')
        self.assertEqual(maintenance.restore(self.root, request), result)
        store = Store(self.root)
        try:
            self.assertEqual(store.one("SELECT COUNT(*) FROM phase_runs WHERE status='started'")[0], 0)
            self.assertEqual(store.one('SELECT COUNT(*) FROM resource_claims')[0], 0)
            with self.assertRaises(EvolveError) as error:
                store.start(self.request(request_id='old-epoch'), action='maintain', method='backup', owner='evolve-maintain')
            self.assertEqual(error.exception.code, 'WORKSPACE_EPOCH')
        finally:
            store.close()
        protected_identity(self.root)
        self.assertEqual(current_state(self.root)['state'], 'connected')

    def test_plan_binds_bytes_selected_package_and_preserves_unregistered_collision(self):
        saved = self.backup()
        plan = self.plan(saved)
        (self.root / 'terms.md').write_text('New external third value.\n')
        self.assert_error('RESTORE_CHANGED', maintenance.restore, self.root, self.apply(plan))
        self.assertEqual((self.root / 'terms.md').read_text(), 'New external third value.\n')
        self.assertFalse((self.root / '.evolve-local/control/maintenance.json').exists())
        # The selected archive may contain knowledge removed from the local registration.
        guard, index = protected_identity(self.root)
        index['files'] = [r for r in index['files'] if r['path'] != 'terms.md']
        value = canonical(index)
        (self.root / '.evolve-local/control/managed.json').write_bytes(value)
        guard['managed_index_digest'] = digest(value)
        (self.root / '.evolve-local/control/guard.json').write_bytes(canonical(guard))
        self.corrupt()
        self.assert_error('RESTORE_COLLISION', self.plan, saved, 'collision-plan')

    def test_held_old_sqlite_connection_and_real_old_writer_block_swap(self):
        saved = self.backup()
        old = Store(self.root)
        try:
            self.assert_error('DATABASE_OPEN', self.plan, saved)
        finally:
            old.close()
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(lambda: child.poll() is None and (child.terminate(), child.wait()))
        guard, index = protected_identity(self.root)
        index['executions'] = [{'id': 'real-old-owner', 'execution_instance': json.dumps({
            'pid': child.pid, 'host': __import__('socket').gethostname(), 'generation': 'controlled-child'})}]
        encoded = canonical(index)
        (self.root / '.evolve-local/control/managed.json').write_bytes(encoded)
        guard['managed_index_digest'] = digest(encoded)
        (self.root / '.evolve-local/control/guard.json').write_bytes(canonical(guard))
        self.corrupt()
        self.assert_error('WRITER_ACTIVE', self.plan, saved)
        child.terminate(); child.wait()
        plan = self.plan(saved)
        self.assertEqual(maintenance.restore(self.root, self.apply(plan))['outcome'], 'restored')

    def test_unknown_check_launch_needs_specific_observation_and_real_group_must_end(self):
        saved = self.backup()
        path = self.root / '.evolve-local/control/checks.json'
        value = json.loads(path.read_text())
        from evolve_core.store import now
        import socket
        attempt = {'execution_id': 'real-attempt', 'command_digest': 'exact-command',
                   'host': socket.gethostname(), 'prepared_at': now()}
        value['attempts'] = {'real-attempt': attempt}
        path.write_bytes(canonical(value))
        self.corrupt()
        self.assert_error('CHECK_EXECUTION_UNKNOWN', self.plan, saved)
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        self.addCleanup(lambda: child.poll() is None and (os.killpg(child.pid, signal.SIGTERM), child.wait()))
        value['attempts']['real-attempt']['pid'] = child.pid
        path.write_bytes(canonical(value))
        self.assert_error('CHECK_RUNNING', self.plan, saved)
        os.killpg(child.pid, signal.SIGTERM); child.wait()
        self.assertEqual(maintenance.restore(self.root, self.apply(self.plan(saved)))['outcome'], 'restored')

    def test_external_running_reference_survives_older_archive_as_unknown(self):
        saved = self.backup()
        path = self.root / '.evolve-local/control/external.json'
        value = json.loads(path.read_text())
        value['pending'] = [{'operation_id': 'controlled-reference-only-no-dispatch', 'state': 'running',
                             'resources': ['temporary:test-target'], 'target': 'temporary-only'}]
        path.write_bytes(canonical(value))
        self.corrupt()
        result = maintenance.restore(self.root, self.apply(self.plan(saved)))
        after = json.loads(path.read_text())
        self.assertEqual(result['external_pending'], 1)
        self.assertEqual(after['pending'][0]['operation_id'], 'controlled-reference-only-no-dispatch')
        self.assertEqual(after['pending'][0]['state'], 'unknown')
        self.assertTrue(after['pending'][0]['requires_reconciliation'])
        self.assertNotEqual(after['workspace_epoch'], value['workspace_epoch'])

    def test_missing_current_external_index_blocks_and_only_legacy_absence_is_unverified(self):
        saved = self.backup()
        (self.root / '.evolve-local/control/external.json').unlink()
        self.corrupt()
        self.assert_error('EXTERNAL_PROTECTION_UNKNOWN', self.plan, saved)
        self.assertEqual(maintenance.external_protection(self.root, self.identity['project_id'], protocol_version='15')['coverage'], 'unverified')
        self.assertFalse((self.root / '.evolve-local/control/external.json').exists())

    def test_inconsistent_protection_and_capacity_do_not_touch_original(self):
        saved = self.backup()
        self.corrupt()
        index = self.root / '.evolve-local/control/managed.json'
        original = index.read_bytes()
        index.write_bytes(original + b' ')
        self.assert_error('PROTECTION_UNKNOWN', self.plan, saved)
        index.write_bytes(original)
        plan = self.plan(saved)
        with patch.object(maintenance.shutil, 'disk_usage', return_value=type('Space', (), {'free': 0})()):
            self.assert_error('ARCHIVE_SPACE', maintenance.restore, self.root, self.apply(plan))
        self.assertEqual((self.root / 'evolve/history.db').read_bytes(), b'actual damaged SQLite bytes\x00\xff')
        self.assertEqual(current_state(self.root)['state'], 'maintenance')
        self.assert_error('MAINTENANCE_ACTIVE', Store, self.root)
        self.assertEqual(maintenance.restore(self.root, self.apply(plan))['outcome'], 'restored')

    def test_explicit_protocol_upgrade_changes_epoch_and_preserves_history(self):
        # Create an actual supported old-protocol file; ordinary init must not migrate it.
        database = self.root / 'evolve/history.db'
        connection = sqlite3.connect(database)
        count = connection.execute('SELECT COUNT(*) FROM phase_runs').fetchone()[0]
        connection.execute("UPDATE project_meta SET value='14' WHERE key='protocol_version'")
        connection.commit(); connection.close()
        self.assert_error('SCHEMA_VERSION', Store, self.root)
        self.assert_error('SCHEMA_VERSION', connect, self.root, self.request())
        plan = maintenance.upgrade(self.root, self.request({'stage': 'plan'}, 'upgrade-plan'))
        result = maintenance.upgrade(self.root, self.apply(plan, 'upgrade-apply'))
        store = Store(self.root)
        try:
            self.assertEqual(store.meta['protocol_version'], str(PROTOCOL_VERSION))
            self.assertEqual(store.one('SELECT COUNT(*) FROM phase_runs')[0], count)
        finally:
            store.close()
        self.assertNotEqual(result['workspace_epoch'], self.identity['expected_workspace_epoch'])

    def fault_subprocess(self, request, point):
        request_path = self.root / 'controlled-restore-request.json'
        request_path.write_bytes(canonical(request))
        code = '''import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from evolve_core import maintenance
def crash(name):
    if name == sys.argv[4]: os._exit(73)
maintenance.fault_point = crash
maintenance.restore(Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text()))
'''
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'), str(self.root),
                                 str(request_path), point], capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 73, result.stderr)

    def test_actual_abrupt_exit_at_every_swap_boundary_resumes_same_request(self):
        # Each case is a separate real crash and a separate new epoch, never a mocked transaction.
        points = ['barrier', 'staged', 'prepared', 'before:evolve/config.toml', 'after:evolve/config.toml',
                  'before:terms.md', 'after:terms.md', 'before:evolve/history.db', 'after:evolve/history.db',
                  'after:.evolve-local/control/managed.json', 'after:.evolve-local/control/guard.json', 'completed']
        for i, point in enumerate(points):
            with self.subTest(point=point):
                saved = self.backup('fault-backup-' + str(i))
                (self.root / 'terms.md').write_text('External Terms before actual swap.\n')
                config = self.root / 'evolve/config.toml'
                config.write_text(config.read_text() + '\n# external current config\n')
                plan = self.plan(saved, 'fault-plan-' + str(i))
                request = self.apply(plan, 'fault-apply-' + str(i))
                self.fault_subprocess(request, point)
                self.assertEqual(current_state(self.root)['state'], 'maintenance')
                result = maintenance.restore(self.root, request)
                self.assertEqual(result['outcome'], 'restored')
                self.assertEqual(current_state(self.root)['state'], 'connected')
                self.identity['expected_workspace_epoch'] = result['workspace_epoch']
                self.assertEqual((self.root / 'business.py').read_text(), 'answer = 42\n')

    def test_third_party_value_after_partial_swap_is_preserved_with_barrier(self):
        saved = self.backup()
        plan = self.plan(saved)
        request = self.apply(plan)
        self.fault_subprocess(request, 'after:terms.md')
        (self.root / 'terms.md').write_text('Third-party edit during stopped restore.\n')
        self.assert_error('RESTORE_CHANGED', maintenance.restore, self.root, request)
        self.assertEqual((self.root / 'terms.md').read_text(), 'Third-party edit during stopped restore.\n')
        self.assertEqual(current_state(self.root)['state'], 'maintenance')

    def test_changed_swap_journal_cannot_expand_the_presented_restore_collection(self):
        saved = self.backup()
        plan = self.plan(saved)
        request = self.apply(plan)
        self.fault_subprocess(request, 'prepared')
        folder = self.root / '.evolve-local/control/restores/restore-plan'
        path = folder / 'journal.json'
        journal = json.loads(path.read_text())
        step = journal['steps'][0]
        step['path'] = 'business.py'
        step['before'] = digest((self.root / 'business.py').read_bytes())
        path.write_bytes(canonical(journal))
        self.assert_error('JOURNAL_INVALID', maintenance.restore, self.root, request)
        self.assertEqual((self.root / 'business.py').read_text(), 'answer = 42\n')
        self.assertEqual(current_state(self.root)['state'], 'maintenance')

    def test_unknown_launch_observation_is_bound_and_missing_check_index_is_not_safe(self):
        saved = self.backup()
        path = self.root / '.evolve-local/control/checks.json'
        original = path.read_bytes()
        path.unlink()
        self.corrupt()
        self.assert_error('PROTECTION_UNKNOWN', self.plan, saved)
        value = json.loads(original)
        from evolve_core.store import now
        import socket
        attempt = {'execution_id': 'unknown-dispatch', 'command_digest': 'exact-command',
                   'host': socket.gethostname(), 'prepared_at': now()}
        value['attempts'] = {'unknown-dispatch': attempt}
        path.write_bytes(canonical(value))
        observation = {**attempt, 'outcome': 'not_started', 'source': 'controlled-fixture-no-process-was-launched',
                       'basis': 'Only this intent was written by the test controller; no child was created.', 'observed_at': now()}
        request = self.request({'stage': 'plan', 'bundle': saved['path'], 'manifest_digest': saved['manifest_digest'],
            'check_observations': [observation]}, 'observed-launch-plan')
        plan = maintenance.restore(self.root, request)
        apply_request = self.apply(plan)
        self.fault_subprocess(apply_request, 'after:.evolve-local/control/checks.json')
        result = maintenance.restore(self.root, apply_request)
        self.assertFalse(result['checks_run'])
        self.assertEqual(result['outcome'], 'restored')

    def test_actual_divergent_archives_keep_both_branches_and_restore_only_the_selected_one(self):
        import shutil
        with tempfile.TemporaryDirectory(prefix='evolve-real-history-fork-') as directory:
            branch = Path(directory).resolve() / 'branch'
            shutil.copytree(self.root, branch)
            branch_auth = {**self.auth, 'paths': ['terms.md', 'left.md', 'right.md'],
                           'text': 'Under actual uniform human authorization, create exactly Left fact and Right fact in two temporary history branches; explicitly select Right archive, protect Left, never merge.'}
            def register_at(root, name, text):
                base = {**self.identity, 'authorization': branch_auth}
                proposal = propose_baseline(root, {**base, 'input': {'path': name, 'content': text, 'expected_digest': None,
                    'presentation': {'source': 'exact-controlled-divergent-fixture', 'text': text}}})
                apply_baseline(root, {**base, 'input': {'proposal_id': proposal['proposal_id'], 'approval': {
                    'proposal_version': proposal['proposal_version'], 'candidate_digest': proposal['candidate_digest'],
                    'expected_digest': None, 'source': 'actual-uniform-authorization-specific-branch-fixture',
                    'text': 'Apply exactly this temporary branch baseline.'}}})
            register_at(self.root, 'left.md', '# Left fact\n')
            left = self.backup('left-archive')
            register_at(branch, 'right.md', '# Right fact\n')
            right = maintenance.backup(branch, {**self.identity, 'request_id': 'right-archive',
                                               'authorization': branch_auth, 'input': {}})
            left_manifest = (Path(left['path']) / 'manifest.json').read_bytes()
            right_manifest = (Path(right['path']) / 'manifest.json').read_bytes()
            # A real unregistered collision must stop before selecting the branch.
            (self.root / 'right.md').write_text('Unregistered current user note.\n')
            self.assert_error('RESTORE_COLLISION', self.plan, right, 'unknown-right-collision')
            self.assertEqual((self.root / 'right.md').read_text(), 'Unregistered current user note.\n')
            (self.root / 'right.md').unlink()  # Controller removes only its own negative fixture.
            selected = self.plan(right, 'explicit-right-branch')
            result = maintenance.restore(self.root, self.apply(selected))
            self.assertFalse((self.root / 'left.md').exists())
            self.assertEqual((self.root / 'right.md').read_text(), '# Right fact\n')
            self.assertEqual((Path(result['protection']) / 'left.md').read_text(), '# Left fact\n')
            self.assertEqual((Path(left['path']) / 'manifest.json').read_bytes(), left_manifest)
            self.assertEqual((Path(right['path']) / 'manifest.json').read_bytes(), right_manifest)
            self.assertEqual((branch / 'right.md').read_text(), '# Right fact\n')
            self.assertFalse((branch / 'left.md').exists())
            self.assertEqual((self.root / 'business.py').read_text(), 'answer = 42\n')
            store = Store(self.root)
            try:
                formal = {r[0] for r in store.connection.execute("SELECT path FROM artifacts WHERE kind='knowledge'")}
                self.assertEqual(formal, {'terms.md', 'right.md'})
                self.assertNotEqual(store.meta['workspace_epoch'], self.identity['expected_workspace_epoch'])
            finally:
                store.close()

    def test_archive_database_changed_after_validation_is_not_installed(self):
        saved = self.backup()
        plan = self.plan(saved)
        original = (self.root / 'evolve/history.db').read_bytes()
        actual = maintenance.candidate_database
        marker = b'unapproved archive payload inserted after validation'
        def changed(source, target, selected_plan, **kwargs):
            with sqlite3.connect(source) as db:
                db.execute('INSERT INTO blobs VALUES (?,?)', (digest(marker), marker))
            return actual(source, target, selected_plan, **kwargs)
        with patch.object(maintenance, 'candidate_database', side_effect=changed):
            self.assert_error('ARCHIVE_CHANGED', maintenance.restore, self.root, self.apply(plan))
        self.assertEqual((self.root / 'evolve/history.db').read_bytes(), original)
        self.assertEqual((self.root / 'terms.md').read_text(), '# Terms\n\nTotal means sum.\n')

    def test_an_actual_other_project_archive_cannot_replace_this_history(self):
        with tempfile.TemporaryDirectory(prefix='evolve-other-archive-project-') as directory:
            other = Path(directory).resolve()
            connected = connect(other, {'authorization': self.auth, 'input': {}})
            saved = maintenance.backup(other, {'request_id': 'foreign-project-backup',
                'project_id': connected['project_id'], 'expected_workspace_epoch': connected['workspace_epoch'],
                'authorization': self.auth, 'input': {}})
            database = (self.root / 'evolve/history.db').read_bytes()
            terms = (self.root / 'terms.md').read_bytes()
            self.assert_error('PROJECT_IDENTITY', self.plan, saved, 'foreign-project-refused')
            self.assertEqual((self.root / 'evolve/history.db').read_bytes(), database)
            self.assertEqual((self.root / 'terms.md').read_bytes(), terms)
            self.assertFalse((self.root / '.evolve-local/control/maintenance.json').exists())

    def test_manual_backup_does_not_trigger_another_full_daily_backup(self):
        with tempfile.TemporaryDirectory(prefix='evolve-backup-no-recursion-') as directory:
            root = Path(directory).resolve()
            connected = connect(root, {'authorization': self.auth, 'input': {}})
            result = maintenance.backup(root, {'request_id': 'only-explicit-backup',
                'project_id': connected['project_id'], 'expected_workspace_epoch': connected['workspace_epoch'],
                'authorization': self.auth, 'input': {}})
            manifests = list((root / '.evolve-local/backups').rglob('manifest.json'))
            self.assertEqual(len(manifests), 1, 'Explicit backup must not trigger a second full protection backup')
            self.assertEqual(manifests[0].parent, Path(result['path']))

    def test_manual_backup_retry_and_next_write_after_restore_keep_old_daily_points(self):
        request = self.request(request_id='manual-idempotent')
        saved = maintenance.backup(self.root, request)
        self.assertEqual(maintenance.backup(self.root, request), saved)
        with self.assertRaises(EvolveError) as error:
            maintenance.backup(self.root, {**request, 'input': {'changed': True}})
        self.assertEqual(error.exception.code, 'REQUEST_CONFLICT')
        result = maintenance.restore(self.root, self.apply(self.plan(saved)))
        self.identity['expected_workspace_epoch'] = result['workspace_epoch']
        self.register('extra.md', '# Extra\n\nNew epoch approved fixture.\n')
        again = self.backup('new-epoch-backup')
        self.assertTrue(Path(saved['path']).is_dir())
        self.assertTrue(Path(again['path']).is_dir())
        daily = list((self.root / '.evolve-local/backups').glob('20*/manifest.json'))
        self.assertEqual(len(daily), 2)
