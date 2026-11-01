"""An actual external candidate is an immutable record, not permission or execution."""
import copy
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.errors import EvolveError
from evolve_core.external import prepare
from evolve_core.package import canonical, digest
from evolve_core.reading import current_state


class ExternalPrepareTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)

    def test_prepared_real_candidate_preserves_exact_target_and_indirect_material_without_dispatch(self):
        request = self.f.request(request_id='actual-candidate')
        before = self.f.database.read_bytes()
        result = prepare(self.f.root, request)
        self.assertEqual(result['outcome'], 'external_candidate_prepared')
        self.assertFalse(result['dispatch_performed'])
        self.assertEqual(result['approval'], 'not_implied')
        self.assertTrue(result['ready'])
        candidate = result['candidate']
        self.assertEqual(result['candidate_digest'], digest(canonical(candidate)))
        self.assertEqual({r['path']: r['content'] for r in candidate['execution']['files']}, self.f.files)
        self.assertEqual(candidate['preconditions_observed'][0]['rows'], [[1, 10]])
        self.assertEqual(candidate['effects_before'][0]['rows'], [[1, 10]])
        self.assertEqual(self.f.database.read_bytes(), before)
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(0,)])
        self.assertEqual(prepare(self.f.root, request), result)
        self.assertFalse(current_state(self.f.root)['changes'])
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM artifacts WHERE kind='external_candidate'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM phase_runs WHERE status='started'").fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0], 0)

    def test_a_missing_effect_or_wrong_target_grant_stops_before_candidate_history(self):
        before = self.f.database.read_bytes()
        for kind in ('missing-read-effect', 'other-environment', 'other-data-scope'):
            request = copy.deepcopy(self.f.request())
            if kind == 'missing-read-effect':request['authorization']['effect_kinds'] = ['project_records']
            elif kind == 'other-environment':request['authorization']['external_targets'][0]['environment'] = 'production'
            else:request['authorization']['external_targets'][0]['scope'] = 'some other range'
            with self.subTest(kind=kind), self.assertRaises(EvolveError) as error:
                prepare(self.f.root, request)
            self.assertIn(error.exception.code, ('AUTHORIZATION', 'EXTERNAL_AUTHORIZATION'))
        self.assertEqual(self.f.database.read_bytes(), before)
        with sqlite3.connect(self.f.root / 'evolve/history.db') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM phase_runs').fetchone()[0], 1)

    def test_actual_precondition_mismatch_is_saved_as_unready_without_target_write(self):
        with sqlite3.connect(self.f.database) as db:
            db.execute('UPDATE ledger SET value=15 WHERE id=1')
        result = prepare(self.f.root, self.f.request())
        self.assertFalse(result['ready'])
        self.assertEqual(result['candidate']['preconditions_observed'][0]['rows'], [[1, 15]])
        self.assertEqual(self.f.rows('SELECT value FROM ledger WHERE id=1'), [(15,)])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(0,)])
