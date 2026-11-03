"""Native workflow acceptance scopes are explicit before installation or account use."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class WorkflowAcceptanceScopeTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/model_workflow_acceptance.py'),
            '--package', str(ROOT), *args], capture_output=True, text=True, timeout=15)

    def test_read_only_preflight_freezes_work_and_actual_old_update_journeys(self):
        for journey, cases in [('work', ['guide', 'plan', 'pause', 'finish', 'diagnose', 'repair']),
                               ('update', ['update_inspect', 'update_continue'])]:
            with self.subTest(journey=journey):
                result = self.invoke('--journey', journey, '--preflight-only')
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertFalse(data['model_requests_sent'])
                scope = data['expanded_scope']
                self.assertEqual(list(scope['cases']), cases)
                self.assertEqual(scope['business_write_paths'], ['calc.py'])
                self.assertEqual(scope['readonly_paths'], ['test_calc.py', 'README.md'])
                self.assertEqual(bool(scope['old_fixture_sha256']), journey == 'update')

    def test_unbound_dispatch_stops_before_creating_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'not-created'
            result = self.invoke('--journey', 'update', '--out', str(output),
                '--authorization-text', 'Unrelated prior scope', '--expected-scope-digest', 'wrong')
            self.assertEqual(result.returncode, 2)
            self.assertIn('exact scope digest', result.stderr)
            self.assertFalse(output.exists())

    def test_update_inspection_can_read_install_receipts_and_old_history_without_writes(self):
        sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'runtime')]
        import model_workflow_acceptance as runner
        with tempfile.TemporaryDirectory() as directory:
            lab = Path(directory)
            project, evidence = lab / 'business', lab / 'evidence'
            base = project / '.agents/evolve-acceptance'
            profile, registered = base / 'profile', base / 'installed-source'
            profile.mkdir(parents=True)
            evidence.mkdir()
            (profile / 'config.toml').write_text('[plugins."evolve@evolve-local"]\nenabled=false\n')
            for name, content in runner.FILES.items():
                (project / name).write_text(content)
            (project / '.evolve-local/control/requests').mkdir(parents=True)
            (project / '.evolve-local/control/requests/headless-staging.json').write_text(
                '{"purpose":"controlled host JSON request and receipt staging"}')
            built = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_package.py'),
                '--out', str(registered)], capture_output=True, text=True, timeout=20)
            self.assertEqual(built.returncode, 0, built.stderr)
            version = json.loads((registered / 'evolve-package.json').read_text())['package_version']
            cache_root = profile / 'plugins/cache/evolve-local/evolve'
            cache = cache_root / version
            shutil.copytree(registered, cache)
            checker = runner.Checks.__new__(runner.Checks)
            checker.project, checker.evidence, checker.base = project, evidence, base
            checker.package, checker.registered = cache, registered
            checker.scope = runner.scope_for(cache, 'update')
            installed = [cache]

            def native(args, *, env, cwd, log):
                # Only the native cache copy is simulated; old-package project,
                # knowledge delivery and read-only CLI calls execute for real.
                if args[2] == 'remove':
                    shutil.rmtree(installed[0])
                    result = {'removed': True}
                else:
                    observed = json.loads((registered / 'evolve-package.json').read_text())
                    installed[0] = cache_root / observed['package_version']
                    shutil.copytree(registered, installed[0])
                    result = {'installedPath': str(installed[0])}
                Path(log).write_text(json.dumps({'argv': args, 'cwd': str(cwd),
                    'exit_code': 0, 'stdout': json.dumps(result), 'stderr': ''}))
                return result

            with patch.object(runner.transport, 'shell', side_effect=native):
                checker.prepare_old_update()
            update = base / 'update'
            context = json.loads((update / 'update-context.json').read_text())
            for name in ('install-actual-old', 'install-current-update'):
                material = next(Path(p) for p in context['native_installation_receipts'] if Path(p).name == name + '.json')
                self.assertTrue(material.is_relative_to(update), 'Promised receipt is outside the model-readable update directory')
                self.assertEqual(material.read_bytes(), (evidence / (name + '.json')).read_bytes())
            bridge = Path(context['old_readonly_bridge'])
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (project / 'evolve').rglob('*') if p.is_file()}
            query = subprocess.run([sys.executable, '-B', str(bridge), 'history', '--owner', 'evolve-maintain'],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(query.returncode, 0, query.stderr)
            receipt_path = Path(json.loads(query.stdout)['receipt'])
            self.assertTrue(receipt_path.is_relative_to(project / '.evolve-local/control/requests'),
                'Read-only bridge bookkeeping must use the allowed request-staging directory')
            receipt = json.loads(receipt_path.read_text())['response']
            self.assertTrue(receipt['ok'], receipt)
            self.assertIn(context['old_digest'], bridge.read_text())
            denied = subprocess.run([sys.executable, '-B', str(bridge), 'init', '--method', 'connect', '--request', '-'],
                input='{}', capture_output=True, text=True, timeout=20)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (project / 'evolve').rglob('*') if p.is_file()}, before)
