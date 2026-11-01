"""Real SQL development uses the ordinary analysis/Change/Task/VER workflow."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))

from evolve_core.analysis import investigate
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.connect import connect
from evolve_core.package import canonical, digest
from evolve_core.plans import propose
from evolve_core.store import now
from evolve_core.verify import verify
from evolve_core.work import fingerprint


ORDERS = [
    ['A', '2026-10-30', 1, 10], ['A', '2026-10-30', 2, 12], ['A', '2026-10-30', 2, 12],
    ['B', '2026-10-30', 1, -2], ['C', '2026-10-30', 1, 9], ['C', '2026-10-30', 2, None],
    ['A', '2026-10-31', 1, 5], ['D', '2026-10-31', 1, 3], ['Z', '2026-10-29', 1, 100],
]
BROKEN = 'SELECT COALESCE(SUM(amount),0), COUNT(*) FROM orders;\n'
FIXED = '''WITH latest AS (
 SELECT amount, ROW_NUMBER() OVER (
  PARTITION BY business_date, order_id ORDER BY revision DESC
 ) AS n
 FROM orders WHERE business_date = :business_date
)
SELECT COALESCE(SUM(amount),0), COUNT(*) FROM latest
WHERE n = 1 AND amount IS NOT NULL;
'''
CHECK = '''import json,sqlite3,unittest
from pathlib import Path
class Reconciliation(unittest.TestCase):
    def actual(self,day):
        with sqlite3.connect(':memory:') as con:
            con.execute('CREATE TABLE orders(order_id TEXT,business_date TEXT,revision INTEGER,amount INTEGER)')
            con.executemany('INSERT INTO orders VALUES (?,?,?,?)',json.loads(Path('orders.json').read_text()))
            rows=con.execute(Path('model.sql').read_text(),{'business_date':day}).fetchall()
            self.assertEqual(len(rows),1)
            return rows[0]
    def test_first_date_latest_duplicate_refund_and_null(self):
        self.assertEqual(self.actual('2026-10-30'),(10,2))
    def test_second_date_is_a_separate_grain(self):
        self.assertEqual(self.actual('2026-10-31'),(8,2))
    def test_empty_date_does_not_include_other_dates(self):
        self.assertEqual(self.actual('2026-11-01'),(0,0))
'''


class SQLWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-sql-workflow-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'orders.json').write_text(json.dumps(ORDERS))
        (self.root / 'model.sql').write_text(BROKEN)
        (self.root / 'test_reconciliation.py').write_text(CHECK)
        self.auth = {'source': 'explicit-controlled-SQL-fixture',
            'text': 'Repair only model.sql; keep the independent literal checks and input fixture; validate only isolated in-memory SQLite.',
            'effect_kinds': ['project_records', 'business_files', 'checks'], 'paths': ['model.sql']}
        self.check = {'id': 'reconcile', 'argv': [sys.executable, '-B', '-m', 'unittest', 'test_reconciliation', '-v'],
                      'cwd': '.', 'timeout': 10}
        connected = connect(self.root, {'authorization': self.auth, 'input': {'checks': [self.check]}})
        self.identity = {'project_id': connected['project_id'], 'expected_workspace_epoch': connected['workspace_epoch']}

    def literal_check(self):
        return subprocess.run(self.check['argv'], cwd=self.root, text=True, capture_output=True)

    def rows(self, sql, values=()):
        with sqlite3.connect(self.root / 'evolve/history.db') as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(sql, values)]

    def prepare(self):
        before = self.literal_check()
        self.assertEqual(before.returncode, 1)
        self.assertIn('FAILED (failures=3)', before.stderr)
        request = {**self.identity, 'authorization': self.auth, 'input': {
            'question': 'Why do daily order totals mix dates and revisions?',
            'scope': ['orders.json', 'model.sql', 'test_reconciliation.py'],
            'business_effect': 'read_only', 'record_intent': 'record',
            'sources': [{'id': key, 'kind': 'file', 'path': name, 'expected_digest': digest((self.root / name).read_bytes()),
                'observer': 'controlled-SQL-file-reader', 'observed_at': now(), 'limitations': [],
                'data_scope': {'objects': ['orders'], 'business_dates': ['2026-10-30', '2026-10-31', '2026-11-01']}}
                for key, name in (('S1', 'orders.json'), ('S2', 'model.sql'), ('S3', 'test_reconciliation.py'))]
                + [{'id': 'S4', 'kind': 'observation', 'object': 'isolated reconciliation command',
                    'version': digest((self.root / 'model.sql').read_bytes()), 'method': ' '.join(self.check['argv']),
                    'observer': 'actual-subprocess-runner', 'observed_at': now(),
                    'content': before.stdout + before.stderr, 'limitations': ['Only the fixed in-memory SQLite fixture.']}],
            'analysis': {'answer_status': 'answered', 'conclusion': 'The saved SQL omits both date selection and latest-order deduplication.',
                'observations': [{'local_key': 'F1', 'statement': 'Actual independent literal reconciliation failed all three date cases.', 'sources': ['S2', 'S3', 'S4']}],
                'hypotheses': [], 'coverage': ['Three declared dates; latest revision per order/day; null and refund behavior.'],
                'limitations': ['No production query or data modification was performed. Identical revision ties in the fixture have identical amounts.'],
                'remaining_questions': [], 'next_steps': ['Repair SQL only under the explicit grant.'],
                'data_context': {'objects': ['orders'], 'business_dates': ['2026-10-30', '2026-10-31', '2026-11-01'],
                    'grain': 'One aggregate per business date, one latest revision per order within that date.',
                    'definitions': ['Select latest revision before excluding null amounts; include negative refunds; empty date is total zero and count zero.'],
                    'source_ids': ['S1'], 'limitations': ['Literal fixture scope only, not production freshness.']},
                'relationships': [{'local_key': 'R1', 'source': 'orders', 'target': 'daily_totals',
                    'transformation': 'The current SQL sums all rows without date selection or latest-revision filtering.',
                    'certainty': 'observed', 'sources': ['S2'], 'limitations': ['Current SQL text only.']}],
                'symptom': {'criterion': {'check': self.check, 'method': ' '.join(self.check['argv']),
                    'environment': 'Disposable in-memory SQLite with orders.json',
                    'side_effects': 'In-memory fixture tables only; no persistent business database.',
                    'input': {'dates': ['2026-10-30', '2026-10-31', '2026-11-01']},
                    'expected': {'2026-10-30': [10, 2], '2026-10-31': [8, 2], '2026-11-01': [0, 0]},
                    'expected_source': 'S3'}, 'status': 'reproduced', 'attempts': 1, 'failures': 1,
                    'sources': ['S3', 'S4'], 'limitations': ['This exact fixture only.']}}}}
        observed = investigate(self.root, request)
        source = {'run_id': observed['run_id'], 'result_digest': digest(canonical(observed)),
                  'criterion_digest': observed['criterion_digest'], 'adoption_basis': 'The original literal checks and exact fixture are unchanged.'}
        text = 'Repair only model.sql: select the business date, choose the latest order revision, then exclude null amounts and reconcile totals/counts.'
        self.plan = propose(self.root, {**self.identity, 'authorization': self.auth, 'input': {
            'title': 'Repair daily order SQL', 'plan': text, 'completion': 'All three original date reconciliations pass.',
            'scope': ['model.sql'], 'acceptance': ['Daily totals/counts are (10,2), (8,2), (0,0) for the declared dates.'],
            'required_checks': ['reconcile'], 'analysis_basis': source,
            'presentation': {'source': 'actual-controlled-short-plan', 'text': text}}})
        self.observed = observed
        return source

    def request(self, data):
        change = self.rows('SELECT * FROM changes WHERE id=?', (self.plan['change_id'],))[0]
        task = self.rows('SELECT * FROM tasks WHERE id=?', (self.plan['task_id'],))[0]
        return {**self.identity, 'authorization': self.auth,
            'expected_versions': {'change': change['row_version'], 'task': task['row_version']},
            'input': {'change_id': change['id'], 'revision_id': change['current_revision'],
                      'definition_digest': task['definition_digest'], **data}}

    def verify_request(self, status='passed', evidence='Actual original reconciliation checks passed.'):
        task = self.rows('SELECT definition_json FROM tasks WHERE id=?', (self.plan['task_id'],))[0]
        definition = json.loads(task['definition_json'])
        snapshot = fingerprint(self.root, definition)
        reviews = [{'axis': axis, 'observer': 'controlled actual SQL/literal reviewer, not an independent model',
            'summary': 'Read SQL, fixture and immutable independent expectations for date, grain, deduplication, nulls and refunds.',
            'fingerprint_digest': snapshot['digest'], 'findings': []} for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': ac['id'], 'status': status,
            'basis': evidence} for ac in self.plan['acceptance']]
        return self.request({'reviews': reviews, 'symptom_result': {
            'criterion_digest': self.observed['criterion_digest'], 'fingerprint_digest': snapshot['digest'],
            'status': status, 'observer': 'actual-controlled-check-runner', 'basis': evidence, 'evidence': evidence,
            'limitations': ['Isolated fixture, no formal data execution.'], 'observed_at': now(),
            'attempts': 1, 'failures': 0 if status == 'passed' else 1}})

    def finish(self):
        self.prepare()
        implemented = implement(self.root, self.request({'accepted_plan_digest': self.plan['plan_digest'],
            'files': [{'path': 'model.sql', 'expected_digest': digest((self.root / 'model.sql').read_bytes()), 'content': FIXED}]}))
        self.assertEqual(implemented['outcome'], 'implemented')
        self.assertEqual(self.literal_check().returncode, 0)
        checked = verify(self.root, self.verify_request())
        self.assertEqual(checked['status'], 'passed')
        closed = archive(self.root, self.request({'verification_id': checked['verification_id']}))
        self.assertEqual(closed['outcome'], 'archived')
        return checked

    def test_real_sql_fix_reconciles_original_literals_and_archives_without_formal_data_execution(self):
        before = {name: (self.root / name).read_bytes() for name in ('orders.json', 'test_reconciliation.py')}
        checked = self.finish()
        self.assertEqual({name: (self.root / name).read_bytes() for name in before}, before)
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'archived')
        self.assertEqual(self.rows('SELECT count(*) AS n FROM knowledge_proposals')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT count(*) AS n FROM resource_claims')[0]['n'], 0)
        self.assertEqual(self.rows("SELECT count(*) AS n FROM phase_runs WHERE status='started'")[0]['n'], 0)
        items = json.loads(self.rows('SELECT items_json FROM verifications WHERE id=?', (checked['verification_id'],))[0]['items_json'])
        self.assertEqual(items['symptom_result']['status'], 'passed')

    def test_later_data_change_adds_failed_verification_without_reopening_archived_sql_work(self):
        original = self.finish()
        rows = json.loads((self.root / 'orders.json').read_text())
        rows[1][3] = rows[2][3] = 99
        (self.root / 'orders.json').write_text(json.dumps(rows))
        observed = self.literal_check()
        self.assertEqual(observed.returncode, 1)
        result = verify(self.root, self.verify_request('failed', observed.stdout + observed.stderr))
        self.assertIn(result['status'], ('failed', 'blocked'))
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'archived')
        self.assertEqual(self.rows('SELECT status FROM verifications WHERE id=?', (original['verification_id'],))[0]['status'], 'passed')
        self.assertEqual((self.root / 'model.sql').read_text(), FIXED)
