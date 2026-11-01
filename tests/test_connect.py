"""Connection preserves user content and recovers actual installation cut points."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.workspace import durable_write
from evolve_core.reading import current_state


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-connect-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'README.md').write_text('既有业务资料')
        self.request = {'request_id': 'connect-request', 'input': {},
                        'authorization': {'source': 'isolated-test-fixture',
                                          'text': 'Connect this temporary test project',
                                          'effect_kinds': ['project_records']}}

    def test_connection_only_creates_records_not_formal_knowledge_or_business_files(self):
        result = connect(self.root, self.request)
        self.assertEqual(result['outcome'], 'connected')
        self.assertEqual((self.root / 'README.md').read_text(), '既有业务资料')
        self.assertFalse((self.root / 'evolve/project.md').exists())
        self.assertEqual(result['formal_baseline'], 'not_proposed')
        self.assertTrue((self.root / 'evolve/history.db').is_file())

    def test_retry_preserves_identity_and_has_one_run(self):
        original = connect(self.root, self.request)
        self.assertEqual(connect(self.root, self.request), original)
        db = sqlite3.connect(self.root / 'evolve/history.db')
        try:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM phase_runs').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM changes').fetchone()[0], 0)
        finally:
            db.close()

    def test_initial_connection_preserves_its_project_local_request_staging(self):
        staged = self.root / '.evolve-local/control/requests/initial-unique.json'
        staged.parent.mkdir(parents=True)
        original = json.dumps(self.request).encode()
        staged.write_bytes(original)
        self.assertEqual(current_state(self.root)['state'], 'not_connected')
        self.assertEqual(connect(self.root, self.request)['outcome'], 'connected')
        self.assertEqual(staged.read_bytes(), original)

    def test_request_staging_does_not_adopt_other_unknown_control_files(self):
        staged = self.root / '.evolve-local/control/requests/initial-unique.json'
        staged.parent.mkdir(parents=True)
        staged.write_text(json.dumps(self.request))
        foreign = staged.parent.parent / 'unknown-control.json'
        foreign.write_text('preserve this unrelated control file')
        with self.assertRaises(EvolveError) as caught:
            connect(self.root, self.request)
        self.assertEqual(caught.exception.code, 'PROJECT_COLLISION')
        self.assertEqual(foreign.read_text(), 'preserve this unrelated control file')
        self.assertFalse((self.root / 'evolve/history.db').exists())

    def test_same_request_identity_cannot_change_candidate(self):
        connect(self.root, self.request)
        with self.assertRaises(EvolveError) as caught:
            connect(self.root, {**self.request, 'input': {'name': 'changed name'}})
        self.assertEqual(caught.exception.code, 'REQUEST_CONFLICT')

    def test_unknown_existing_directory_is_preserved(self):
        (self.root / 'evolve').mkdir()
        (self.root / 'evolve/user.txt').write_text('保留')
        with self.assertRaises(EvolveError):
            connect(self.root, self.request)
        self.assertEqual((self.root / 'evolve/user.txt').read_text(), '保留')
        self.assertFalse((self.root / '.evolve-local').exists())

    def test_missing_authorization_is_rejected_before_any_record_directory(self):
        with self.assertRaises(EvolveError):
            connect(self.root, {'input': {}})
        self.assertFalse((self.root / '.evolve-local').exists())

    def test_configuration_quotes_names_and_does_not_execute_checks(self):
        sentinel = self.root / 'must-not-run'
        request = {**self.request, 'input': {'name': '中文 "名称"\n[another]', 'checks': [
            {'id': 'check', 'argv': [sys.executable, '-c', f'open({str(sentinel)!r},"w").close()']}]}}
        connect(self.root, request)
        config = tomllib.loads((self.root / 'evolve/config.toml').read_text())
        self.assertEqual(config['project']['name'], request['input']['name'])
        self.assertFalse(sentinel.exists())

    def test_shell_string_check_is_rejected_before_connection(self):
        request = {**self.request, 'input': {'checks': [{'id': 'check', 'argv': 'echo unsafe'}]}}
        with self.assertRaises(EvolveError):
            connect(self.root, request)
        self.assertFalse((self.root / '.evolve-local').exists())

    def test_foreign_drive_check_directory_is_not_accepted_on_posix(self):
        request = {**self.request, 'input': {'checks': [
            {'id': 'check', 'argv': ['python3', '-V'], 'cwd': 'C:/other-project'}]}}
        with self.assertRaises(EvolveError):
            connect(self.root, request)
        self.assertFalse((self.root / '.evolve-local').exists())

    def test_init_journal_exists_before_project_database_installation(self):
        installed = []

        def observed_write(path, content, **kwargs):
            if str(path).endswith('evolve/history.db'):
                journal = json.loads((self.root / '.evolve-local/control/init.json').read_text())
                self.assertEqual(journal['state'], 'prepared')
                installed.append(path)
            return durable_write(path, content, **kwargs)

        with patch('evolve_core.connect.durable_write', side_effect=observed_write):
            connect(self.root, self.request)
        self.assertEqual(len(installed), 1)

    def test_interruption_after_configuration_preserves_identity_on_recovery(self):
        def interrupted_write(path, content, **kwargs):
            if str(path).endswith('evolve/history.db'):
                raise OSError('injected database installation interruption')
            return durable_write(path, content, **kwargs)

        with patch('evolve_core.connect.durable_write', side_effect=interrupted_write):
            with self.assertRaises(OSError):
                connect(self.root, self.request)
        journal = json.loads((self.root / '.evolve-local/control/init.json').read_text())
        self.assertTrue((self.root / 'evolve/config.toml').exists())
        self.assertFalse((self.root / 'evolve/history.db').exists())
        result = connect(self.root, self.request, recover=True)
        self.assertEqual(result['project_id'], journal['project_id'])
        self.assertEqual(result['run_id'], journal['run_id'])

    def test_interrupted_connection_does_not_replace_third_party_configuration(self):
        def interrupted_write(path, content, **kwargs):
            if str(path).endswith('evolve/history.db'):
                raise OSError('injected interruption')
            return durable_write(path, content, **kwargs)

        with patch('evolve_core.connect.durable_write', side_effect=interrupted_write):
            with self.assertRaises(OSError):
                connect(self.root, self.request)
        config = self.root / 'evolve/config.toml'
        config.write_text('user edit')
        with self.assertRaises(EvolveError) as caught:
            connect(self.root, self.request, recover=True)
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        self.assertEqual(config.read_text(), 'user edit')


if __name__ == '__main__':
    unittest.main()
