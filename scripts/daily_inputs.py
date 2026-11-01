"""Frozen inputs for the same-project M2 composition; source-only acceptance data."""
import json
ORDERS = [['A', '2026-10-30', 1, 10],
 ['A', '2026-10-30', 2, 12],
 ['A', '2026-10-30', 2, 12],
 ['B', '2026-10-30', 1, -2],
 ['C', '2026-10-30', 1, 9],
 ['C', '2026-10-30', 2, None],
 ['A', '2026-10-31', 1, 5],
 ['D', '2026-10-31', 1, 3],
 ['Z', '2026-10-29', 1, 100]]
SQL_BROKEN = 'SELECT COALESCE(SUM(amount),0), COUNT(*) FROM orders;\n'
SQL_CHECK = "import json,sqlite3,unittest\nfrom pathlib import Path\nclass Reconciliation(unittest.TestCase):\n    def actual(self,day):\n        with sqlite3.connect(':memory:') as con:\n            con.execute('CREATE TABLE orders(order_id TEXT,business_date TEXT,revision INTEGER,amount INTEGER)')\n            con.executemany('INSERT INTO orders VALUES (?,?,?,?)',json.loads(Path('orders.json').read_text()))\n            rows=con.execute(Path('model.sql').read_text(),{'business_date':day}).fetchall()\n            self.assertEqual(len(rows),1)\n            return rows[0]\n    def test_first_date_latest_duplicate_refund_and_null(self):\n        self.assertEqual(self.actual('2026-10-30'),(10,2))\n    def test_second_date_is_a_separate_grain(self):\n        self.assertEqual(self.actual('2026-10-31'),(8,2))\n    def test_empty_date_does_not_include_other_dates(self):\n        self.assertEqual(self.actual('2026-11-01'),(0,0))\n"

FILES = {
    'total.py': 'def total(values):\n    return len(values)\n',
    'report.py': 'from total import total\ndef render_total(values):\n    return "pending"\n',
    'test_total.py': 'import unittest\nfrom total import total\nclass TestTotal(unittest.TestCase):\n'
        '    def test_literals(self):\n        self.assertEqual(total([2,3]),5)\n        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n',
    'test_report.py': 'import unittest\nfrom report import render_total\nclass TestReport(unittest.TestCase):\n'
        '    def test_literal(self): self.assertEqual(render_total([2,3]),"5")\n',
    'test_integration.py': 'import unittest\nfrom report import render_total\nclass TestIntegration(unittest.TestCase):\n'
        '    def test_negative_report(self): self.assertEqual(render_total([-2,3]),"1")\n',
    'orders.json': json.dumps(ORDERS), 'model.sql': SQL_BROKEN, 'test_reconciliation.py': SQL_CHECK,
}
CHECKS = [{'id': key, 'argv': ['python3', '-B', '-m', 'unittest', *modules, '-v'], 'cwd': '.', 'timeout': 15}
    for key, modules in [('sum', ['test_total']), ('report', ['test_report']),
        ('integration', ['test_total', 'test_report', 'test_integration', 'test_reconciliation']),
        ('reconcile', ['test_reconciliation'])]]
GUIDE = '# 日常工作观察\n\n仅在内存 SQLite 固定订单样例核对三个日期；未验证生产数据时效。\n'
EXTERNAL_REPORT = 'from total import total\ndef render_total(values):\n    return "external:" + str(total(values))\n'
CASES = ('prepare', 'application', 'missing_check', 'sql_repair', 'integration', 'lineage', 'reexport', 'external_verify')
