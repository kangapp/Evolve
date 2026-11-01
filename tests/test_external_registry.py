"""Actual protected capsules, third-party values and real dispatch sender liveness."""
from pathlib import Path
import signal
import socket
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.errors import EvolveError
from evolve_core.external import prepare
from evolve_core import external_registry as registry
from evolve_core.package import canonical
from evolve_core.store import Store, now
from evolve_core.workspace import writer_lock


class ExternalRegistryTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)
        store = Store(self.f.root)
        self.meta = store.meta
        store.close()

    def assert_error(self, code, function, *args):
        with self.assertRaises(EvolveError) as error:
            function(*args)
        self.assertEqual(error.exception.code, code)

    def test_actual_candidate_capsule_is_immutable_and_protection_remains_minimal(self):
        prepared = prepare(self.f.root, self.f.request())
        capsule = {'operation_id': 'controlled-not-dispatched', 'project_id': self.meta['project_id'],
                   'original_epoch': self.meta['workspace_epoch'], 'candidate': prepared['candidate'],
                   'candidate_digest': prepared['candidate_digest'], 'authorization': self.f.auth}
        with writer_lock(self.f.root):
            ref = registry.save_capsule(self.f.root, capsule)
            self.assertEqual(registry.save_capsule(self.f.root, capsule), ref)
            value, before = registry.load_index(self.f.root, self.meta)
            value['pending'].append({**ref, 'operation_id': capsule['operation_id'], 'state': 'unknown',
                                     'resources': ['sqlite:temporary-external-target:ledger'],
                                     'sender': {'execution_id': 'intent-not-launched', 'command_digest': prepared['candidate_digest'],
                                         'host': socket.gethostname(), 'prepared_at': now(), 'state': 'not_started'}})
            registry.save_index(self.f.root, value, before)
            observed, _ = registry.load_index(self.f.root, self.meta)
        self.assertEqual(registry.read_capsule(self.f.root, observed['pending'][0], self.meta['project_id']), capsule)
        self.assertNotIn('candidate', observed['pending'][0])
        self.assertFalse(registry.require_senders_stopped(observed))
        changed = {**capsule, 'candidate_digest': 'changed'}
        self.assert_error('EXTERNAL_PROTECTION_CHANGED', registry.save_capsule, self.f.root, changed)
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])

    def test_capsule_paths_digest_and_index_epoch_or_third_values_do_not_get_repaired(self):
        capsule = {'operation_id': 'bounded-capsule', 'project_id': self.meta['project_id'], 'source': 'controlled reference only'}
        ref = {**registry.save_capsule(self.f.root, capsule), 'operation_id': capsule['operation_id']}
        self.assert_error('EXTERNAL_PROTECTION_UNKNOWN', registry.read_capsule, self.f.root,
            {**ref, 'capsule_path': '../outside.json'}, self.meta['project_id'])
        path = self.f.root / ref['capsule_path']
        path.write_bytes(path.read_bytes() + b' ')
        self.assert_error('EXTERNAL_PROTECTION_UNKNOWN', registry.read_capsule, self.f.root, ref, self.meta['project_id'])
        index, expected = registry.load_index(self.f.root, self.meta)
        actual_path = self.f.root / registry.INDEX
        third = canonical({**index, 'external_note': 'actual third-party edit'})
        actual_path.write_bytes(third)
        self.assert_error('EXTERNAL_PROTECTION_CHANGED', registry.save_index, self.f.root, index, expected)
        self.assertEqual(actual_path.read_bytes(), third)
        self.assert_error('EXTERNAL_PROTECTION_UNKNOWN', registry.load_index, self.f.root,
            {**self.meta, 'workspace_epoch': 'another-epoch'})

    def test_actual_sender_group_blocks_and_unknown_launch_needs_exact_stopping_evidence(self):
        prepared_at = now()
        sender = {'execution_id': 'actual-sender', 'command_digest': 'exact-command',
                  'host': socket.gethostname(), 'prepared_at': prepared_at, 'state': 'intent'}
        index = {'pending': [{'operation_id': 'bounded-sender', 'sender': sender}]}
        self.assert_error('CHECK_EXECUTION_UNKNOWN', registry.require_senders_stopped, index)
        observation = {**sender, 'outcome': 'not_started', 'source': 'actual-test-controller',
                       'basis': 'The fixture only persisted intent and did not launch any process.', 'observed_at': now()}
        self.assertEqual(registry.require_senders_stopped(index, [observation]), [observation])
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        try:
            sender.update(pid=child.pid, state='started')
            self.assert_error('CHECK_RUNNING', registry.require_senders_stopped, index)
        finally:
            os_signal = signal.SIGTERM
            if child.poll() is None:
                import os
                os.killpg(child.pid, os_signal)
            child.wait()
        self.assertFalse(registry.require_senders_stopped(index))
