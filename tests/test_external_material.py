"""Real target reads and fixed indirect material, before external dispatch is exposed."""
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core import external_material as material
from evolve_core.errors import EvolveError


class ExternalMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-actual-external-material-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.database = self.root / 'business.db'
        with sqlite3.connect(self.database) as db:
            db.executescript("CREATE TABLE identity(value TEXT); INSERT INTO identity VALUES ('temporary-target-a'); "
                             'CREATE TABLE ledger(id INTEGER PRIMARY KEY, value INTEGER); INSERT INTO ledger VALUES (1,10);')
        (self.root / 'write.py').write_text('import sqlite3,sys\nfrom helper import sql\n'
            'with sqlite3.connect(sys.argv[1]) as db: db.executescript(sql())\n')
        (self.root / 'helper.py').write_text('from pathlib import Path\nimport json\ndef sql():\n'
            '    return Path(json.loads(Path("alias.json").read_text())["sql"]).read_text()\n')
        (self.root / 'step.sql').write_text('UPDATE ledger SET value=20 WHERE id=1;\n')
        (self.root / 'alias.json').write_text('{"sql":"step.sql"}')
        self.target = {'kind': 'sqlite', 'path': 'business.db', 'environment': 'isolated',
            'objects': ['ledger'], 'scope': 'ledger id=1 only',
            'identity': {'sql': 'SELECT value FROM identity', 'expected': 'temporary-target-a'}}
        self.execution = {'files': ['write.py', 'helper.py', 'step.sql', 'alias.json'],
            'argv': ['write.py', '{target}', '{operation_id}'], 'cwd': '.', 'closure': {
                'complete': True, 'no_detached_or_delayed_work': True,
                'observer': 'actual-controlled-fixture-under-uniform-human-authorization',
                'basis': 'Actually read this finite entry, imported helper, alias and SQL; only the selected temporary ledger is written, no background work.',
                'limitations': ['Only this temporary local SQLite mechanism, not arbitrary Python or production.']}}

    def candidate(self):
        return {'target': self.target, 'target_snapshot': material.target_snapshot(self.root, self.target),
                'execution': material.collect_material(self.root, self.execution, self.database)}

    def assert_error(self, code, function, *args):
        with self.assertRaises(EvolveError) as error:
            function(*args)
        self.assertEqual(error.exception.code, code)

    def test_actual_frozen_helper_alias_and_indirect_sql_are_the_executed_bytes(self):
        candidate = self.candidate()
        folder = self.root / '.evolve-local/control/frozen'
        material.freeze_material(folder, candidate)
        material.require_current(self.root, candidate)
        # Controller changes live SQL after the actual predispatch check; the frozen
        # mechanism still reads the exact approved copy, not these later live bytes.
        (self.root / 'step.sql').write_text('UPDATE ledger SET value=999 WHERE id=1;\n')
        result = subprocess.run([candidate['execution']['interpreter']['path'], '-B', str(folder / 'write.py'),
                                 str(self.database), 'controlled-operation'], cwd=folder, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(material.read_query(self.database, 'SELECT value FROM ledger')['rows'], [[20]])
        self.assertIn('999', (self.root / 'step.sql').read_text())
        self.assert_error('EXTERNAL_MATERIAL_CHANGED', material.require_current, self.root, candidate)

    def test_entry_indirect_sql_helper_and_alias_changes_invalidate_the_approval(self):
        candidate = self.candidate()
        for name in ('write.py', 'helper.py', 'step.sql', 'alias.json'):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b'\n# changed after candidate\n')
                self.assert_error('EXTERNAL_MATERIAL_CHANGED', material.require_current, self.root, candidate)
                self.assertEqual(material.read_query(self.database, 'SELECT value FROM ledger')['rows'], [[10]])
                path.write_bytes(original)
        material.require_current(self.root, candidate)

    def test_actual_provider_identity_schema_and_replaced_target_are_not_aliases(self):
        candidate = self.candidate()
        original = self.database.read_bytes()
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE identity SET value='other-target'")
        self.assert_error('EXTERNAL_TARGET_CHANGED', material.require_current, self.root, candidate)
        self.database.write_bytes(original)
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE other(value INTEGER)')
        self.assert_error('EXTERNAL_TARGET_CHANGED', material.require_current, self.root, candidate)
        replacement = self.root / 'replacement.db'
        replacement.write_bytes(original)
        replacement.replace(self.database)
        self.assert_error('EXTERNAL_TARGET_CHANGED', material.require_current, self.root, candidate)

    def test_read_only_observer_cannot_update_or_attach_or_create_another_database(self):
        outside = self.root / 'must-not-create.db'
        self.assert_error('EXTERNAL_OBSERVATION', material.read_query, self.database, 'UPDATE ledger SET value=99')
        self.assert_error('EXTERNAL_OBSERVATION', material.read_query, self.database, 'ATTACH DATABASE ? AS other', [str(outside)])
        self.assertFalse(outside.exists())
        self.assertEqual(material.read_query(self.database, 'SELECT value FROM ledger')['rows'], [[10]])
        self.assert_error('EXTERNAL_OBSERVATION', material.read_query, self.database, 'SELECT zeroblob(1000000)')
        self.assert_error('EXTERNAL_QUERY_LIMIT', material.read_query, self.database,
            'WITH RECURSIVE seq(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM seq WHERE n<1002) SELECT n FROM seq')

    def test_incomplete_dynamic_linked_or_oversize_material_is_never_complete(self):
        incomplete = {**self.execution, 'closure': {**self.execution['closure'], 'complete': False}}
        self.assert_error('EXTERNAL_CLOSURE', material.collect_material, self.root, incomplete, self.database)
        original = (self.root / 'helper.py').read_bytes()
        (self.root / 'helper-copy.py').write_bytes(original)
        (self.root / 'helper.py').unlink()
        (self.root / 'helper.py').symlink_to(self.root / 'helper-copy.py')
        self.assert_error('EXTERNAL_PATH', material.collect_material, self.root, self.execution, self.database)
        (self.root / 'helper.py').unlink(); (self.root / 'helper.py').write_bytes(original)
        with patch.object(material, 'MAX_MATERIAL_BYTES', 1):
            self.assert_error('EXTERNAL_MATERIAL_LIMIT', material.collect_material, self.root, self.execution, self.database)
        self.assertEqual(material.read_query(self.database, 'SELECT value FROM ledger')['rows'], [[10]])

    def test_frozen_tampering_extra_imports_and_line_endings_are_not_silent_changes(self):
        path = self.root / 'step.sql'
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        candidate = self.candidate()
        folder = self.root / '.evolve-local/control/frozen'
        material.freeze_material(folder, candidate)
        self.assertEqual((folder / 'step.sql').read_bytes(), path.read_bytes())
        (folder / 'unexpected.py').write_text('raise RuntimeError("undeclared helper")\n')
        self.assert_error('EXTERNAL_MATERIAL_CHANGED', material.validate_frozen, folder, candidate)
        (folder / 'unexpected.py').unlink()
        (folder / 'step.sql').write_text('UPDATE ledger SET value=99;\n')
        self.assert_error('EXTERNAL_MATERIAL_CHANGED', material.validate_frozen, folder, candidate)
