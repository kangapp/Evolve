"""A real, intentionally broken arithmetic project for workflow acceptance."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.connect import connect
from evolve_core.plans import propose
from evolve_core.package import digest
from evolve_core.work import fingerprint


class WorkflowFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-workflow-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'total.py').write_text('def total(values):\n    return len(values)\n')
        (self.root / 'test_total.py').write_text(
            'import unittest\nfrom total import total\n'
            'class Totals(unittest.TestCase):\n'
            '    def test_values(self):\n'
            '        self.assertEqual(total([2,3]),5)\n'
            '        self.assertEqual(total([]),0)\n'
            '        self.assertEqual(total([-2,3]),1)\n')
        self.auth = {'source': 'isolated-test-fixture', 'text': 'Repair the arithmetic example and run its tests',
                     'effect_kinds': ['project_records', 'business_files', 'checks'],
                     'paths': ['total.py', 'test_total.py']}
        self.checks = [{'id': 'unit', 'argv': [sys.executable, '-B', '-m', 'unittest', 'discover', '-v'],
                        'cwd': '.', 'timeout': 10}]
        self.project = connect(self.root, {'request_id': 'connect', 'authorization': self.auth,
                                          'input': {'checks': self.checks}})
        self.plan = propose(self.root, {**self.identity(), 'request_id': 'plan', 'authorization': self.auth,
            'input': {'title': 'Correct arithmetic total', 'plan': 'Return the sum of values, including empty and negative cases.',
                      'completion': 'Arithmetic examples pass without changing their expected results.',
                      'scope': ['total.py', 'test_total.py'], 'required_checks': ['unit'],
                      'acceptance': ['[2, 3] totals 5', 'Empty input totals zero', 'Negative values retain their sign'],
                      'presentation': {'source': 'fixture-assistant-message',
                                       'text': 'Return the sum of values, including empty and negative cases.'}}})

    def identity(self):
        return {'project_id': self.project['project_id'],
                'expected_workspace_epoch': self.project['workspace_epoch']}

    def rows(self, sql, values=()):
        connection = sqlite3.connect(self.root / 'evolve/history.db')
        connection.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in connection.execute(sql, values)]
        finally:
            connection.close()

    def request(self, extra=None):
        change = self.rows('SELECT * FROM changes WHERE id=?', (self.plan['change_id'],))[0]
        task = self.rows('SELECT * FROM tasks WHERE id=?', (self.plan['task_id'],))[0]
        return {**self.identity(), 'request_id': str(uuid.uuid4()), 'authorization': self.auth,
                'expected_versions': {'change': change['row_version'], 'task': task['row_version']},
                'input': {'change_id': change['id'], 'revision_id': change['current_revision'],
                          'definition_digest': task['definition_digest'], **(extra or {})}}

    def apply_request(self, text='def total(values):\n    return sum(values)\n'):
        return self.request({'accepted_plan_digest': self.plan['plan_digest'], 'files': [
            {'path': 'total.py', 'expected_digest': digest((self.root / 'total.py').read_bytes()), 'content': text}]})

    def current_fingerprint(self):
        definition = json.loads(self.rows('SELECT definition_json FROM tasks WHERE id=?',
                                          (self.plan['task_id'],))[0]['definition_json'])
        return fingerprint(self.root, definition)

    def verification_request(self):
        snapshot = self.current_fingerprint()
        reviews = [{'axis': axis, 'observer': 'isolated-fixture-observer',
                    'summary': 'Inspected the arithmetic function and the independent examples in test_total.py',
                    'fingerprint_digest': snapshot['digest'], 'findings': []}
                   for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': ac['id'], 'status': 'passed',
                                             'basis': 'Independent literal expectations in test_total.py:test_values'}
                                            for ac in self.plan['acceptance']]
        return self.request({'reviews': reviews})
