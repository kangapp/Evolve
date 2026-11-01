"""Complete archive facts are tested through the same collector and validator used by maintenance."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core import archive_sets
from evolve_core.archive_sets import collect_archive, validate_archive
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.knowledge import propose_baseline, apply_baseline
from evolve_core.package import canonical, digest
from evolve_core.store import Store
from evolve_core.workspace import writer_lock


class ArchiveSetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-archive-set-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.auth = {'source': 'controlled-archive-fixture-under-uniform-user-authorization',
            'text': 'Register exactly the temporary Terms baseline, preserve business bytes, and exercise complete local archive collection.',
            'effect_kinds': ['project_records', 'knowledge'], 'paths': ['terms.md']}
        project = connect(self.root, {'authorization': self.auth, 'input': {}})
        self.identity = {'project_id': project['project_id'], 'expected_workspace_epoch': project['workspace_epoch']}
        self.content = '# Terms\n\nTotal means sum.\n'
        item = propose_baseline(self.root, {**self.identity, 'authorization': self.auth, 'input': {
            'path': 'terms.md', 'expected_digest': None, 'content': self.content,
            'presentation': {'source': 'controlled-specific-baseline', 'text': self.content}}})
        apply_baseline(self.root, {**self.identity, 'authorization': self.auth, 'input': {
            'proposal_id': item['proposal_id'], 'approval': {'proposal_version': item['proposal_version'],
                'candidate_digest': item['candidate_digest'], 'expected_digest': None,
                'source': 'actual-uniform-test-authorization-and-exact-fixture-plan',
                'text': 'Apply only this exact temporary Terms baseline.'}}})
        self.store = Store(self.root)
        self.addCleanup(self.store.close)
        self.destination = self.root / '.evolve-local/backups/sets/selected'

    def collect(self):
        with writer_lock(self.root):
            return collect_archive(self.store, self.destination, 'controlled-archive-request')

    def test_consistent_authority_and_external_appendix_never_include_business_code(self):
        (self.root / 'main.py').write_text('raise RuntimeError("business bytes are outside restore")\n')
        external = self.content + '\nExternal unapproved note.\n'
        (self.root / 'terms.md').write_text(external)
        result = self.collect()
        manifest = validate_archive(self.destination, result['manifest_digest'])
        self.assertEqual({r['path'] for r in manifest['files']}, {'evolve/history.db', 'evolve/config.toml', 'terms.md'})
        self.assertEqual((self.destination / 'authority/terms.md').read_text(), self.content)
        self.assertEqual((self.destination / manifest['observations'][0]['protected_copy']).read_text(), external)
        self.assertEqual((self.root / 'terms.md').read_text(), external)
        self.assertFalse((self.destination / 'authority/main.py').exists())
        self.assertFalse(manifest['business_data_included'])
        with sqlite3.connect(self.destination / 'authority/evolve/history.db') as db:
            self.assertEqual(db.execute("SELECT value FROM project_meta WHERE key='checkpoint'").fetchone()[0], manifest['checkpoint'])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_actual_document_change_after_database_snapshot_refuses_complete_archive(self):
        actual = archive_sets.database_copy
        def changed(connection, target):
            actual(connection, target)
            (self.root / 'terms.md').write_text('External change after database snapshot.\n')
        with patch.object(archive_sets, 'database_copy', side_effect=changed):
            with self.assertRaises(EvolveError) as error:
                self.collect()
        self.assertEqual(error.exception.code, 'ARCHIVE_CHANGED')
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.root / 'terms.md').read_text(), 'External change after database snapshot.\n')
        incomplete = list(self.destination.parent.glob('.incomplete-*'))
        self.assertEqual(len(incomplete), 1)
        self.assertTrue((incomplete[0] / 'authority/evolve/history.db').is_file())
        self.assertFalse((incomplete[0] / 'manifest.json').exists())

    def test_required_blob_damage_is_not_a_complete_backup(self):
        row = self.store.one('SELECT digest FROM blobs LIMIT 1')
        self.store.connection.execute('UPDATE blobs SET content=? WHERE digest=?', (b'damaged immutable bytes', row['digest']))
        with self.assertRaises(EvolveError) as error:
            self.collect()
        self.assertEqual(error.exception.code, 'ARCHIVE_DATABASE')
        self.assertFalse(self.destination.exists())

    def test_pending_file_journal_and_capacity_fail_before_collection(self):
        journal = self.root / '.evolve-local/control/operations/unfinished.json'
        journal.write_text('{"state":"prepared"}')
        with self.assertRaises(EvolveError) as error:
            self.collect()
        self.assertEqual(error.exception.code, 'NEEDS_RECOVERY')
        journal.unlink()
        with patch.object(archive_sets, 'MAX_SET_BYTES', 1):
            with self.assertRaises(EvolveError) as error:
                self.collect()
        self.assertEqual(error.exception.code, 'ARCHIVE_CAPACITY')
        self.assertFalse(self.destination.exists())
        with patch.object(archive_sets.shutil, 'disk_usage', return_value=type('Space', (), {'free': 0})()):
            with self.assertRaises(EvolveError) as error:
                self.collect()
        self.assertEqual(error.exception.code, 'ARCHIVE_SPACE')
        self.assertFalse(self.destination.exists())

    def test_missing_current_version_is_not_silently_omitted_from_authority(self):
        self.store.connection.execute("UPDATE artifacts SET current_version='missing-version' WHERE path='terms.md'")
        with self.assertRaises(EvolveError) as error:
            self.collect()
        self.assertEqual(error.exception.code, 'ARCHIVE_DATABASE')
        self.assertFalse(self.destination.exists())

    def test_two_observations_can_share_one_exact_protected_payload(self):
        text = '# Other\n\nSeparate registered baseline.\n'
        auth = {**self.auth, 'paths': ['other.md']}
        item = propose_baseline(self.root, {**self.identity, 'authorization': auth, 'input': {
            'path': 'other.md', 'expected_digest': None, 'content': text,
            'presentation': {'source': 'controlled-exact-additional-fixture', 'text': text}}})
        apply_baseline(self.root, {**self.identity, 'authorization': auth, 'input': {
            'proposal_id': item['proposal_id'], 'approval': {'proposal_version': item['proposal_version'],
                'candidate_digest': item['candidate_digest'], 'expected_digest': None,
                'source': 'uniform-user-authorization-specific-additional-fixture',
                'text': 'Apply exactly this temporary Other baseline.'}}})
        # The opened observer adopts the actual committed checkpoint, without writing it.
        self.store.close()
        self.store = Store(self.root)
        self.addCleanup(self.store.close)
        external = 'Same external unapproved observation.\n'
        (self.root / 'terms.md').write_text(external)
        (self.root / 'other.md').write_text(external)
        result = self.collect()
        manifest = validate_archive(self.destination, result['manifest_digest'])
        self.assertEqual(len(manifest['observations']), 2)
        self.assertEqual(len({r['protected_copy'] for r in manifest['observations']}), 1)
        self.assertEqual((self.destination / manifest['observations'][0]['protected_copy']).read_text(), external)

    def test_selected_manifest_and_payload_damage_are_both_rejected(self):
        result = self.collect()
        with self.assertRaises(EvolveError) as error:
            validate_archive(self.destination, 'a-different-unreviewed-manifest')
        self.assertEqual(error.exception.code, 'ARCHIVE_INVALID')
        (self.destination / 'authority/terms.md').write_text('tampered')
        with self.assertRaises(EvolveError) as error:
            validate_archive(self.destination, result['manifest_digest'])
        self.assertEqual(error.exception.code, 'ARCHIVE_INVALID')

    def test_paths_and_links_are_rejected_even_with_a_recomputed_manifest_digest(self):
        result = self.collect()
        manifest = json.loads((self.destination / 'manifest.json').read_text())
        original = canonical(manifest)
        row = next(r for r in manifest['files'] if r['path'] == 'terms.md')
        row.update(path='../outside.md', payload='authority/../outside.md')
        changed = canonical(manifest)
        (self.destination / 'manifest.json').write_bytes(changed)
        with self.assertRaises(EvolveError) as error:
            validate_archive(self.destination, digest(changed))
        self.assertIn(error.exception.code, ('PATH', 'ARCHIVE_PATH'))
        self.assertFalse((self.root / 'outside.md').exists())
        (self.destination / 'manifest.json').write_bytes(original)
        path = self.destination / 'authority/terms.md'
        path.unlink()
        path.symlink_to(self.root / 'terms.md')
        with self.assertRaises(EvolveError) as error:
            validate_archive(self.destination, result['manifest_digest'])
        self.assertIn(error.exception.code, ('PATH', 'ARCHIVE_PATH'))
