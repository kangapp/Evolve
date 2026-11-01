"""Reconcile prepared file writes while preserving conflicts and prior evidence."""
import json
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
from evolve_core.recover import recover
from evolve_core.store import Store


class LocalRecoveryTests(WorkflowFixture):
    def interrupted_apply(self):
        with patch('evolve_core.apply.install_files', side_effect=OSError('injected interruption before file installation')):
            with self.assertRaises(EvolveError) as caught:
                implement(self.root, self.apply_request())
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        return self.rows("SELECT * FROM operations WHERE effect_kind='business_files'")[0]

    def test_recovery_finishes_only_authorized_file_bytes_without_rerunning_checks(self):
        operation = self.interrupted_apply()
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertFalse(result['business_commands_run'])
        self.assertEqual(result['checks'], 'not_run')
        self.assertIn('sum(values)', (self.root / 'total.py').read_text())
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (operation['run_id'],))[0]['status'], 'interrupted')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)
        self.assertTrue((self.root / result['protection'] / 'manifest.json').exists())
        # A later apply performs the real checks, using the preserved result basis.
        self.assertEqual(implement(self.root, self.apply_request())['outcome'], 'implemented')

    def test_recovery_replay_is_idempotent_after_original_run_becomes_terminal(self):
        operation = self.interrupted_apply()
        request = self.request({'operation_id': operation['id']})
        first = recover(self.root, request)
        count = self.rows('SELECT COUNT(*) n FROM phase_runs')[0]['n']
        self.assertEqual(recover(self.root, request), first)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM phase_runs')[0]['n'], count)

    def test_legacy_operation_recovers_from_original_resource_digest_without_inventing_a_binding(self):
        operation = self.interrupted_apply()
        store = Store(self.root)
        try:
            with store.transaction() as connection:
                connection.execute("DELETE FROM events WHERE run_id=? AND kind='file_targets_bound'", (operation['run_id'],))
        finally:
            store.close()
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertFalse(result['business_commands_run'])
        self.assertIn('sum(values)', (self.root / 'total.py').read_text())
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE run_id=? AND kind='file_targets_bound'", (operation['run_id'],))[0]['n'], 0)

    def test_recovery_preserves_third_party_content_and_keeps_pending_claim(self):
        operation = self.interrupted_apply()
        (self.root / 'total.py').write_text('external edit that must survive')
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'needs_recovery')
        self.assertEqual(result['conflicts'], ['total.py'])
        self.assertEqual((self.root / 'total.py').read_text(), 'external edit that must survive')
        self.assertGreater(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (operation['run_id'],))[0]['status'], 'started')

    def test_tampered_journal_cannot_expand_the_original_authorization(self):
        operation = self.interrupted_apply()
        path = self.root / '.evolve-local/control/operations' / (operation['id'] + '.json')
        journal = json.loads(path.read_text())
        journal['files'][0]['path'] = 'other.py'
        path.write_text(json.dumps(journal))
        with self.assertRaises(EvolveError) as caught:
            recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(caught.exception.code, 'JOURNAL_INVALID')
        self.assertFalse((self.root / 'other.py').exists())

    def test_live_original_execution_is_not_taken_over_without_a_stop_fact(self):
        operation = self.interrupted_apply()
        import sqlite3
        connection = sqlite3.connect(self.root / 'evolve/history.db')
        connection.execute("DELETE FROM events WHERE kind='implementation_interrupted'")
        connection.commit()
        connection.close()
        with self.assertRaises(EvolveError) as caught:
            recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(caught.exception.code, 'WRITER_ACTIVE')
