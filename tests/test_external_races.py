"""Actual competing processes admit either maintenance or external dispatch first."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from external_fixture import ExternalFixture
from evolve_core.external import execute, prepare
from evolve_core.errors import EvolveError
from evolve_core.maintenance import backup, restore
from evolve_core.package import canonical, digest


class ExternalAdmissionRaceTests(unittest.TestCase):
    def setUp(self):
        self.f = ExternalFixture()
        self.addCleanup(self.f.close)

    def candidate(self):
        candidate = prepare(self.f.root, self.f.request())
        return self.f.request({'stage': 'apply', 'candidate_ref': {'run_id': candidate['run_id'], 'result_digest': digest(canonical(candidate))},
            'approval': {'candidate_digest': candidate['candidate_digest'], 'target_digest': candidate['candidate']['target_snapshot']['digest'],
                'source': 'actual-uniform-human-authorization-specific-race-fixture', 'text': 'Only this exact isolated data candidate.'}})

    def child_at(self, module, function, seam, request):
        ready = self.f.root / '.evolve-local/control/race-ready'
        release = self.f.root / '.evolve-local/control/race-release'
        script = ('import importlib,json,sys,time\nfrom pathlib import Path\n'
            'module=importlib.import_module("evolve_core."+sys.argv[1])\n'
            'def fault(name):\n    if name==sys.argv[3]:\n        Path(sys.argv[5]).write_text("actual seam reached")\n'
            '        deadline=time.monotonic()+15\n        while not Path(sys.argv[6]).exists():\n'
            '            if time.monotonic()>deadline: raise TimeoutError("controlled release missing")\n            time.sleep(.01)\n'
            'module.fault_point=fault\nprint(json.dumps(getattr(module,sys.argv[2])(sys.argv[4],json.loads(sys.argv[7]))))\n')
        environment = {**os.environ, 'PYTHONPATH': str(ROOT / 'runtime')}
        child = subprocess.Popen([sys.executable, '-B', '-c', script, module, function, seam, str(self.f.root),
            str(ready), str(release), json.dumps(request)], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            release.write_text('release controlled seam')
            if child.poll() is None:
                try: child.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill(); child.communicate()
        self.addCleanup(cleanup)
        deadline = time.monotonic() + 5
        while not ready.exists():
            if child.poll() is not None:
                self.fail('Race child exited before seam: ' + child.communicate()[1])
            if time.monotonic() > deadline:
                self.fail('Actual controlled race seam was not reached')
            time.sleep(.01)
        return child, release

    def test_maintenance_barrier_wins_and_old_epoch_candidate_cannot_dispatch_after_swap(self):
        saved = backup(self.f.root, self.f.request({}))
        candidate = self.candidate()
        plan = restore(self.f.root, self.f.request({'stage': 'plan', 'bundle': saved['path'], 'manifest_digest': saved['manifest_digest']}))
        request = self.f.request({'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']})
        child, release = self.child_at('maintenance', 'restore', 'barrier', request)
        with self.assertRaises(EvolveError) as error:
            execute(self.f.root, candidate)
        self.assertEqual(error.exception.code, 'WRITER_ACTIVE')
        self.assertFalse(self.f.rows('SELECT operation_id FROM operation_receipts'))
        release.write_text('allow this exact maintenance')
        stdout, stderr = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 0, stderr)
        result = json.loads(stdout)
        self.assertNotEqual(result['workspace_epoch'], self.f.identity['expected_workspace_epoch'])
        with self.assertRaises(EvolveError) as error:
            execute(self.f.root, candidate)
        self.assertEqual(error.exception.code, 'WORKSPACE_EPOCH')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(10,)])
        self.assertFalse(self.f.rows('SELECT operation_id FROM operation_receipts'))

    def test_admitted_dispatch_wins_and_competing_maintenance_cannot_swap_under_it(self):
        saved = backup(self.f.root, self.f.request({}))
        request = self.candidate()
        plan = restore(self.f.root, self.f.request({'stage': 'plan', 'bundle': saved['path'], 'manifest_digest': saved['manifest_digest']}))
        child, release = self.child_at('external', 'execute', 'sender_recorded', request)
        with self.assertRaises(EvolveError) as error:
            restore(self.f.root, self.f.request({'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']}))
        self.assertEqual(error.exception.code, 'WRITER_ACTIVE')
        self.assertFalse((self.f.root / '.evolve-local/control/maintenance.json').exists())
        release.write_text('finish the single actual dispatch')
        stdout, stderr = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout)['effect_outcome'], 'succeeded')
        with self.assertRaises(EvolveError) as error:
            restore(self.f.root, self.f.request({'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']}))
        self.assertEqual(error.exception.code, 'RESTORE_CHANGED')
        self.assertEqual(self.f.rows('SELECT value FROM ledger'), [(20,)])
        self.assertEqual(self.f.rows('SELECT COUNT(*) FROM operation_receipts'), [(1,)])
