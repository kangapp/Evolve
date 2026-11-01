"""File-operation recovery invariants, with real subprocess interruption."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.errors import EvolveError
from evolve_core.package import digest
from evolve_core.workspace import (inside, current_digest, writer_lock, prepare_files,
                                    install_files, finish_journal)


class FileCommitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-file-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def candidate(self, path='feature.txt', old=None, new='new result'):
        return {'path': path, 'expected_digest': digest(old.encode()) if old is not None else None,
                'content': new}

    def test_new_file_and_recovery_only_finalize_the_same_content(self):
        journal = prepare_files(self.root, 'test-op', [self.candidate()])
        install_files(self.root, journal)
        stamp = (self.root / 'feature.txt').stat().st_mtime_ns
        install_files(self.root, journal)
        self.assertEqual((self.root / 'feature.txt').stat().st_mtime_ns, stamp)
        finish_journal(self.root, journal)
        stored = json.loads((self.root / '.evolve-local/control/operations/test-op.json').read_text())
        self.assertEqual(stored['state'], 'committed')

    def test_existing_file_original_is_preserved_in_prepared_journal(self):
        (self.root / 'feature.txt').write_text('original')
        journal = prepare_files(self.root, 'test-op', [self.candidate(old='original')])
        self.assertIsNotNone(journal['files'][0]['original_b64'])
        self.assertEqual((self.root / 'feature.txt').read_text(), 'original')
        install_files(self.root, journal)
        self.assertEqual((self.root / 'feature.txt').read_text(), 'new result')

    def test_third_party_edit_after_prepare_is_not_overwritten(self):
        journal = prepare_files(self.root, 'test-op', [self.candidate()])
        (self.root / 'feature.txt').write_text('external edit')
        with self.assertRaises(EvolveError) as caught:
            install_files(self.root, journal)
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        self.assertEqual((self.root / 'feature.txt').read_text(), 'external edit')

    def test_partial_multi_file_commit_can_resume_without_rewriting_finished_file(self):
        journal = prepare_files(self.root, 'test-op', [self.candidate('a.txt'), self.candidate('b.txt')])
        (self.root / 'a.txt').write_text('new result')
        install_files(self.root, journal)
        self.assertEqual((self.root / 'a.txt').read_text(), 'new result')
        self.assertEqual((self.root / 'b.txt').read_text(), 'new result')

    def test_old_precondition_does_not_replace_current_file(self):
        (self.root / 'feature.txt').write_text('external edit')
        with self.assertRaises(EvolveError) as caught:
            prepare_files(self.root, 'test-op', [self.candidate(old='original')])
        self.assertEqual(caught.exception.code, 'FILE_CONFLICT')

    def test_replacement_preserves_existing_executable_mode(self):
        path = self.root / 'run.sh'
        path.write_text('original')
        path.chmod(0o755)
        journal = prepare_files(self.root, 'test-op', [self.candidate('run.sh', old='original')])
        install_files(self.root, journal)
        self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_internal_operation_identity_cannot_choose_another_journal_path(self):
        with self.assertRaises(EvolveError) as caught:
            prepare_files(self.root, '../unexpected', [self.candidate()])
        self.assertEqual(caught.exception.code, 'OPERATION_ID')

    def test_posix_and_windows_escaping_paths_are_rejected(self):
        for name in ['../outside', '/outside', 'C:/outside', 'C:relative', '..\\outside']:
            with self.subTest(name=name), self.assertRaises(EvolveError):
                inside(self.root, name)

    def test_symlink_escaping_project_is_rejected(self):
        (self.root / 'escape').symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(EvolveError):
            inside(self.root, 'escape/outside')

    def test_live_lock_is_not_reclaimed_by_recovery(self):
        with writer_lock(self.root):
            with self.assertRaises(EvolveError) as caught:
                with writer_lock(self.root, recover_dead=True):
                    self.fail('A live writer was replaced')
            self.assertEqual(caught.exception.code, 'WRITER_ACTIVE')

    def test_dead_process_lock_requires_explicit_recovery(self):
        code = ('import os,sys;sys.path.insert(0,sys.argv[1]);'
                'from pathlib import Path;from evolve_core.workspace import writer_lock;'
                'lock=writer_lock(Path(sys.argv[2]));lock.__enter__();os._exit(17)')
        process = subprocess.run([sys.executable, '-c', code, str(Path(__file__).resolve().parents[1] / 'runtime'),
                                  str(self.root)], capture_output=True)
        self.assertEqual(process.returncode, 17)
        with self.assertRaises(EvolveError):
            with writer_lock(self.root):
                self.fail('Implicitly reclaimed a dead writer')
        with writer_lock(self.root, recover_dead=True):
            self.assertTrue((self.root / '.evolve-local/control/writer.lock').exists())
        self.assertFalse((self.root / '.evolve-local/control/writer.lock').exists())


if __name__ == '__main__':
    unittest.main()
