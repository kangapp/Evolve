"""Data observations and exports cross the real analysis/maintenance interfaces."""
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
import uuid
import zipfile
from unittest.mock import patch

import test_analysis as fixture
from evolve_core.analysis import investigate
from evolve_core.cli import main
from evolve_core.errors import EvolveError
from evolve_core.exporting import export_analysis
from evolve_core.package import canonical, digest
from evolve_core.plans import propose
from evolve_core.reading import current_state
from evolve_core.recover import recover
from evolve_core.store import now

ROOT = Path(__file__).resolve().parents[1]


class DataReportTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.InvestigationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        (self.root / 'orders.csv').write_text('order_id,business_date,amount\n1,2026-10-30,7\n2,2026-10-31,4\n')
        (self.root / 'model.sql').write_text('SELECT business_date, SUM(amount) FROM orders GROUP BY business_date;\n')
        self.f.connected()

    def request(self):
        request = self.f.payload()
        data = request['input']
        data.update(question='What feeds daily order totals?', scope=['orders.csv', 'model.sql'])
        data['sources'] = [{'id': key, 'kind': 'file', 'path': path,
            'expected_digest': digest((self.root / path).read_bytes()), 'observer': 'actual-fixture-reader',
            'observed_at': now(), 'limitations': [],
            'data_scope': {'objects': ['orders'], 'business_dates': ['2026-10-30', '2026-10-31']}}
            for key, path in (('S1', 'orders.csv'), ('S2', 'model.sql'))]
        data['analysis'] = {'answer_status': 'partial', 'conclusion': 'The saved SQL groups local orders by business date.',
            'coverage': ['Two local fixture dates and this SQL only'], 'limitations': ['Production sources were not queried.'],
            'remaining_questions': ['Production version and coverage remain unobserved.'], 'next_steps': ['Request a new scoped observation if needed.'],
            'observations': [{'local_key': 'F1', 'statement': 'SQL reads orders and groups by date.', 'sources': ['S1', 'S2']}], 'hypotheses': [],
            'data_context': {'objects': ['orders'], 'business_dates': ['2026-10-30', '2026-10-31'],
                'grain': 'One total per business date', 'definitions': ['Sum amount in the saved local fixture.'],
                'source_ids': ['S1'], 'limitations': ['Two fixture dates only; no current production guarantee.']},
            'relationships': [{'local_key': 'R1', 'source': 'orders', 'target': 'daily_totals',
                'transformation': 'GROUP BY business_date; SUM(amount)', 'certainty': 'observed', 'sources': ['S2'],
                'limitations': ['Only the saved SQL relation, not complete production lineage.']}]}
        return request

    def saved(self, request=None):
        result = investigate(self.root, request or self.request())
        return result, {'run_id': result['run_id'], 'result_digest': digest(canonical(result))}

    def export_request(self, source, output='report.md'):
        return {**self.f.identity, 'request_id': str(uuid.uuid4()), 'authorization': self.f.auth,
                'input': {'source': source, 'output': '.evolve-local/exports/' + output,
                          'format': 'json' if output.endswith('.json') else 'markdown'}}

    def test_data_and_relationships_are_saved_without_work_items_or_business_changes(self):
        request = self.request()
        before = {name: (self.root / name).read_bytes() for name in request['input']['scope']}
        result, reference = self.saved(request)
        selected = current_state(self.root, result['run_id'])['analyses'][0]
        self.assertEqual(selected['analysis']['data_context'], request['input']['analysis']['data_context'])
        self.assertEqual(selected['analysis']['relationships'], request['input']['analysis']['relationships'])
        self.assertEqual(selected['result_digest'], reference['result_digest'])
        self.assertEqual({name: (self.root / name).read_bytes() for name in before}, before)
        self.assertEqual(self.f.rows('SELECT count(*) AS n FROM changes')[0]['n'], 0)

    def test_analysis_cli_receipt_binds_saved_result_without_status_or_business_reobservation(self):
        request_file = self.root / 'request.json'
        request_file.write_text(json.dumps(self.request()))
        output = io.StringIO()
        with patch('sys.stdout', output):
            code = main(['--project', str(self.root), 'analyze', '--request', str(request_file)])
        self.assertEqual(code, 0, output.getvalue())
        result = json.loads(output.getvalue())['data']
        with sqlite3.connect(self.root / 'evolve/history.db') as connection:
            stored = connection.execute('SELECT result_digest FROM phase_runs WHERE id=?', (result['run_id'],)).fetchone()
        self.assertEqual(result['result_digest'], stored[0])
        (self.root / 'orders.csv').unlink()
        (self.root / 'model.sql').unlink()
        exported = export_analysis(self.root, self.export_request({key: result[key] for key in ('run_id', 'result_digest')}))
        self.assertEqual(exported['outcome'], 'exported')

    def test_expanding_business_dates_cannot_relabel_old_source_coverage(self):
        request = self.request()
        request['input']['analysis']['data_context']['business_dates'].append('2026-11-01')
        with self.assertRaises(EvolveError) as caught:
            investigate(self.root, request)
        self.assertEqual(caught.exception.code, 'DATA_SOURCE_SCOPE')
        self.assertEqual(self.f.rows("SELECT count(*) AS n FROM phase_runs WHERE action='analyze'")[0]['n'], 0)

    def test_unknown_data_fields_require_partial_answer_and_explicit_limits(self):
        request = self.request()
        request['input']['analysis']['data_context']['business_dates'] = None
        result, _ = self.saved(request)
        self.assertIsNone(result['analysis']['data_context']['business_dates'])
        request['request_id'] = str(uuid.uuid4())
        request['input']['analysis']['answer_status'] = 'answered'
        with self.assertRaisesRegex(EvolveError, 'Unknown data fields'):
            investigate(self.root, request)

    def test_relationship_claims_need_real_refs_and_bounded_inference(self):
        for change in ('missing_source', 'unbounded_inference', 'undated_observed'):
            request = self.request()
            relation = request['input']['analysis']['relationships'][0]
            if change == 'missing_source':
                relation['sources'] = ['MISSING']
            elif change == 'unbounded_inference':
                relation.update(certainty='inferred', limitations=[])
            else:
                request['input']['sources'][1].update(observed_at=None, limitations=['Unknown observation time.'])
            with self.subTest(change=change), self.assertRaises(EvolveError):
                investigate(self.root, request)

    def test_local_drift_and_external_unknown_are_reported_without_new_observations(self):
        request = self.request()
        request['input']['sources'].append({'id': 'S3', 'kind': 'observation', 'object': 'production.orders',
            'version': 'observed-snapshot-1', 'method': 'third-party read-only count', 'observer': 'named-third-party',
            'observed_at': now(), 'content': 'count=2', 'limitations': ['Historical external observation, not queried by this tool.']})
        result, _ = self.saved(request)
        database = self.root / 'evolve/history.db'
        before = database.read_bytes()
        (self.root / 'orders.csv').write_text('later local data\n')
        selected = current_state(self.root, result['run_id'])['analyses'][0]
        states = {item['source_id']: item for item in selected['source_applicability']}
        self.assertEqual(states['S1']['status'], 'local_bytes_changed')
        self.assertEqual(states['S3']['status'], 'not_reobserved')
        self.assertEqual(states['S3']['external_data'], 'not_observed')
        self.assertEqual(database.read_bytes(), before)

    def test_changed_local_data_cannot_be_used_as_the_old_repair_basis(self):
        _, source = self.saved()
        (self.root / 'orders.csv').write_text('different input version\n')
        text = 'Repair only model.sql against the observed literal reconciliation.'
        request = {**self.f.identity, 'authorization': self.f.auth, 'input': {'title': 'Repair data query',
            'plan': text, 'completion': 'Independent reconciliation passes.', 'scope': ['model.sql'],
            'required_checks': [], 'acceptance': ['Original data scope remains applicable.'],
            'analysis_basis': {**source, 'adoption_basis': 'Use this observed scope.'},
            'presentation': {'source': 'actual-fixture-presentation', 'text': text}}}
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, request)
        self.assertEqual(caught.exception.code, 'DATA_EVIDENCE_CHANGED')
        self.assertEqual(self.f.rows('SELECT count(*) AS n FROM changes')[0]['n'], 0)

    def test_export_uses_saved_facts_after_source_deletion_without_moving_analysis_head(self):
        original, source = self.saved()
        (self.root / 'orders.csv').unlink()
        (self.root / 'model.sql').unlink()
        result = export_analysis(self.root, self.export_request(source))
        self.assertEqual(result['view_status'], 'written')
        body = (self.root / result['output']).read_text()
        self.assertIn('```mermaid', body)
        self.assertIn('daily_totals', body)
        self.assertIn('2026-10-30', body)
        self.assertIn('not complete production lineage', body)
        self.assertEqual(self.f.rows("SELECT count(*) AS n FROM phase_runs WHERE action='analyze'")[0]['n'], 1)
        selected = current_state(self.root, original['run_id'])['analyses'][0]
        self.assertEqual(selected['current_head'], original['run_id'])

    def test_cli_export_does_not_load_business_status_for_identity_binding(self):
        _, source = self.saved()
        request = self.export_request(source, 'cli.json')
        request.pop('request_id')
        request.pop('project_id')
        request.pop('expected_workspace_epoch')
        with patch('sys.stdin', io.StringIO(json.dumps(request))), patch('sys.stdout', new_callable=io.StringIO) as output:
            with patch('evolve_core.cli.project_status', side_effect=AssertionError('Business status must not be read')):
                code = main(['--project', str(self.root), 'maintain', '--owner', 'evolve-maintain', '--method', 'export', '--request', '-'])
        self.assertEqual(code, 0, output.getvalue())
        self.assertTrue(json.loads(output.getvalue())['ok'])

    def test_json_and_repeated_export_preserve_the_exact_original_receipt(self):
        _, source = self.saved()
        request = self.export_request(source, 'facts.json')
        first = export_analysis(self.root, request)
        path = self.root / first['output']
        body = json.loads(path.read_text())
        self.assertEqual(body['source'], source)
        self.assertFalse(body['business_sources_reobserved'])
        path.write_text('later third-party view')
        self.assertEqual(export_analysis(self.root, request), first)
        self.assertEqual(path.read_text(), 'later third-party view')

    def test_output_conflict_and_failure_do_not_change_analysis_or_overwrite_views(self):
        original, source = self.saved()
        request = self.export_request(source)
        output = self.root / request['input']['output']
        output.parent.mkdir(parents=True)
        output.write_text('third-party report')
        first = export_analysis(self.root, request)
        self.assertEqual(first['outcome'], 'view_stale')
        self.assertEqual(output.read_text(), 'third-party report')
        with patch('evolve_core.exporting.durable_write', side_effect=OSError('controlled export failure')):
            second = export_analysis(self.root, self.export_request(source, 'failed.md'))
        self.assertEqual(second['view_status'], 'stale')
        self.assertEqual(current_state(self.root, original['run_id'])['analyses'][0]['current_head'], original['run_id'])
        self.assertEqual(self.f.rows("SELECT count(*) AS n FROM phase_runs WHERE status='started'")[0]['n'], 0)

    def test_export_rejects_business_outputs_and_linked_export_directories(self):
        _, source = self.saved()
        request = self.export_request(source)
        request['input']['output'] = 'model.sql'
        with self.assertRaises(EvolveError):
            export_analysis(self.root, request)
        folder = self.root / '.evolve-local/exports'
        folder.mkdir()
        (folder / 'alias').symlink_to(self.root, target_is_directory=True)
        request = self.export_request(source, 'alias/unauthorized.md')
        with self.assertRaises(EvolveError):
            export_analysis(self.root, request)
        self.assertFalse((self.root / 'unauthorized.md').exists())

    def test_historical_export_includes_recorded_correction_without_replacing_old_facts(self):
        first, source = self.saved()
        request = self.request()
        request['input']['previous'] = source
        request['input']['analysis']['observations'][0]['corrects'] = [{**source, 'local_key': 'F1'}]
        request['input']['analysis']['observations'][0]['statement'] = 'Clarify that only this local SQL was inspected.'
        latest = investigate(self.root, request)
        result = export_analysis(self.root, self.export_request(source, 'historical.json'))
        report = json.loads((self.root / result['output']).read_text())
        self.assertEqual(report['analysis'], first['analysis'])
        self.assertEqual(report['recorded_head'], latest['run_id'])
        self.assertEqual(report['recorded_corrections'][0]['source_run_id'], latest['run_id'])

    def test_real_export_exit_is_recovered_without_rewriting_the_completed_view(self):
        original, source = self.saved()
        request = self.export_request(source)
        code = '''import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core import exporting
actual=exporting.durable_write
def crash(path,content,**kwargs):
    actual(path,content,**kwargs)
    os._exit(26)
exporting.durable_write=crash
exporting.export_analysis(sys.argv[2],json.loads(sys.argv[3]))
'''
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'), str(self.root), json.dumps(request)])
        self.assertEqual(result.returncode, 26)
        output = self.root / request['input']['output']
        before = (output.read_bytes(), output.stat().st_mtime_ns)
        pending = self.f.rows("SELECT id FROM phase_runs WHERE action='maintain' AND method='export' AND status='started'")[0]['id']
        with patch('evolve_core.exporting.durable_write', side_effect=AssertionError('Recovery must not render or write a view')):
            recovered = recover(self.root, {**self.f.identity, 'authorization': self.f.auth, 'input': {'run_id': pending}})
        self.assertEqual(recovered['outcome'], 'recovered_registration')
        self.assertEqual(before, (output.read_bytes(), output.stat().st_mtime_ns))
        with sqlite3.connect(self.root / 'evolve/history.db') as connection:
            sealed = connection.execute('SELECT status,result_json FROM phase_runs WHERE id=?', (pending,)).fetchone()
        self.assertEqual(sealed[0], 'interrupted')
        self.assertEqual(json.loads(sealed[1])['view_status'], 'written')
        self.assertEqual(current_state(self.root, original['run_id'])['analyses'][0]['current_head'], original['run_id'])

    def test_actual_alpha14_writer_cannot_change_new_protocol_data_history(self):
        self.saved()
        package = self.root / '.evolve-local/old-alpha14'
        with zipfile.ZipFile(ROOT / 'tests/fixtures/runtime-package-alpha14.zip') as archive:
            archive.extractall(package)
        candidates = list(package.rglob('runtime/evolve.py'))
        self.assertEqual(len(candidates), 1)
        database = self.root / 'evolve/history.db'
        before = database.read_bytes()
        request = self.request()
        result = subprocess.run([sys.executable, '-B', str(candidates[0]), '--project', str(self.root),
            'analyze', '--owner', 'evolve-propose', '--method', 'investigate', '--request', '-'],
            input=json.dumps(request), text=True, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'SCHEMA_VERSION')
        self.assertEqual(database.read_bytes(), before)
