"""Incremental init preserves user TOML and does not reset task definitions."""
import json
import sys
import tomllib
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.recover import recover


class ConfigurationTests(WorkflowFixture):
    def changes(self):
        return {'checks': [{'id': 'additional', 'argv': [sys.executable, '-c', 'raise SystemExit(0)'], 'timeout': 12}]}

    def prepare(self, data=None):
        request = self.request(data or self.changes())
        return request, connect(self.root, request)

    def apply_candidate(self, original_request, candidate):
        request = self.request({**original_request['input'], 'expected_config_digest': candidate['expected_config_digest'],
                                'presentation': {'source': 'fixture-presented-config-diff', 'text': candidate['candidate']}})
        return request

    def test_repeated_connection_inspects_existing_identity_without_recreating_it(self):
        result = connect(self.root, self.request({}))
        self.assertEqual(result['outcome'], 'already_connected')
        self.assertEqual(result['project_id'], self.project['project_id'])
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM changes')[0]['n'], 1)

    def test_new_check_is_presented_before_application_and_retains_unknown_bytes(self):
        path = self.root / 'evolve/config.toml'
        extra = '\n# User-owned commentary\n[user_extension]\nvalue = "preserve this exact line"\n'
        path.write_text(path.read_text() + extra)
        before = path.read_bytes()
        change_before = self.rows('SELECT * FROM changes')[0]
        task_before = self.rows('SELECT * FROM tasks')[0]
        request, candidate = self.prepare()
        self.assertEqual(candidate['outcome'], 'config_candidate')
        self.assertEqual(path.read_bytes(), before)
        applied = connect(self.root, self.apply_candidate(request, candidate))
        self.assertEqual(applied['outcome'], 'configuration_updated')
        self.assertFalse(applied['checks_run'])
        self.assertIn(extra, path.read_text())
        parsed = tomllib.loads(path.read_text())
        self.assertEqual({c['id'] for c in parsed['verification']['checks']}, {'unit', 'additional'})
        self.assertEqual(self.rows('SELECT * FROM changes')[0], change_before)
        self.assertEqual(self.rows('SELECT * FROM tasks')[0], task_before)

    def test_existing_check_value_changes_keep_its_comment_and_other_check(self):
        path = self.root / 'evolve/config.toml'
        path.write_text(path.read_text().replace('timeout = 10', 'timeout = 10 # local explanation'))
        request, candidate = self.prepare({'checks': [{**self.checks[0], 'timeout': 11}]})
        connect(self.root, self.apply_candidate(request, candidate))
        self.assertIn('timeout = 11 # local explanation', path.read_text())

    def test_unsupported_literal_value_is_preserved_instead_of_template_rewrite(self):
        path = self.root / 'evolve/config.toml'
        current = path.read_text()
        lines = current.splitlines(keepends=True)
        lines = ["argv = ['python3', '-V']\n" if line.startswith('argv =') else line for line in lines]
        path.write_text(''.join(lines))
        before = path.read_bytes()
        with self.assertRaises(EvolveError) as caught:
            self.prepare({'checks': [{**self.checks[0], 'argv': [sys.executable, '-V']}]})
        self.assertEqual(caught.exception.code, 'CONFIG_UNSUPPORTED')
        self.assertEqual(path.read_bytes(), before)

    def test_external_change_makes_prior_config_candidate_unusable(self):
        request, candidate = self.prepare()
        path = self.root / 'evolve/config.toml'
        path.write_text(path.read_text() + '\n# external observation after presentation\n')
        with self.assertRaises(EvolveError) as caught:
            connect(self.root, self.apply_candidate(request, candidate))
        self.assertEqual(caught.exception.code, 'CONFIG_PRESENTATION')
        self.assertNotIn('additional', path.read_text())

    def test_interrupted_configuration_recovers_bytes_without_running_checks(self):
        marker = self.root / 'unexpected-check-execution'
        request, candidate = self.prepare({'checks': [{'id': 'must-not-run',
            'argv': [sys.executable, '-c', f'open({str(marker)!r},"w").close()']}]})
        with patch('evolve_core.configure.install_files', side_effect=OSError('injected configuration interruption')):
            with self.assertRaises(EvolveError):
                connect(self.root, self.apply_candidate(request, candidate))
        operation = self.rows("SELECT * FROM operations WHERE effect_kind='config'")[0]
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertIn('must-not-run', (self.root / 'evolve/config.toml').read_text())
        self.assertFalse(marker.exists())

    def test_configuration_application_replay_does_not_repeat_versions(self):
        request, candidate = self.prepare()
        accepted = self.apply_candidate(request, candidate)
        first = connect(self.root, accepted)
        count = self.rows("SELECT COUNT(*) n FROM artifact_versions v JOIN artifacts a ON a.id=v.artifact_id WHERE a.kind='config'")[0]['n']
        self.assertEqual(connect(self.root, accepted), first)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM artifact_versions v JOIN artifacts a ON a.id=v.artifact_id WHERE a.kind='config'")[0]['n'], count)
