"""Observable installed-package behavior; never touches personal host settings."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def tree(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


class InstalledPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix='evolve-tests-')
        cls.base = Path(cls.workspace.name)
        cls.distribution = cls.base / 'distribution'
        subprocess.run([sys.executable, str(ROOT / 'scripts/build_package.py'),
                        '--out', str(cls.distribution)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.base)
        self.addCleanup(self.temp.cleanup)
        self.lab = Path(self.temp.name).resolve()
        self.package = self.lab / '缓存 space 中文'
        shutil.copytree(self.distribution, self.package)
        self.project = self.lab / 'project'
        self.project.mkdir()
        (self.project / 'user.txt').write_text('保留用户内容')

    def run_cli(self, *args, expected=0):
        before = tree(self.project)
        process = subprocess.run([sys.executable, str(self.package / 'runtime/evolve.py'),
                                  '--project', str(self.project), *args],
                                 cwd=self.lab, text=True, capture_output=True)
        self.assertEqual(process.returncode, expected, process.stderr + process.stdout)
        self.assertEqual(tree(self.project), before, 'Read-only command changed project files')
        self.assertNotIn('Traceback', process.stderr)
        return json.loads(process.stdout)

    def connect_fixture(self, *, schema=None, identity='fixture-id'):
        if schema is None:
            schema = json.loads((self.package / 'evolve-package.json').read_text())['schema_version']
        folder = self.project / 'evolve'
        folder.mkdir()
        (folder / 'config.toml').write_text('config_version=1\n[project]\nid="fixture-id"\n'
                                          '[history]\nbackend="sqlite"\ndatabase="evolve/history.db"\n')
        db = sqlite3.connect(folder / 'history.db')
        db.execute('CREATE TABLE project_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.executemany('INSERT INTO project_meta VALUES (?, ?)',
                       [('schema_version', str(schema)), ('project_id', identity)])
        db.commit()
        db.close()
        return folder

    def test_default_status_is_read_only_and_unconnected(self):
        result = self.run_cli()
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['project']['state'], 'not_connected')
        self.assertFalse((self.project / 'evolve').exists())
        self.assertEqual(result['data']['host_enablement'], 'not_observed')
        history = self.run_cli('history')['data']['history']
        self.assertEqual(history['project']['state'], 'not_connected')
        self.assertEqual(history['runs'], [])
        self.assertFalse((self.project / 'evolve').exists())

    def test_moved_complete_package_works_without_download_source(self):
        result = self.run_cli('maintain', '--method', 'doctor')
        self.assertEqual(result['data']['action_owners']['sync'], 'evolve-archive')
        self.assertEqual(result['data']['action_owners']['update'], 'evolve-propose')
        self.assertEqual(result['data']['action_owners']['analyze'], 'evolve-propose')
        self.assertEqual(Path(result['data']['package_root']), self.package)
        observation = result['data']['package_observation']
        self.assertEqual(Path(observation['executing_root']), self.package)
        self.assertEqual(observation['source']['source_root'], str(ROOT))
        self.assertEqual(observation['source']['source_attestation'], 'unsigned')
        self.assertEqual(result['data']['available_methods'], [
            'analyze.investigate', 'apply.external.compensate', 'apply.external.execute', 'apply.external.reconcile', 'apply.external.record', 'apply.implement', 'archive.close', 'history.show', 'init.baseline.apply', 'init.baseline.propose',
            'init.complete', 'init.connect', 'init.survey', 'init.templates', 'learn.disable', 'learn.promote', 'learn.record', 'learn.retro', 'learn.review', 'learn.search', 'maintain.backup', 'maintain.cancel', 'maintain.clean', 'maintain.doctor', 'maintain.export', 'maintain.materials', 'maintain.recover', 'maintain.repair', 'maintain.restore', 'maintain.upgrade', 'next.show', 'propose.create', 'resume.show', 'status.show', 'sync.apply', 'sync.assess', 'sync.check', 'sync.facts', 'sync.propose', 'sync.review', 'update.revise', 'verify.knowledge', 'verify.run'])

    def test_build_source_observation_tampering_is_rejected(self):
        path = self.package / 'evolve-package.json'
        manifest = json.loads(path.read_text())
        manifest['source_observation']['git_revision'] = 'changed-source-claim'
        path.write_text(json.dumps(manifest))
        response = self.run_cli('maintain', '--method', 'doctor', expected=2)
        self.assertEqual(response['error']['code'], 'PACKAGE_INCOMPLETE')

    def test_unknown_action_and_method_never_fall_back(self):
        for args, code in [(('release',), 'UNKNOWN_ACTION'),
                           (('maintain', '--method', 'execute'), 'UNKNOWN_METHOD')]:
            with self.subTest(args=args):
                result = self.run_cli(*args, expected=2)
                self.assertEqual(result['error']['code'], code)

    def test_direct_skill_owner_cannot_bypass_routing(self):
        for action in ['status', 'learn']:
            result = self.run_cli(action, '--owner', 'evolve-apply', expected=2)
            self.assertEqual(result['error']['code'], 'OWNER')

    def test_unimplemented_methods_are_explicitly_unavailable(self):
        for action, method in [('verify', 'record')]:
            with self.subTest(action=action):
                result = self.run_cli(action, '--method', method, expected=2)
                self.assertEqual(result['error']['code'], 'UNAVAILABLE')
                self.assertFalse(result['data']['committed'])

    def test_implemented_writes_require_explicit_request_and_do_not_initialize_implicitly(self):
        for action in ['init', 'propose', 'apply', 'verify', 'archive', 'analyze', 'sync']:
            with self.subTest(action=action):
                result = self.run_cli(action, expected=2)
                self.assertEqual(result['error']['code'], 'REQUEST_REQUIRED')

    def test_builder_rejects_syntax_errors_before_creating_a_distribution(self):
        scripts = self.package / 'scripts'
        scripts.mkdir()
        shutil.copyfile(ROOT / 'scripts/build_package.py', scripts / 'build_package.py')
        (self.package / 'runtime/evolve_core/learning.py').write_text('def broken(:\n')
        target = self.lab / 'invalid-distribution'
        result = subprocess.run([sys.executable, '-B', str(scripts / 'build_package.py'), '--out', str(target)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('Invalid Python resource runtime/evolve_core/learning.py', result.stderr)
        self.assertFalse(target.exists())

    def test_missing_shared_resource_is_diagnosed(self):
        (self.package / 'shared/contract.md').unlink()
        self.assertEqual(self.run_cli('status', expected=2)['error']['code'], 'PACKAGE_INCOMPLETE')

    def test_missing_runtime_is_diagnosed_without_traceback(self):
        (self.package / 'runtime/evolve_core/cli.py').unlink()
        self.assertEqual(self.run_cli('status', expected=2)['error']['code'], 'PACKAGE_INCOMPLETE')

    def test_mixed_host_manifest_is_rejected(self):
        path = self.package / '.codex-plugin/plugin.json'
        data = json.loads(path.read_text())
        data['version'] = '99.0.0'
        path.write_text(json.dumps(data))
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'PACKAGE_INCOMPLETE')

    def test_changed_package_schema_is_rejected(self):
        path = self.package / 'evolve-package.json'
        data = json.loads(path.read_text())
        data['schema_version'] = 999
        path.write_text(json.dumps(data))
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'PACKAGE_VERSION')

    def test_inventory_cannot_reference_outside_package(self):
        path = self.package / 'evolve-package.json'
        data = json.loads(path.read_text())
        data['files']['../user.txt'] = 'bad'
        path.write_text(json.dumps(data))
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'PACKAGE_PATH')

    def test_unrelated_same_name_directory_is_not_adopted(self):
        (self.project / 'evolve').mkdir()
        (self.project / 'evolve/user.md').write_text('用户资料')
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'PROJECT_COLLISION')

    def test_missing_configuration_does_not_recreate_existing_database(self):
        folder = self.connect_fixture()
        (folder / 'config.toml').unlink()
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'PROJECT_INCOMPLETE')

    def test_newer_schema_is_not_migrated(self):
        self.connect_fixture(schema=999)
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'SCHEMA_VERSION')

    def test_different_project_identity_is_not_overwritten(self):
        self.connect_fixture(identity='other-project')
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'PROJECT_IDENTITY')

    def test_connected_query_does_not_modify_history(self):
        self.connect_fixture()
        self.assertEqual(self.run_cli()['data']['project']['project_id'], 'fixture-id')

    def test_wal_query_reads_committed_state_without_touching_shared_memory(self):
        folder = self.connect_fixture()
        db = sqlite3.connect(folder / 'history.db')
        self.addCleanup(db.close)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute("UPDATE project_meta SET value='999' WHERE key='schema_version'")
        db.commit()
        self.assertTrue((folder / 'history.db-wal').exists())
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'SCHEMA_VERSION')

    def test_project_storage_symlink_escape_is_rejected(self):
        outside = self.lab / 'outside'
        outside.mkdir()
        (self.project / 'evolve').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.run_cli(expected=2)['error']['code'], 'PROJECT_PATH')

    def test_standalone_and_plugin_channels_are_diagnosed_without_deletion(self):
        standalone = self.project / '.agents/skills/evolve-workflow/SKILL.md'
        standalone.parent.mkdir(parents=True)
        standalone.write_text('Existing independently installed skill')
        result = self.run_cli(expected=3)
        self.assertEqual(result['error']['code'], 'DUPLICATE_INSTALLATION')
        self.assertIn(str(standalone), result['error']['message'])

    def test_distribution_has_closed_local_links_and_no_project_data(self):
        for path in self.package.rglob('*.md'):
            for link in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', path.read_text()):
                if '://' not in link and not link.startswith('#'):
                    target = (path.parent / link.split('#', 1)[0]).resolve()
                    self.assertTrue(target.is_relative_to(self.package), (path, link))
                    self.assertTrue(target.exists(), (path, link))
        self.assertFalse(list(self.package.rglob('history.db')))
        self.assertFalse((self.package / 'tests').exists())
        self.assertFalse((self.package / 'docs/archive').exists())

    def test_build_refuses_existing_output_without_destroying_it(self):
        before = tree(self.package)
        process = subprocess.run([sys.executable, str(ROOT / 'scripts/build_package.py'),
                                  '--out', str(self.package)], capture_output=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(tree(self.package), before)


if __name__ == '__main__':
    unittest.main()
