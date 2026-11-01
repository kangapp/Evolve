"""Hard process exits at file/database boundaries, not simulated passing receipts."""
import json
from pathlib import Path
import subprocess
import sys

from workflow_fixture import WorkflowFixture
from evolve_core.recover import recover
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.verify import verify


CHILD = '''
import importlib,json,os,sys
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
app=importlib.import_module('evolve_core.apply')
point=sys.argv[3]
targets={'before-operation':'claim_resources', 'before-journal':'prepare_files',
         'after-files':'fingerprint', 'before-journal-finalize':'finish_journal'}
if point == 'before-run-finish':
    context=patch.object(app.Store,'finish',side_effect=lambda *a,**k:os._exit(35))
else:
    context=patch.object(app,targets[point],side_effect=lambda *a,**k:os._exit(35))
with context:
    app.implement(Path(sys.argv[2]),json.load(sys.stdin))
'''

METADATA_CHILD = '''
import importlib,json,os,sys
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
app=importlib.import_module('evolve_core.'+sys.argv[3])
if sys.argv[4] == 'before-run-finish':
    context=patch.object(app.Store,'finish',side_effect=lambda *a,**k:os._exit(35))
else:
    context=patch.object(app,'check_basis' if sys.argv[3]=='verify' else 'gate',side_effect=lambda *a,**k:os._exit(35))
with context:
    getattr(app,sys.argv[3])(Path(sys.argv[2]),json.load(sys.stdin))
'''


class ProcessCrashTests(WorkflowFixture):
    def crash(self, point):
        request = self.apply_request()
        process = subprocess.run([sys.executable, '-B', '-c', CHILD,
                                  str(Path(__file__).resolve().parents[1] / 'runtime'), str(self.root), point],
                                 input=json.dumps(request), text=True, capture_output=True)
        self.assertEqual(process.returncode, 35, process.stderr)
        return self.rows('SELECT * FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]

    def test_exit_after_run_start_preserves_observed_facts_without_inventing_effects(self):
        original = self.crash('before-operation')
        result = recover(self.root, self.request({'run_id': original['id']}))
        self.assertEqual(result['outcome'], 'recovered_registration')
        self.assertFalse(result['implementation_completed'])
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'todo')
        self.assertIn('len(values)', (self.root / 'total.py').read_text())

    def test_exit_after_operation_prepare_before_journal_does_not_dispatch_files(self):
        original = self.crash('before-journal')
        operation = self.rows('SELECT * FROM operations WHERE run_id=?', (original['id'],))[0]
        self.assertIsNone(operation['journal_path'])
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'recovered_registration')
        self.assertIn('len(values)', (self.root / 'total.py').read_text())
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)

    def test_exit_after_file_write_reconciles_actual_files_without_running_checks(self):
        original = self.crash('after-files')
        operation = self.rows('SELECT * FROM operations WHERE run_id=?', (original['id'],))[0]
        self.assertIn('sum(values)', (self.root / 'total.py').read_text())
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertEqual(result['checks'], 'not_run')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)

    def test_exit_after_database_commit_only_finalizes_the_saved_file_journal(self):
        original = self.crash('before-journal-finalize')
        operation = self.rows('SELECT * FROM operations WHERE run_id=?', (original['id'],))[0]
        self.assertEqual(operation['state'], 'committed')
        stamp = (self.root / 'total.py').stat().st_mtime_ns
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertEqual((self.root / 'total.py').stat().st_mtime_ns, stamp)

    def test_exit_after_task_done_does_not_erase_real_task_completion_or_check_evidence(self):
        original = self.crash('before-run-finish')
        operation = self.rows('SELECT * FROM operations WHERE run_id=?', (original['id'],))[0]
        old_task = self.rows('SELECT * FROM tasks')[0]
        self.assertEqual(old_task['state'], 'done')
        evidence = self.rows('SELECT COUNT(*) n FROM evidence')[0]['n']
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertEqual(self.rows('SELECT * FROM tasks')[0], old_task)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], evidence)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM verifications')[0]['n'], 0)

    def test_external_revert_after_committed_files_is_not_overwritten_by_recovery(self):
        original = self.crash('before-journal-finalize')
        operation = self.rows('SELECT * FROM operations WHERE run_id=?', (original['id'],))[0]
        (self.root / 'total.py').write_text('def total(values):\n    return len(values)\n')
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'needs_recovery')
        self.assertIn('len(values)', (self.root / 'total.py').read_text())


class MetadataCrashTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        implement(self.root, self.apply_request())

    def crash(self, action, point, request):
        process = subprocess.run([sys.executable, '-B', '-c', METADATA_CHILD,
            str(Path(__file__).resolve().parents[1] / 'runtime'), str(self.root), action, point],
            input=json.dumps(request), text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 35, process.stderr)
        original = self.rows('SELECT * FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]
        return original, self.rows('SELECT * FROM operations WHERE run_id=?', (original['id'],))[0]

    def test_interrupted_verification_keeps_task_facts_and_does_not_invent_check_success(self):
        original, operation = self.crash('verify', 'before-final-transaction', self.verification_request())
        old_task = self.rows('SELECT * FROM tasks')[0]
        evidence = self.rows('SELECT * FROM evidence')
        result = recover(self.root, self.request({'run_id': original['id']}))
        self.assertEqual(result['outcome'], 'recovered_metadata')
        self.assertFalse(result['business_commands_run'])
        self.assertEqual(self.rows('SELECT status FROM verifications')[0]['status'], 'blocked')
        self.assertEqual(self.rows('SELECT * FROM tasks')[0], old_task)
        self.assertEqual(self.rows('SELECT * FROM evidence'), evidence)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (original['id'],))[0]['status'], 'interrupted')
        self.assertEqual(verify(self.root, self.verification_request())['status'], 'passed')

    def test_committed_verification_is_sealed_without_rerunning_checks(self):
        original, operation = self.crash('verify', 'before-run-finish', self.verification_request())
        saved = self.rows('SELECT * FROM verifications')[0]
        evidence = self.rows('SELECT * FROM evidence')
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertTrue(result['original_facts_committed'])
        self.assertEqual(self.rows('SELECT * FROM verifications')[0], saved)
        self.assertEqual(self.rows('SELECT * FROM evidence'), evidence)
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (original['id'],))[0]['status'], 'interrupted')
        self.assertEqual(archive(self.root, self.request({'verification_id': saved['id']}))['outcome'], 'archived')

    def test_interrupted_archive_does_not_complete_uncommitted_work(self):
        verified = verify(self.root, self.verification_request())
        original, operation = self.crash('archive', 'before-final-transaction',
                                       self.request({'verification_id': verified['verification_id']}))
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertFalse(result['original_facts_committed'])
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'active')
        self.assertEqual(archive(self.root, self.request({'verification_id': verified['verification_id']}))['outcome'], 'archived')

    def test_committed_archive_is_preserved_and_recovery_replay_is_idempotent(self):
        verified = verify(self.root, self.verification_request())
        original, operation = self.crash('archive', 'before-run-finish',
                                       self.request({'verification_id': verified['verification_id']}))
        change = self.rows('SELECT * FROM changes')[0]
        request = self.request({'operation_id': operation['id']})
        result = recover(self.root, request)
        self.assertTrue(result['original_facts_committed'])
        self.assertEqual(recover(self.root, request), result)
        self.assertEqual(self.rows('SELECT * FROM changes')[0], change)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='change_archived'")[0]['n'], 1)

