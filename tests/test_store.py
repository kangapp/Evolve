"""Persistent request and checkpoint behavior; no fabricated workflow completion."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.errors import EvolveError
from evolve_core.store import Store, create_database


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-store-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'evolve').mkdir()
        self.database = self.root / 'evolve/history.db'
        create_database(self.database, 'project-a', 'epoch-a')
        (self.root / 'evolve/config.toml').write_text('config_version=1\n[project]\nid="project-a"\n')
        # This deliberately bare database tests the persistence primitive, not a
        # connected archive (it has no registered configuration). Complete archive
        # behavior is exercised with real init in test_backup/test_archive_sets.
        protection = patch('evolve_core.backup.protect_before_write', return_value='unit-store-fixture-no-archive')
        protection.start()
        self.addCleanup(protection.stop)
        self.request = {'request_id': 'request-a', 'project_id': 'project-a',
                        'expected_workspace_epoch': 'epoch-a',
                        'authorization': {'source': 'test-fixture', 'effect_kind': 'project_records'},
                        'input': {'purpose': 'persistence test'}}

    def open(self):
        store = Store(self.root)
        self.addCleanup(store.close)
        return store

    def start(self, store, request=None):
        return store.start(request or self.request, action='propose', method='create', owner='evolve-propose')

    def test_same_request_returns_original_sealed_result_and_one_run(self):
        store = self.open()
        run_id, previous = self.start(store)
        self.assertIsNone(previous)
        result = store.finish(run_id, {'committed': True, 'outcome': 'recorded'})
        repeated_id, repeated = self.start(store)
        self.assertEqual((repeated_id, repeated), (run_id, result))
        self.assertEqual(store.one('SELECT COUNT(*) FROM phase_runs')[0], 1)
        self.assertEqual(store.one('SELECT COUNT(*) FROM events')[0], 3)

    def test_same_identity_different_input_is_rejected(self):
        store = self.open()
        run_id, _ = self.start(store)
        store.finish(run_id, {'outcome': 'recorded'})
        changed = {**self.request, 'input': {'purpose': 'different request'}}
        with self.assertRaises(EvolveError) as caught:
            self.start(store, changed)
        self.assertEqual(caught.exception.code, 'REQUEST_CONFLICT')

    def test_old_epoch_request_is_not_replayed_even_with_same_identity(self):
        store = self.open()
        run_id, _ = self.start(store)
        store.finish(run_id, {'outcome': 'recorded'})
        with self.assertRaises(EvolveError) as caught:
            self.start(store, {**self.request, 'expected_workspace_epoch': 'old-epoch'})
        self.assertEqual(caught.exception.code, 'WORKSPACE_EPOCH')

    def test_unfinished_request_requires_recovery_instead_of_reexecution(self):
        store = self.open()
        self.start(store)
        with self.assertRaises(EvolveError) as caught:
            self.start(store)
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')

    def test_terminal_result_is_immutable(self):
        store = self.open()
        run_id, _ = self.start(store)
        original = store.finish(run_id, {'outcome': 'partial'})
        with self.assertRaises(EvolveError):
            store.finish(run_id, {'outcome': 'different'})
        self.assertEqual(json.loads(store.one('SELECT result_json FROM phase_runs')[0]), original)

    def test_failed_transaction_rolls_back_facts_and_checkpoint(self):
        store = self.open()
        checkpoint = store.meta['checkpoint']
        with self.assertRaises(RuntimeError):
            with store.transaction() as connection:
                connection.execute("INSERT INTO blobs VALUES ('candidate',x'00')")
                raise RuntimeError('injected transaction failure')
        self.assertEqual(store.one('SELECT COUNT(*) FROM blobs')[0], 0)
        self.assertEqual(store.meta['checkpoint'], checkpoint)
        self.assertEqual(store.one("SELECT value FROM project_meta WHERE key='checkpoint'")[0], checkpoint)

    def test_restoring_an_older_database_cannot_silently_reuse_newer_guard(self):
        old = self.database.read_bytes()
        store = Store(self.root)
        run_id, _ = self.start(store)
        store.finish(run_id, {'outcome': 'recorded'})
        store.close()
        self.database.write_bytes(old)
        with self.assertRaises(EvolveError) as caught:
            Store(self.root)
        self.assertEqual(caught.exception.code, 'HISTORY_DIVERGED')

    def test_stale_guard_on_same_checkpoint_lineage_is_accepted_without_rewriting_on_open(self):
        store = self.open()
        self.start(store)
        guard = self.root / '.evolve-local/control/guard.json'
        original = guard.read_bytes()
        with store.transaction() as connection:
            connection.execute("INSERT INTO blobs VALUES ('candidate',x'00')")
        guard.write_bytes(original)
        reopened = self.open()
        self.assertEqual(reopened.one('SELECT COUNT(*) FROM blobs')[0], 1)
        self.assertEqual(guard.read_bytes(), original)

    def test_guard_write_failure_reports_committed_fact_instead_of_safe_retry(self):
        store = self.open()
        with patch('evolve_core.protection.durable_write', side_effect=OSError('injected guard failure')):
            with self.assertRaises(EvolveError) as caught:
                self.start(store)
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        self.assertTrue(caught.exception.committed)
        self.assertEqual(store.one('SELECT COUNT(*) FROM phase_runs')[0], 1)

    def test_foreign_project_cannot_write_into_this_history(self):
        store = self.open()
        with self.assertRaises(EvolveError) as caught:
            self.start(store, {**self.request, 'project_id': 'another-project'})
        self.assertEqual(caught.exception.code, 'PROJECT_IDENTITY')
        self.assertEqual(store.one('SELECT COUNT(*) FROM phase_runs')[0], 0)

    def test_two_open_readers_commit_a_single_checkpoint_lineage(self):
        first, second = self.open(), self.open()
        with first.transaction() as connection:
            connection.execute("INSERT INTO blobs VALUES ('first',x'01')")
        first_head = first.meta['checkpoint']
        with second.transaction() as connection:
            connection.execute("INSERT INTO blobs VALUES ('second',x'02')")
        parent = second.one('SELECT parent_id FROM checkpoints WHERE id=?', (second.meta['checkpoint'],))[0]
        self.assertEqual(parent, first_head)
        reopened = self.open()
        self.assertEqual(reopened.one('SELECT COUNT(*) FROM blobs')[0], 2)

    def test_incomplete_old_schema_is_not_silently_recreated_or_migrated(self):
        connection = sqlite3.connect(self.database)
        connection.execute('DROP TABLE knowledge_proposals')
        connection.commit()
        connection.close()
        original = self.database.read_bytes()
        with self.assertRaises(EvolveError) as caught:
            Store(self.root)
        self.assertEqual(caught.exception.code, 'SCHEMA_VERSION')
        self.assertEqual(self.database.read_bytes(), original)

    def test_corrupt_checkpoint_cycle_is_reported_without_repair_or_unbounded_walk(self):
        store = self.open()
        with store.transaction():
            pass
        guard = self.root / '.evolve-local/control/guard.json'
        previous = guard.read_bytes()
        with store.transaction() as connection:
            pass
        connection = sqlite3.connect(self.database)
        connection.execute('UPDATE checkpoints SET parent_id=id WHERE id=?', (store.meta['checkpoint'],))
        connection.commit()
        connection.close()
        guard.write_bytes(previous)
        before = self.database.read_bytes()
        with self.assertRaises(EvolveError) as caught:
            Store(self.root)
        self.assertEqual(caught.exception.code, 'HISTORY_DIVERGED')
        self.assertEqual(self.database.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
