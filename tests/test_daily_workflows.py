"""Four daily cases share actual checks, missing inputs and immutable historical results."""
import json
import unittest

from daily_cycle_fixture import DailyCycleFixture, CASES


class DailyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.f = DailyCycleFixture()
        self.addCleanup(self.f.close)

    def test_four_cases_keep_shared_integration_deferral_and_later_negative_truthful(self):
        for stage in CASES:
            getattr(self.f, stage)()
        f = self.f
        self.assertEqual({r['state'] for r in f.app.rows('SELECT * FROM changes')}, {'archived'})
        for name in ('test_total.py', 'test_report.py', 'test_integration.py', 'test_reconciliation.py', 'orders.json'):
            self.assertEqual((f.root / name).read_bytes(), f.original[name])
        self.assertEqual(len(f.negative), 3)
        self.assertFalse(f.app.rows('SELECT * FROM resource_claims'))
        self.assertFalse(f.app.rows("SELECT * FROM phase_runs WHERE status='started'"))
        self.assertEqual(f.app.rows('SELECT state FROM knowledge_proposals')[0]['state'], 'deferred')
        self.assertFalse(f.app.rows('SELECT * FROM spec_applications'))
        self.assertFalse((f.root / 'daily-guide.md').exists())
        failed = f.app.rows('SELECT items_json FROM verifications WHERE id=?', (f.negative['missing_check'],))[0]
        self.assertIn('integration', failed['items_json'])

    def test_missing_environment_does_not_succeed_or_create_replacement_tests(self):
        f = self.f
        f.prepare()
        f.application()
        target = f.root / 'test_reconciliation.py'
        target.unlink()
        before = {p.relative_to(f.root).as_posix(): p.read_bytes() for p in f.root.iterdir() if p.is_file()}
        f.missing_check(inject=False)
        self.assertFalse(target.exists())
        self.assertEqual(before, {p.relative_to(f.root).as_posix(): p.read_bytes() for p in f.root.iterdir() if p.is_file()})
        self.assertNotEqual(f.app.context()[0]['state'], 'archived')
        row = f.app.rows('SELECT items_json FROM verifications WHERE id=?', (f.negative['missing_check'],))[0]
        self.assertNotEqual(json.loads(row['items_json'])['checks'][0]['status'], 'passed')
