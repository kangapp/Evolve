"""The new host scope and every real parent boundary work before model dispatch."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/model_daily_acceptance.py'


class DailyScopeTests(unittest.TestCase):
    def invoke(self, *args, runner=RUNNER):
        return subprocess.run([sys.executable, '-B', str(runner), '--package', str(ROOT), *args],
                              capture_output=True, text=True, timeout=15)

    def test_scope_pins_eight_files_eight_sessions_and_no_formal_approval(self):
        result = self.invoke('--preflight-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        scope = json.loads(result.stdout)['expanded_scope']
        self.assertEqual(scope['slice'], 'IMP-011')
        self.assertEqual(scope['maximum_sessions'], 8)
        self.assertEqual(len(scope['first_files']), 8)
        self.assertEqual(len(scope['readonly_paths']), 5)
        self.assertEqual(scope['business_write_paths'], ['total.py', 'report.py', 'model.sql'])
        self.assertEqual(scope['formal_decisions']['decision'], 'deferred')
        self.assertEqual(scope['formal_decisions']['approval_or_application'], 'not authorized')

    def test_absent_or_previous_learning_authorization_never_installs_or_dispatches(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'must-not-exist'
            for fields in ([], ['--authorization-text', 'IMP-010 only', '--expected-scope-digest', 'old-learning-scope']):
                result = self.invoke('--out', str(output), *fields)
                self.assertEqual(result.returncode, 2)
                self.assertIn('exact scope digest', result.stderr)
                self.assertFalse(output.exists())

    def test_frozen_alias_has_the_same_actual_scope(self):
        original = self.invoke('--preflight-only')
        self.assertEqual(original.returncode, 0, original.stderr)
        scope = json.loads(original.stdout)['expanded_scope']
        with tempfile.TemporaryDirectory() as directory:
            controller = Path(directory) / 'controller'
            for name in scope['runner_files']:
                target = controller / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, target)
            alias = Path(directory) / 'alias'
            alias.symlink_to(controller, target_is_directory=True)
            result = self.invoke('--preflight-only', runner=alias / 'scripts/model_daily_acceptance.py')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['expanded_scope']['scope_digest'], scope['scope_digest'])

    def test_all_eight_actual_parent_boundaries_and_readonly_tamper_rejection_without_models(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Path(directory)
            package = lab / 'cache'
            build = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_package.py'), '--out', str(package)],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            registered = lab / 'installed-source'
            shutil.copytree(package, registered)
            profile = lab / 'profile'
            profile.mkdir()
            (profile / 'config.toml').write_text('isolated = true\n')
            evidence = lab / 'evidence'
            evidence.mkdir()
            code = """import json,sys
from pathlib import Path
package,registered,evidence,source=map(Path,sys.argv[1:])
sys.path[:0]=[str(package/'runtime'),str(source/'scripts'),str(source/'tests')]
import evolve_core.package
from daily_cycle_fixture import DailyCycleFixture
from daily_inputs import CASES
from model_daily_checks import DailyChecks,scope_for
fixture=DailyCycleFixture()
try:
    (fixture.root/'.codex').mkdir()
    (fixture.root/'.codex/config.toml').write_text('isolated = true\\n')
    parent=DailyChecks(fixture.root,evidence,scope_for(package),package,registered)
    observations=[]
    for case in CASES:
        parent.before(case)
        if case in ('missing_check','reexport','external_verify'): getattr(fixture,case)(inject=False)
        else: getattr(fixture,case)()
        observations.append(parent.after(case))
    parent.before('external_verify')
    extra=fixture.root/'unexpected.py'
    extra.write_text('outside the eight-file scope\\n')
    try:
        parent.after('external_verify')
    except AssertionError as error:
        assert str(error).startswith('Unexpected business files:'),str(error)
    else: raise AssertionError('Extra business file was not refused')
    extra.unlink()
    parent.before('external_verify')
    with (fixture.root/'test_total.py').open('a') as stream: stream.write('\\n# changed readonly test\\n')
    try:
        parent.after('external_verify')
    except AssertionError as error:
        assert str(error)=='test_total.py',str(error)
    else: raise AssertionError('Readonly mutation was not refused')
    print(json.dumps({'model_requests_sent':False,'observations':observations,'readonly_mutation_rejected':True,'extra_business_file_rejected':True}))
finally:
    fixture.close()
"""
            result = subprocess.run([sys.executable, '-B', '-c', code, str(package), str(registered),
                                     str(evidence), str(ROOT)], capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            observed = json.loads(result.stdout)
            self.assertFalse(observed['model_requests_sent'])
            self.assertEqual(len(observed['observations']), 8)
            self.assertTrue(observed['readonly_mutation_rejected'])
            self.assertTrue(observed['extra_business_file_rejected'])
