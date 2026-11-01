"""Investigations preserve business bytes, provenance, partial answers and chains."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from evolve_core.analysis import investigate
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.package import digest
from evolve_core.reading import current_state
from evolve_core.recover import recover
from evolve_core.store import Store, now
from evolve_core import store as storage


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-analysis-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'total.py').write_text('def total(values):\n    return len(values)\n')
        (self.root / 'test_total.py').write_text('import unittest\nfrom total import total\nclass Values(unittest.TestCase):\n'
            '    def test_total(self):\n        self.assertEqual(total([8,3]),11)\n        self.assertEqual(total([]),0)\n')
        self.auth = {'source': 'isolated-investigation-fixture', 'text': 'Investigate and record the arithmetic symptom; do not repair.',
                     'effect_kinds': ['project_records']}
        self.identity = {}

    def connected(self):
        result = connect(self.root, {'request_id': 'connect', 'authorization': self.auth, 'input': {}})
        self.identity = {'project_id': result['project_id'], 'expected_workspace_epoch': result['workspace_epoch']}

    def payload(self, *, record=True):
        return {**self.identity, 'request_id': str(uuid.uuid4()),
            'authorization': self.auth if record else {**self.auth, 'effect_kinds': ['read_only']},
            'input': {'question': 'Why is the total 2 instead of 11?', 'scope': ['total.py', 'test_total.py'],
                'business_effect': 'read_only', 'record_intent': 'record' if record else 'answer_only',
                'sources': [{'id': 'S1', 'kind': 'file', 'path': 'total.py',
                             'expected_digest': digest((self.root / 'total.py').read_bytes()),
                             'observer': 'fixture-file-observer', 'observed_at': now(), 'limitations': []},
                            {'id': 'S2', 'kind': 'file', 'path': 'test_total.py',
                             'expected_digest': digest((self.root / 'test_total.py').read_bytes()),
                             'observer': 'fixture-file-observer', 'observed_at': now(), 'limitations': []}],
                'analysis': {'observations': [{'local_key': 'F1', 'statement': 'The function calls len; the independent test expects eleven.',
                                              'sources': ['S1', 'S2']}],
                             'hypotheses': [{'local_key': 'H1', 'statement': 'Counting instead of summing explains the selected example.',
                                             'status': 'supported', 'observations': ['F1'], 'basis': 'Direct inspection of the one-line function and the literal test expectation.'}],
                             'answer_status': 'partial', 'conclusion': 'The selected code counts items; no actual execution has been observed yet.',
                             'coverage': ['The two supplied source files'], 'limitations': ['No runtime reproduction in this observation.'],
                             'remaining_questions': ['Run the existing test in the authorized environment.'], 'next_steps': ['Propose a repair only if requested.']}}}

    def rows(self, sql):
        c = sqlite3.connect(self.root / 'evolve/history.db')
        c.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in c.execute(sql)]
        finally:
            c.close()

    def test_answer_only_is_a_real_read_only_query_without_initialization(self):
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        result = investigate(self.root, self.payload(record=False))
        self.assertFalse(result['committed'])
        self.assertIsNone(result['run_id'])
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()})
        self.assertFalse((self.root / 'evolve').exists())

    def test_recorded_investigation_has_no_business_change_and_completed_does_not_mean_answered(self):
        self.connected()
        request = self.payload()
        before = [(self.root / p).read_bytes() for p in ('total.py', 'test_total.py', 'evolve/config.toml')]
        result = investigate(self.root, request)
        self.assertEqual(result['analysis']['answer_status'], 'partial')
        self.assertEqual(self.rows("SELECT status FROM phase_runs WHERE action='analyze'")[0]['status'], 'completed')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM changes')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM tasks')[0]['n'], 0)
        self.assertEqual(before, [(self.root / p).read_bytes() for p in ('total.py', 'test_total.py', 'evolve/config.toml')])
        evidence = self.rows("SELECT * FROM evidence WHERE subject_kind='analysis'")
        self.assertEqual(evidence[0]['observer'], 'fixture-file-observer')
        self.assertEqual(evidence[0]['observed_at'], request['input']['sources'][0]['observed_at'])
        self.assertFalse(result['business_commands_run'])

    def test_retry_returns_original_answer_even_after_the_observed_file_changes(self):
        self.connected()
        request = self.payload()
        first = investigate(self.root, request)
        (self.root / 'total.py').write_text('unrelated later user content')
        self.assertEqual(investigate(self.root, request), first)
        self.assertEqual(len(self.rows("SELECT id FROM phase_runs WHERE action='analyze'")), 1)

    def test_changed_source_is_not_saved_as_if_it_were_the_supplied_observation(self):
        self.connected()
        request = self.payload()
        (self.root / 'total.py').write_text('later third-party edit')
        with self.assertRaises(EvolveError) as caught:
            investigate(self.root, request)
        self.assertEqual(caught.exception.code, 'ANALYSIS_SOURCE_CHANGED')
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM phase_runs WHERE action='analyze'")[0]['n'], 0)

    def test_continuation_preserves_old_result_and_rejects_an_old_head(self):
        self.connected()
        original = self.payload()
        first = investigate(self.root, original)
        row = self.rows("SELECT * FROM phase_runs WHERE action='analyze'")[0]
        request = self.payload()
        request['input']['previous'] = {'run_id': first['run_id'], 'result_digest': row['result_digest']}
        second = investigate(self.root, request)
        self.assertEqual(second['previous']['run_id'], first['run_id'])
        self.assertEqual(self.rows("SELECT result_json FROM phase_runs WHERE id='" + first['run_id'] + "'")[0]['result_json'], row['result_json'])
        self.assertEqual(investigate(self.root, original), first)
        with self.assertRaises(EvolveError) as caught:
            investigate(self.root, {**request, 'request_id': str(uuid.uuid4())})
        self.assertEqual(caught.exception.code, 'ANALYSIS_HEAD')
        self.assertEqual(len(self.rows('SELECT * FROM source_runs')), 1)

    def test_current_report_folds_the_chain_and_history_keeps_later_correction_visible(self):
        self.connected()
        first = investigate(self.root, self.payload())
        original = self.rows("SELECT * FROM phase_runs WHERE action='analyze'")[0]
        request = self.payload()
        ref = {'run_id': first['run_id'], 'result_digest': original['result_digest']}
        request['input']['previous'] = ref
        request['input']['analysis']['hypotheses'][0].update(
            statement='The earlier causal inference needs a runtime observation.', status='unconfirmed',
            basis='Only file inspection is available; no execution was observed.', corrects=[{**ref, 'local_key': 'H1'}])
        request['input']['analysis']['conclusion'] = 'Causal confirmation remains unavailable.'
        second = investigate(self.root, request)
        before = {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.root.rglob('*') if p.is_file()}
        current = current_state(self.root)['analyses']
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['run_id'], second['run_id'])
        self.assertFalse(current[0]['details_loaded'])
        history = current_state(self.root, first['run_id'])['analyses'][0]
        self.assertEqual(history['analysis'], first['analysis'])
        self.assertEqual(history['current_head'], second['run_id'])
        self.assertEqual(history['current_corrections'][0]['corrects'][0]['local_key'], 'H1')
        self.assertEqual(current_state(self.root, request['input']['question'])['analyses'][0]['run_id'], second['run_id'])
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                                 for p in self.root.rglob('*') if p.is_file()})
        third_request = self.payload()
        second_row = next(r for r in self.rows("SELECT * FROM phase_runs WHERE action='analyze'") if r['id'] == second['run_id'])
        third_request['input']['previous'] = {'run_id': second['run_id'], 'result_digest': second_row['result_digest']}
        third = investigate(self.root, third_request)
        history = current_state(self.root, first['run_id'])['analyses'][0]
        self.assertEqual(history['current_head'], third['run_id'])
        self.assertEqual(history['current_corrections'][0]['source_run_id'], second['run_id'])

    def test_external_tampering_does_not_turn_an_old_result_into_a_current_fact(self):
        self.connected()
        investigate(self.root, self.payload())
        connection = sqlite3.connect(self.root / 'evolve/history.db')
        connection.execute("UPDATE phase_runs SET result_json=? WHERE action='analyze'", ('{"analysis":{"conclusion":"tampered certainty"}}',))
        connection.commit()
        connection.close()
        with self.assertRaises(EvolveError) as caught:
            current_state(self.root)
        self.assertEqual(caught.exception.code, 'ANALYSIS_RECORD_INVALID')

    def test_old_protocol_writer_cannot_ignore_new_required_diagnostic_task_semantics(self):
        self.connected()
        with patch.object(storage, 'PROTOCOL_VERSION', 1), self.assertRaises(EvolveError) as caught:
            writer = Store(self.root)
            writer.close()
        self.assertEqual(caught.exception.code, 'SCHEMA_VERSION')

    def test_a_correction_cannot_invent_a_prior_finding(self):
        self.connected()
        first = investigate(self.root, self.payload())
        original = self.rows("SELECT * FROM phase_runs WHERE action='analyze'")[0]
        request = self.payload()
        request['input']['analysis']['observations'][0]['corrects'] = [
            {'run_id': first['run_id'], 'result_digest': original['result_digest'], 'local_key': 'F999'}]
        with self.assertRaises(EvolveError) as caught:
            investigate(self.root, request)
        self.assertEqual(caught.exception.code, 'ANALYSIS_REFERENCE')

    def test_equal_questions_in_different_topics_require_a_stable_target(self):
        self.connected()
        first = investigate(self.root, self.payload())
        investigate(self.root, self.payload())
        self.assertEqual(len(current_state(self.root)['analyses']), 2)
        with self.assertRaises(EvolveError) as caught:
            current_state(self.root, self.payload()['input']['question'])
        self.assertEqual(caught.exception.code, 'TARGET')
        self.assertEqual(current_state(self.root, first['run_id'])['analyses'][0]['run_id'], first['run_id'])

    def test_two_real_processes_cannot_branch_the_same_observed_head(self):
        self.connected()
        first = investigate(self.root, self.payload())
        row = self.rows("SELECT * FROM phase_runs WHERE action='analyze'")[0]
        command = [sys.executable, '-B', str(ROOT / 'runtime/evolve.py'), '--project', str(self.root),
                   'analyze', '--request', '-']
        processes = []
        for _ in range(2):
            request = self.payload()
            request['input']['previous'] = {'run_id': first['run_id'], 'result_digest': row['result_digest']}
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            process.stdin.write(json.dumps(request))
            process.stdin.close()
            process.stdin = None
            processes.append(process)
        output = [process.communicate(timeout=15) for process in processes]
        self.assertEqual(sum(process.returncode == 0 for process in processes), 1, output)
        self.assertEqual(len(self.rows("SELECT * FROM source_runs WHERE purpose='analysis_previous'")), 1)

    def test_public_answer_only_request_does_not_require_a_database_or_create_record_facilities(self):
        request = self.payload(record=False)
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'runtime/evolve.py'), '--project', str(self.root),
                                 'analyze', '--request', '-'], input=json.dumps(request), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['data']['outcome'], 'answered_without_record')
        self.assertFalse((self.root / '.evolve-local').exists())

    def test_claims_cannot_refer_to_missing_sources_or_facts(self):
        self.connected()
        for field in ('observations', 'hypotheses'):
            request = self.payload()
            key = 'sources' if field == 'observations' else 'observations'
            request['input']['analysis'][field][0][key] = ['missing-reference']
            with self.assertRaises(EvolveError) as caught:
                investigate(self.root, request)
            self.assertEqual(caught.exception.code, 'ANALYSIS')

    def test_historical_external_observation_does_not_invent_time_or_self_execution(self):
        self.connected()
        request = self.payload()
        source = {'id': 'S3', 'kind': 'observation', 'observer': 'external-maintainer', 'observed_at': None,
                  'object': 'arithmetic example', 'version': None, 'method': 'reported historical unittest output',
                  'content': 'AssertionError: 2 != 11', 'limitations': ['Original date and exact checkout are unknown; this agent did not run it.']}
        request['input']['sources'].append(source)
        result = investigate(self.root, request)
        self.assertIsNone(result['sources'][-1]['observed_at'])
        evidence = self.rows("SELECT * FROM evidence WHERE observer='external-maintainer'")[0]
        self.assertEqual(evidence['observed_at'], 'unknown')
        self.assertTrue(json.loads(evidence['limitations'])['observation_time_unknown'])

    def test_file_evidence_outside_scope_is_rejected(self):
        self.connected()
        request = self.payload()
        request['input']['scope'] = ['total.py']
        with self.assertRaises(EvolveError) as caught:
            investigate(self.root, request)
        self.assertEqual(caught.exception.code, 'ANALYSIS_SCOPE')

    def test_zero_observed_failures_cannot_be_promoted_to_reproduced(self):
        self.connected()
        request = self.payload()
        request['input']['analysis']['symptom'] = {'criterion': {'method': 'Existing unittest example',
            'environment': 'isolated Python fixture', 'side_effects': 'No business writes', 'input': [8, 3],
            'expected': 11, 'expected_source': 'S2'}, 'status': 'reproduced', 'attempts': 0, 'failures': 0,
            'sources': ['S1'], 'limitations': []}
        with self.assertRaises(EvolveError) as caught:
            investigate(self.root, request)
        self.assertEqual(caught.exception.code, 'SYMPTOM')
        symptom = request['input']['analysis']['symptom']
        symptom.update(status='not_reproduced', attempts=1, intermittent=True, trigger='Unknown trigger',
                       window='Single controlled observation', limitations=['One absence is not proof of elimination.'])
        observed = subprocess.run([sys.executable, '-B', '-c', 'from total import total; print(total([]))'],
                                  cwd=self.root, capture_output=True, text=True, check=True)
        self.assertEqual(observed.stdout.strip(), '0')
        request['input']['sources'].append({'id': 'S3', 'kind': 'observation', 'observer': 'actual-fixture-process',
            'observed_at': now(), 'object': 'total([])', 'version': digest((self.root / 'total.py').read_bytes()),
            'method': 'python -B -c from total import total; print(total([]))', 'content': observed.stdout, 'limitations': []})
        symptom['criterion'].update(input=[], expected=0, method='Invoke total([]) in a clean Python process')
        symptom['sources'] = ['S3']
        result = investigate(self.root, request)
        self.assertEqual(result['analysis']['answer_status'], 'partial')
        self.assertEqual(result['analysis']['symptom']['failures'], 0)

    def test_record_failure_reports_incomplete_and_keeps_saved_input_instead_of_inventing_success(self):
        self.connected()
        with patch.object(Store, 'finish', side_effect=OSError('injected full disk')), self.assertRaises(EvolveError) as caught:
            investigate(self.root, self.payload())
        self.assertEqual(caught.exception.code, 'ANALYSIS_INCOMPLETE')
        run = self.rows("SELECT * FROM phase_runs WHERE action='analyze'")[0]
        self.assertEqual(run['status'], 'started')
        self.assertIsNone(run['result_json'])
        self.assertEqual(json.loads(run['input_json'])['request']['input']['question'], 'Why is the total 2 instead of 11?')
        self.assertEqual(current_state(self.root)['pending_runs'][0]['id'], run['id'])

    def test_only_the_still_active_parent_execution_can_supply_phase_context(self):
        self.connected()
        parent = self.payload()
        store = Store(self.root)
        try:
            run_id, _ = store.start(parent, action='analyze', method='investigate', owner='evolve-propose')
            row = store.one('SELECT * FROM phase_runs WHERE id=?', (run_id,))
            request = self.payload()
            request['input']['parent'] = {'run_id': run_id, 'input_digest': row['input_digest'],
                                          'execution_instance': json.loads(row['execution_instance'])}
            investigated = investigate(self.root, request)
            self.assertEqual(investigated['parent']['run_id'], run_id)
            checks = [r for r in self.rows('SELECT * FROM input_checks')
                      if r['run_id'] == investigated['run_id'] and r['purpose'] == 'analysis_parent']
            self.assertEqual(len(checks), 1)
            self.assertEqual(checks[0]['target_id'], run_id)
            self.assertEqual(checks[0]['expected_digest'], row['input_digest'])
            self.assertEqual(json.loads(checks[0]['result'])['status'], 'passed')
            revoked = {**request, 'request_id': str(uuid.uuid4())}
            with store.transaction():
                store.event(run_id, 'authorization_revoked', {'request_id': parent['request_id']})
            with self.assertRaises(EvolveError) as caught:
                investigate(self.root, revoked)
            self.assertEqual(caught.exception.code, 'AUTHORIZATION')
            store.finish(run_id, {'outcome': 'partial', 'committed': True})
            with self.assertRaises(EvolveError) as caught:
                investigate(self.root, {**request, 'request_id': str(uuid.uuid4())})
            self.assertEqual(caught.exception.code, 'ANALYSIS_PARENT')
        finally:
            store.close()

    def test_active_parent_input_bytes_must_match_the_observed_input_digest(self):
        from evolve_core.analysis import check_parent
        self.connected()
        parent = self.payload()
        store = Store(self.root)
        try:
            run_id, _ = store.start(parent, action='analyze', method='investigate', owner='evolve-propose')
            row = store.one('SELECT * FROM phase_runs WHERE id=?', (run_id,))
            reference = {'run_id': run_id, 'input_digest': row['input_digest'],
                         'execution_instance': json.loads(row['execution_instance'])}
            changed = json.loads(row['input_json'])
            changed['request']['input']['scope'] = ['outside-original-context.py']
            with store.transaction() as connection:
                connection.execute('UPDATE phase_runs SET input_json=? WHERE id=?', (json.dumps(changed), run_id))
            with self.assertRaises(EvolveError) as error:
                check_parent(store, reference, ['outside-original-context.py'])
            self.assertEqual(error.exception.code, 'ANALYSIS_PARENT')
        finally:
            store.close()

    def test_real_controller_exit_keeps_analysis_input_and_recovery_does_not_invent_a_conclusion(self):
        self.connected()
        request = self.payload()
        child = '''import os,json,sys
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
from evolve_core.store import Store
from evolve_core.analysis import investigate
with patch.object(Store, 'finish', side_effect=lambda *a,**k:os._exit(39)):
    investigate(Path(sys.argv[2]),json.load(sys.stdin))
'''
        result = subprocess.run([sys.executable, '-B', '-c', child, str(ROOT / 'runtime'), str(self.root)],
                                input=json.dumps(request), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 39, result.stderr)
        run = self.rows("SELECT * FROM phase_runs WHERE action='analyze'")[0]
        recovery = recover(self.root, {**self.identity, 'request_id': 'recover-analysis', 'authorization': self.auth,
                                      'input': {'run_id': run['id']}})
        self.assertFalse(recovery['business_commands_run'])
        current = self.rows("SELECT * FROM phase_runs WHERE action='analyze'")[0]
        self.assertEqual(current['status'], 'interrupted')
        self.assertNotIn('analysis', json.loads(current['result_json']))
        view = current_state(self.root, run['id'])['analyses'][0]
        self.assertIsNone(view['analysis'])
        self.assertFalse(view['draft_is_completed_answer'])
        self.assertEqual(view['unfinished_input']['question'], request['input']['question'])
        self.assertEqual(len(view['retained_evidence']), 2)
        next_request = self.payload()
        next_request['input']['previous'] = {'run_id': run['id'], 'result_digest': current['result_digest']}
        self.assertEqual(investigate(self.root, next_request)['outcome'], 'analyzed')
