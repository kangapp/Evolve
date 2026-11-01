"""Protection is collected before facts change and refuses misleading partial sets."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.backup import protect_before_write
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.store import Store


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-backup-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.auth = {'source': 'isolated-test-fixture', 'text': 'Connect this temporary test project',
                     'effect_kinds': ['project_records']}
        self.project = connect(self.root, {'request_id': 'connect', 'input': {}, 'authorization': self.auth})
        self.store = Store(self.root)
        self.addCleanup(self.store.close)

    def request(self):
        return {'request_id': 'first-work', 'project_id': self.project['project_id'],
                'expected_workspace_epoch': self.project['workspace_epoch'],
                'input': {}, 'authorization': self.auth}

    def test_backup_precedes_new_run_and_matches_its_own_checkpoint(self):
        self.store.start(self.request(), action='propose', method='create', owner='evolve-propose')
        manifest_path = next((self.root / '.evolve-local/backups').glob('*/manifest.json'))
        manifest = json.loads(manifest_path.read_text())
        db = sqlite3.connect(manifest_path.parent / 'authority/evolve/history.db')
        try:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM phase_runs').fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT value FROM project_meta WHERE key='checkpoint'").fetchone()[0],
                             manifest['checkpoint'])
        finally:
            db.close()
        self.assertEqual(self.store.one('SELECT COUNT(*) FROM phase_runs')[0], 2)
        self.assertFalse(manifest['business_data_included'])

    def test_daily_backup_is_reused_without_recursive_growth(self):
        reference = protect_before_write(self.store, 'first')
        manifest = (self.root / reference).read_bytes()
        self.assertEqual(protect_before_write(self.store, 'next'), reference)
        self.assertEqual((self.root / reference).read_bytes(), manifest)
        protected = self.root / reference
        self.assertFalse((protected.parent / '.evolve-local').exists())

    def test_corrupt_protection_blocks_new_run_instead_of_claiming_safe_backup(self):
        reference = protect_before_write(self.store, 'first')
        (self.root / reference).parent.joinpath('authority/evolve/history.db').write_bytes(b'corrupted')
        with self.assertRaises(EvolveError) as caught:
            self.store.start(self.request(), action='propose', method='create', owner='evolve-propose')
        self.assertEqual(caught.exception.code, 'ARCHIVE_INVALID')
        self.assertEqual(self.store.one('SELECT COUNT(*) FROM phase_runs')[0], 1)

    def test_unfinished_file_journal_does_not_become_consistent_backup(self):
        directory = self.root / '.evolve-local/control/operations'
        directory.mkdir()
        (directory / 'unfinished.json').write_text('{"state":"prepared"}')
        with self.assertRaises(EvolveError) as caught:
            protect_before_write(self.store, 'first')
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        self.assertFalse((self.root / '.evolve-local/backups').exists())

    def test_reusing_daily_backup_still_checks_for_a_new_pending_operation(self):
        protect_before_write(self.store, 'first')
        directory = self.root / '.evolve-local/control/operations'
        directory.mkdir()
        (directory / 'unfinished.json').write_text('{"state":"prepared"}')
        with self.assertRaises(EvolveError) as caught:
            self.store.start(self.request(), action='propose', method='create', owner='evolve-propose')
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        self.assertEqual(self.store.one('SELECT COUNT(*) FROM phase_runs')[0], 1)

    def test_external_bytes_are_protected_separately_from_registered_configuration(self):
        config = self.root / 'evolve/config.toml'
        original = config.read_bytes()
        edited = original + b'\n# externally edited\n'
        config.write_bytes(edited)
        reference = protect_before_write(self.store, 'first')
        manifest_path = self.root / reference
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual((manifest_path.parent / 'authority/evolve/config.toml').read_bytes(), original)
        observed = manifest['observations'][0]
        self.assertEqual((manifest_path.parent / observed['protected_copy']).read_bytes(), edited)
        self.assertEqual(config.read_bytes(), edited)


if __name__ == '__main__':
    unittest.main()
