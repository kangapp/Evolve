"""A short plan remains candidate material, preserves sources, and never edits business files."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.plans import propose


class ShortPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-plan-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'total.py').write_text('def total(values): return len(values)\n')
        auth = {'source': 'isolated-test-fixture', 'text': 'Prepare a repair plan, do not implement yet',
                'effect_kinds': ['project_records']}
        project = connect(self.root, {'request_id': 'connect', 'input': {}, 'authorization': auth})
        self.request = {'request_id': 'plan', 'project_id': project['project_id'],
                        'expected_workspace_epoch': project['workspace_epoch'], 'authorization': auth,
                        'input': {'title': 'Correct total', 'plan': 'Sum values instead of counting them.',
                                  'completion': 'Behavior matches supplied arithmetic examples.',
                                  'scope': ['total.py'], 'acceptance': ['total([2, 3]) returns 5'],
                                  'required_checks': [], 'presentation': {
                                      'text': 'Sum values instead of counting them.', 'source': 'fixture-assistant-message'}}}

    def inspect(self, sql):
        db = sqlite3.connect(self.root / 'evolve/history.db')
        try:
            return db.execute(sql).fetchall()
        finally:
            db.close()

    def test_presented_plan_is_saved_without_implicit_acceptance_or_business_change(self):
        original = (self.root / 'total.py').read_bytes()
        result = propose(self.root, self.request)
        self.assertFalse(result['accepted'])
        self.assertEqual((self.root / 'total.py').read_bytes(), original)
        self.assertEqual(self.inspect('SELECT state FROM tasks')[0][0], 'todo')
        self.assertIsNone(self.inspect('SELECT accepted_event_id FROM plan_revisions')[0][0])
        saved = self.inspect('SELECT b.content FROM blobs b JOIN plan_revisions r ON r.plan_digest=b.digest')[0][0]
        self.assertEqual(saved.decode(), self.request['input']['plan'])

    def test_repeated_request_allocates_one_change_one_task_and_one_acceptance_number(self):
        first = propose(self.root, self.request)
        self.assertEqual(propose(self.root, self.request), first)
        self.assertEqual(self.inspect('SELECT COUNT(*) FROM changes')[0][0], 1)
        self.assertEqual(self.inspect('SELECT COUNT(*) FROM tasks')[0][0], 1)
        self.assertEqual(self.inspect("SELECT value FROM counters WHERE prefix='AC'")[0][0], 1)

    def test_plan_cannot_target_internal_records_or_host_configuration(self):
        for scope in ['evolve/project.md', '.evolve-local/control/guard.json', '.claude/settings.json']:
            request = {**self.request, 'input': {**self.request['input'], 'scope': [scope]}}
            with self.subTest(scope=scope), self.assertRaises(EvolveError):
                propose(self.root, request)
        self.assertEqual(self.inspect('SELECT COUNT(*) FROM changes')[0][0], 0)

    def test_unpresented_or_different_plan_text_is_not_accepted_as_presented(self):
        request = {**self.request, 'input': {**self.request['input'], 'presentation': {
            'text': 'different text', 'source': 'fixture-message'}}}
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, request)
        self.assertEqual(caught.exception.code, 'PRESENTATION')
        self.assertEqual(self.inspect('SELECT COUNT(*) FROM changes')[0][0], 0)

    def test_unknown_check_cannot_become_an_execution_instruction(self):
        request = {**self.request, 'input': {**self.request['input'], 'required_checks': ['unknown']}}
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, request)
        self.assertEqual(caught.exception.code, 'CHECK_CONFIG')

    def test_unimplemented_required_deliverables_are_rejected_instead_of_ignored(self):
        request = {**self.request, 'input': {**self.request['input'], 'required_knowledge': [{'path': 'evolve/project.md'}]}}
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, request)
        self.assertEqual(caught.exception.code, 'UNAVAILABLE')
        self.assertEqual(self.inspect('SELECT COUNT(*) FROM changes')[0][0], 0)

    def test_complexity_or_specification_cannot_be_silently_treated_as_a_short_plan(self):
        for extra in ({'complexity': 'complex'}, {'spec': {'requirements': ['a structured feature']}}):
            with self.subTest(extra=extra):
                request = {**self.request, 'input': {**self.request['input'], **extra}}
                with self.assertRaises(EvolveError) as caught:
                    propose(self.root, request)
                self.assertEqual(caught.exception.code, 'INPUT' if extra.get('complexity') == 'complex' else 'UNAVAILABLE')
        self.assertEqual(self.inspect('SELECT COUNT(*) FROM changes')[0][0], 0)


if __name__ == '__main__':
    unittest.main()
