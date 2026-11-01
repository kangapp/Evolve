"""Actual controller exits must not release ownership of orphaned checks."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest

from workflow_fixture import WorkflowFixture
from evolve_core.errors import EvolveError
from evolve_core.package import digest
from evolve_core.recover import recover
from evolve_core.reading import current_state
from evolve_core.store import now


CHILD = '''
import importlib,json,os,sys
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
app=importlib.import_module('evolve_core.apply')
original=app.check_event_sink
def interrupted(*args):
    sink=original(*args)
    def emit(kind,payload):
        sink(kind,payload)
        if kind == sys.argv[3]:
            os._exit(35)
    return emit
with patch.object(app,'check_event_sink',side_effect=interrupted):
    app.implement(Path(sys.argv[2]),json.load(sys.stdin))
'''


@unittest.skipUnless(os.name == 'posix', 'Requires real POSIX process-group observations')
class CheckLifecycleTests(WorkflowFixture):
    def crash(self, point):
        test = self.root / 'test_total.py'
        test.write_text('import time\ntime.sleep(60)\n' + test.read_text())
        request = self.apply_request()
        request['input']['observations'] = {'test_total.py': digest(test.read_bytes())}
        controller = subprocess.run([sys.executable, '-B', '-c', CHILD,
            str(Path(__file__).resolve().parents[1] / 'runtime'), str(self.root), point],
            input=json.dumps(request), text=True, capture_output=True, timeout=15)
        self.assertEqual(controller.returncode, 35, controller.stderr)
        run = self.rows('SELECT * FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]
        operation = self.rows('SELECT * FROM operations WHERE run_id=?', (run['id'],))[0]
        events = self.rows("SELECT payload_json FROM events WHERE run_id=? AND kind='check_process_started'", (run['id'],))
        if events:
            pid = json.loads(events[0]['payload_json'])['pid']
            self.addCleanup(self.stop_group, pid)
        return run, operation, events

    @staticmethod
    def stop_group(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def test_controller_exit_does_not_release_a_still_running_check(self):
        original, operation, events = self.crash('check_process_started')
        pid = json.loads(events[0]['payload_json'])['pid']
        os.killpg(pid, 0)
        observed = next(r for r in current_state(self.root)['pending_runs'] if r['id'] == original['id'])
        self.assertEqual(observed['pending_checks'][0]['pid'], pid)
        self.assertEqual(observed['pending_checks'][0]['state'], 'process_group_present')
        self.assertEqual(observed['operations'][0]['id'], operation['id'])
        before = self.rows('SELECT * FROM resource_claims')
        with self.assertRaises(EvolveError) as caught:
            recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(caught.exception.code, 'CHECK_RUNNING')
        self.assertEqual(self.rows('SELECT * FROM resource_claims'), before)
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (original['id'],))[0]['status'], 'started')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')

    def test_dispatch_without_a_saved_process_identity_remains_unknown(self):
        original, operation, events = self.crash('check_dispatch_prepared')
        self.assertEqual(events, [])
        with self.assertRaises(EvolveError) as caught:
            recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(caught.exception.code, 'CHECK_EXECUTION_UNKNOWN')
        self.assertGreater(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (original['id'],))[0]['status'], 'started')

    def observation(self, original):
        attempt = next(r for r in current_state(self.root)['pending_runs'] if r['id'] == original['id'])['pending_checks'][0]
        return {**{k: attempt[k] for k in ('execution_id', 'command_digest', 'host')},
                'outcome': 'not_started', 'observed_at': now(), 'source': 'actual-controlled-controller-exit',
                'basis': 'The controller exited immediately after saving dispatch intent, before Popen was called; no check process was created.'}

    def test_specific_observation_can_close_unknown_launch_without_claiming_a_test_result(self):
        original, operation, _ = self.crash('check_dispatch_prepared')
        observation = self.observation(original)
        request = self.request({'operation_id': operation['id'], 'check_observations': [observation]})
        result = recover(self.root, request)
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertFalse(result['business_commands_run'])
        self.assertEqual(result['checks'], 'not_run')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        event = self.rows("SELECT payload_json FROM events WHERE run_id=? AND kind='check_execution_observed'", (result['run_id'],))[0]
        payload = json.loads(event['payload_json'])
        self.assertEqual(payload['original_run_id'], original['id'])
        self.assertEqual(payload['observation'], observation)
        self.assertEqual(recover(self.root, request), result)

    def test_wrong_command_observation_does_not_release_unknown_execution(self):
        original, operation, _ = self.crash('check_dispatch_prepared')
        observation = {**self.observation(original), 'command_digest': 'wrong-command'}
        with self.assertRaises(EvolveError) as caught:
            recover(self.root, self.request({'operation_id': operation['id'], 'check_observations': [observation]}))
        self.assertEqual(caught.exception.code, 'CHECK_OBSERVATION')
        self.assertGreater(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)

    def test_observation_before_dispatch_does_not_resolve_new_unknown_effect(self):
        original, operation, _ = self.crash('check_dispatch_prepared')
        observation = {**self.observation(original), 'observed_at': '2000-01-01T00:00:00+00:00'}
        with self.assertRaises(EvolveError) as caught:
            recover(self.root, self.request({'operation_id': operation['id'], 'check_observations': [observation]}))
        self.assertEqual(caught.exception.code, 'CHECK_OBSERVATION')

    def test_statement_of_stopping_cannot_override_a_present_process_group(self):
        original, operation, _ = self.crash('check_process_started')
        observation = {**self.observation(original), 'outcome': 'stopped'}
        with self.assertRaises(EvolveError) as caught:
            recover(self.root, self.request({'operation_id': operation['id'], 'check_observations': [observation]}))
        self.assertEqual(caught.exception.code, 'CHECK_RUNNING')
