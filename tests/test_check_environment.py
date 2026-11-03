"""Environment observations are read-only; declared preflight checks precede writes."""
import json
import os
import sys
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.check_environment import observe
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.package import digest
from evolve_core.plans import propose


class CheckEnvironmentTests(WorkflowFixture):
    def configure(self, check):
        data = {'checks': [check]}
        candidate = connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': data})
        connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': {**data,
            'expected_config_digest': candidate['expected_config_digest'],
            'presentation': {'source': 'actual-environment-config-candidate', 'text': candidate['candidate']}}})
        plan = 'Repair totals after checking the declared execution environment.'
        self.plan = propose(self.root, {**self.identity(), 'authorization': self.auth, 'input': {
            'title': 'Environment-protected total', 'plan': plan, 'completion': 'Original totals pass.',
            'scope': ['total.py'], 'required_checks': [check['id'], 'unit'], 'acceptance': ['Original totals pass.'],
            'presentation': {'source': 'environment-fixture-plan', 'text': plan}}})

    def test_missing_interpreter_blocks_before_business_writes(self):
        self.configure({'id': 'environment', 'argv': ['.venv-missing/bin/python', '-V'], 'preflight': True})
        before = (self.root / 'total.py').read_bytes()
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, self.apply_request())
        self.assertEqual(caught.exception.code, 'CHECK_ENVIRONMENT')
        self.assertEqual(caught.exception.details['execution']['business_files'], 'not_dispatched')
        self.assertEqual((self.root / 'total.py').read_bytes(), before)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='check_dispatch_prepared'")[0]['n'], 0)

    def test_actual_missing_python_dependency_is_retained_as_preflight_failure(self):
        self.configure({'id': 'environment', 'argv': [sys.executable, '-c', 'import evolve_missing_dependency_fixture'], 'preflight': True})
        before = (self.root / 'total.py').read_bytes()
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, self.apply_request())
        error = caught.exception
        self.assertEqual(error.code, 'CHECK_ENVIRONMENT')
        self.assertEqual(error.details['result']['returncode'], 1)
        self.assertIn('ModuleNotFoundError', error.details['result']['output'])
        self.assertEqual((self.root / 'total.py').read_bytes(), before)
        self.assertTrue(self.rows("SELECT * FROM events WHERE kind='environment_preflight'"))

    def test_successful_preflight_runs_before_files_and_observes_actual_python(self):
        self.configure({'id': 'environment', 'argv': [sys.executable, '-c', 'import sys; print(sys.version)'], 'preflight': True})
        result = implement(self.root, self.apply_request())
        self.assertEqual(result['outcome'], 'implemented')
        events = self.rows('SELECT kind,payload_json FROM events WHERE run_id=? ORDER BY rowid', (result['run_id'],))
        kinds = [item['kind'] for item in events]
        self.assertLess(kinds.index('environment_preflight'), kinds.index('files_applied'))
        row = self.rows('SELECT b.content FROM blobs b JOIN evidence e ON e.content_digest=b.digest WHERE e.source_run_id=? ORDER BY e.rowid',
                        (result['run_id'],))[0]
        actual = json.loads(row['content'])
        self.assertEqual(actual['environment']['tools'][0]['version'], sys.version.split()[0])

    def test_observation_hashes_only_declared_noncredential_values_without_commands(self):
        check = {**self.checks[0], 'environment_variables': ['FINANCE_PYTHON']}
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.dict(os.environ, {'FINANCE_PYTHON': '.venv/bin/python', 'EXAMPLE_API_KEY': 'private-fixture-credential'}):
            observed = observe(self.root, check)
        encoded = json.dumps(observed)
        self.assertNotIn('private-fixture-credential', encoded)
        self.assertNotIn('.venv/bin/python', encoded)
        self.assertEqual(observed['variables']['FINANCE_PYTHON']['digest'], digest(b'.venv/bin/python'))
        self.assertEqual(observed['version_probes'], 'not_executed')
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_environment_value_change_invalidates_fingerprint(self):
        from evolve_core.work import fingerprint
        self.configure({'id': 'environment', 'argv': [sys.executable, '-V'], 'environment_variables': ['FINANCE_PYTHON']})
        definition = json.loads(self.rows('SELECT definition_json FROM tasks WHERE id=?', (self.plan['task_id'],))[0]['definition_json'])
        definition['structured'] = True
        with patch.dict(os.environ, {'FINANCE_PYTHON': 'first'}):
            first = fingerprint(self.root, definition)
        with patch.dict(os.environ, {'FINANCE_PYTHON': 'second'}):
            second = fingerprint(self.root, definition)
        self.assertNotEqual(first['digest'], second['digest'])
        self.assertNotEqual(first['task_basis_digest'], second['task_basis_digest'])
