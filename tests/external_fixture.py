"""A real finite Python/SQL project mechanism against an actual temporary target."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import uuid


ENTRY = '''import json,sys
from helper import execute
print(json.dumps(execute(sys.argv[1], sys.argv[2])))
'''
HELPER = '''import json,sqlite3
from pathlib import Path

def execute(path, operation_id):
    alias=json.loads(Path('alias.json').read_text())
    sql=Path(alias['sql']).read_text()
    db=sqlite3.connect(path, isolation_level=None)
    try:
        db.execute('BEGIN IMMEDIATE')
        identity=db.execute('SELECT value FROM identity').fetchone()[0]
        if identity != alias['identity']: raise RuntimeError('wrong actual target')
        previous=db.execute('SELECT operation_id FROM operation_receipts WHERE operation_id=?',(operation_id,)).fetchone()
        if previous:
            db.rollback()
            return {'operation_id':operation_id,'target_identity':identity,'provider_operation_ref':operation_id}
        before=db.execute('SELECT value FROM ledger WHERE id=1').fetchone()[0]
        if before != alias['before']: raise RuntimeError('actual target precondition changed')
        db.execute(sql,(alias['after'],alias['before']))
        known={'ledger_id':1,'before':before,'after':alias['after'],'complete_scope':True}
        db.execute('INSERT INTO operation_receipts VALUES (?,?,?,1)',(operation_id,'succeeded',json.dumps(known)))
        db.commit()
        return {'operation_id':operation_id,'target_identity':identity,'provider_operation_ref':operation_id}
    finally:
        db.close()
'''


class ExternalFixture:
    def __init__(self, *, with_work=False):
        from evolve_core.connect import connect
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-real-data-action-')
        self.root = Path(self.temp.name).resolve()
        self.database = self.root / 'business.db'
        with sqlite3.connect(self.database) as db:
            db.executescript("CREATE TABLE identity(value TEXT); INSERT INTO identity VALUES ('temporary-external-target'); "
                'CREATE TABLE ledger(id INTEGER PRIMARY KEY,value INTEGER); INSERT INTO ledger VALUES(1,10); '
                'CREATE TABLE operation_receipts(operation_id TEXT PRIMARY KEY,outcome TEXT,known_effects_json TEXT,finished INTEGER);')
        self.files = {'writer.py': ENTRY, 'helper.py': HELPER,
            'step.sql': 'UPDATE ledger SET value=? WHERE id=1 AND value=?;\n',
            'alias.json': json.dumps({'sql': 'step.sql', 'identity': 'temporary-external-target', 'before': 10, 'after': 20})}
        for name, text in self.files.items():
            (self.root / name).write_text(text)
        self.target = {'kind': 'sqlite', 'path': 'business.db', 'environment': 'isolated',
            'objects': ['ledger', 'operation_receipts'], 'scope': 'ledger id=1 and this operation receipt only',
            'identity': {'sql': 'SELECT value FROM identity', 'expected': 'temporary-external-target'}}
        self.auth = {'source': 'actual-uniform-human-authorization-specific-controlled-external-fixture',
            'text': 'In this temporary controlled project only, prepare the exact Python/helper/alias/SQL candidate and inspect this SQLite identity/scope; later writes require the exact saved candidate approval.',
            'effect_kinds': ['project_records', 'external_read', 'external_write'], 'paths': [],
            'external_targets': [{**{k: self.target[k] for k in ('kind', 'path', 'environment', 'objects', 'scope')},
                                  'provider_identity': self.target['identity']['expected']}]}
        checks = []
        if with_work:
            self.auth['effect_kinds'].append('checks')
            (self.root / 'test_target.py').write_text('import sqlite3,unittest\nclass Target(unittest.TestCase):\n    def test_actual_target(self):\n        with sqlite3.connect("file:business.db?mode=ro",uri=True) as db:\n            self.assertEqual(db.execute("SELECT id,value FROM ledger").fetchall(),[(1,20)])\n')
            checks = [{'id': 'data', 'argv': [sys.executable, '-B', '-m', 'unittest', 'test_target'], 'cwd': '.', 'timeout': 30}]
        result = connect(self.root, {'authorization': self.auth, 'input': {'checks': checks}})
        self.identity = {'project_id': result['project_id'], 'expected_workspace_epoch': result['workspace_epoch']}
        self.data = {'stage': 'prepare', 'target': self.target, 'execution': {
            'files': sorted(self.files), 'argv': ['writer.py', '{target}', '{operation_id}'], 'cwd': '.', 'closure': {
                'complete': True, 'no_detached_or_delayed_work': True, 'observer': 'controlled-actual-source-review',
                'basis': 'Read the finite entry/helper/alias/SQL; helper pins identity and prior value inside its transaction, writes one ledger row and its provider receipt, without delayed/background work.',
                'limitations': ['Only this actual temporary project mechanism; not arbitrary Python or a production provider.']}},
            'idempotency': {'supported': True, 'basis': 'Actually inspected helper: unique operation_receipts key is tested inside the same BEGIN IMMEDIATE transaction before any ledger update.'},
            'preconditions': [{'sql': 'SELECT id,value FROM ledger WHERE id=1', 'parameters': [], 'expected_rows': [[1, 10]], 'description': 'Exact approved prior ledger row.'}],
            'reconciliation': {'receipt': {'sql': 'SELECT operation_id,outcome,known_effects_json,finished FROM operation_receipts WHERE operation_id=?', 'parameters': ['{operation_id}']},
                'complete_scope': True, 'coverage_basis': 'Only ledger id=1 plus this unique operation receipt may change; actually checked all frozen source and target schema.',
                'effects': [{'sql': 'SELECT id,value FROM ledger WHERE id=1', 'parameters': [], 'expected_rows': [[1, 20]], 'description': 'Entire approved business row, independently observed from actual target.'}]},
            'limitations': ['The project mechanism provides a unique SQLite receipt and identity/value checks in the same transaction; only this local synchronous mechanism is supported.']}

        self.plan = None
        if with_work:
            from evolve_core.plans import propose
            self.plan = propose(self.root, self.request({'title': 'Update the isolated ledger',
                'plan': 'Update only ledger id=1 from 10 to 20 through the fixed Python/SQL mechanism and a unique provider receipt; keep all mechanism and independent test bytes unchanged.',
                'completion': 'Actual target/data check and independent final verification pass.',
                'scope': sorted(self.files) + ['test_target.py'], 'required_checks': ['data'],
                'execution_kind': 'external_write', 'external_target': self.target,
                'acceptance': ['The actual isolated ledger row is (1,20) after this exact operation.'],
                'presentation': {'source': 'actual-controlled-fixture-specific-data-plan',
                    'text': 'Update only ledger id=1 from 10 to 20 through the fixed Python/SQL mechanism and a unique provider receipt; keep all mechanism and independent test bytes unchanged.'}}))

    def request(self, data=None, request_id=None):
        return {**self.identity, 'request_id': request_id or str(uuid.uuid4()),
                'authorization': self.auth, 'input': self.data if data is None else data}

    def work_request(self, data=None, request_id=None):
        with sqlite3.connect(self.root / 'evolve/history.db') as db:
            db.row_factory = sqlite3.Row
            task = db.execute('SELECT * FROM tasks WHERE id=?', (self.plan['task_id'],)).fetchone()
            change = db.execute('SELECT * FROM changes WHERE id=?', (self.plan['change_id'],)).fetchone()
            revision = db.execute('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],)).fetchone()
        request = self.request({**(self.data if data is None else data), 'change_id': change['id'],
            'revision_id': revision['id'], 'definition_digest': task['definition_digest'], 'accepted_plan_digest': revision['plan_digest']}, request_id)
        request['expected_versions'] = {'change': change['row_version'], 'task': task['row_version']}
        return request

    def rows(self, sql, parameters=()):
        with sqlite3.connect(self.database) as db:
            return db.execute(sql, parameters).fetchall()

    def close(self):
        self.temp.cleanup()
