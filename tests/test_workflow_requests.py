"""Public next steps prepare actual observations and bindings without granting effects."""
import json
import subprocess
import sys
from pathlib import Path

from workflow_fixture import WorkflowFixture
from evolve_core.connect import connect
from evolve_core.package import digest
from evolve_core.plans import propose


class WorkflowRequestTests(WorkflowFixture):
    def cli(self, action='next', data=None, *, target=None, ok=True):
        argv = [sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'runtime/evolve.py'), '--project', str(self.root), action]
        if target:
            argv.append(target)
        if data is not None:
            argv += ['--request', '-']
        result = subprocess.run(argv, input=json.dumps(data) if data is not None else None, capture_output=True, text=True, timeout=30)
        response = json.loads(result.stdout)
        self.assertEqual(response['ok'], ok, response)
        return response

    def snapshot(self):
        return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}

    def test_next_is_pure_and_prepares_the_unique_goal_without_authorization(self):
        before = self.snapshot()
        response = self.cli()
        execution = response['data']['execution']
        self.assertEqual((execution['action'], execution['method']), ('apply', 'implement'))
        self.assertEqual(execution['target'], self.plan['change_id'])
        self.assertEqual(execution['request_help']['required_input_fields'], ['files'])
        self.assertIn('request_id', execution['request_help']['automatic_fresh_bindings'])
        self.assertFalse(execution['authorization_granted'])
        self.assertTrue(execution['requires_actual_plan_acceptance'])
        self.assertEqual(self.snapshot(), before)

    def test_fresh_apply_resolves_one_active_goal_without_internal_identifiers(self):
        response = self.cli('apply', {'authorization': self.auth, 'input': {'files': self.apply_request()['input']['files']}})
        self.assertEqual(response['data']['outcome'], 'implemented')

    def test_actual_latest_acceptance_selects_archive_and_stale_acceptance_does_not(self):
        self.cli('apply', {'authorization': self.auth, 'input': self.apply_request()['input']})
        before = self.snapshot()
        review = self.cli()['data']['execution']['review_subject']
        self.assertEqual(review['required_axes'], ['spec', 'standards'])
        self.assertEqual({item['id'] for item in review['acceptance']}, {item['id'] for item in self.plan['acceptance']})
        self.assertEqual(self.snapshot(), before)
        verified = self.cli('verify', {'authorization': self.auth, 'input': self.verification_request()['input']})['data']
        next_step = self.cli()['data']['execution']
        self.assertEqual(next_step['action'], 'archive')
        self.assertEqual(next_step['request_input']['verification_id'], verified['verification_id'])
        (self.root / 'unrelated-source.txt').write_text('new real source')
        self.assertEqual(self.cli()['data']['execution']['action'], 'verify')

    def test_ambiguous_target_exposes_candidates_before_effects(self):
        text = 'A separate inspection.'
        propose(self.root, {**self.identity(), 'authorization': self.auth, 'input': {'title': 'Other goal', 'plan': text,
            'completion': 'The second outcome is checked.', 'scope': ['other.py'], 'required_checks': [],
            'acceptance': ['The outcome is checked.'], 'presentation': {'source': 'actual-other-plan', 'text': text}}})
        before = self.snapshot()
        response = self.cli('apply', {'authorization': self.auth, 'input': {'files': []}}, ok=False)
        self.assertEqual(response['error']['code'], 'TARGET')
        self.assertEqual(len(response['error']['details']['candidates']), 2)
        self.assertEqual(response['error']['request_help']['required_input_fields'], ['files'])
        self.assertEqual(self.snapshot(), before)

    def test_unrelated_missing_tool_does_not_block_the_selected_goal(self):
        data = {'checks': [{'id': 'unrelated', 'argv': ['evolve-nonexistent-unrelated-tool']}]}
        candidate = connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': data})
        connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': {**data,
            'expected_config_digest': candidate['expected_config_digest'],
            'presentation': {'source': 'exact-unrelated-config', 'text': candidate['candidate']}}})
        result = self.cli()['data']
        self.assertEqual(result['readiness']['execution_environment']['status'], 'blocked')
        self.assertEqual(result['execution']['action'], 'apply')
        self.assertEqual(result['execution']['blockers'], [])

    def test_failed_effect_receipt_retains_exact_prepared_retry_bindings(self):
        path = self.root / 'test_total.py'
        path.write_text(path.read_text() + '\nfrom pathlib import Path\nPath("side-effect.txt").write_text("observed")\n')
        data = self.apply_request()['input']
        data['observations'] = {'test_total.py': digest(path.read_bytes())}
        request = {'authorization': self.auth, 'input': data}
        failed = self.cli('apply', request, ok=False)
        self.assertEqual(failed['error']['code'], 'WORKSPACE_CHANGED')
        self.assertTrue(failed['data']['request_context']['request_id'])
        retried = {**request, **failed['data']['request_context'], 'input': {**data, **failed['data']['input_bindings']}}
        before = self.snapshot()
        result = self.cli('apply', retried)
        self.assertEqual(result['data']['outcome'], 'blocked')
        self.assertEqual(self.snapshot(), before)

    def test_formal_task_prepares_required_delivery_instead_of_business_files(self):
        text = 'Create the first formal guide through its owner.'
        self.plan = propose(self.root, {**self.identity(), 'authorization': self.auth, 'input': {
            'title': 'Formal guide', 'plan': text, 'completion': 'The guide defines the actual total.',
            'scope': ['evolve/guide.md'], 'required_checks': [], 'responsible_action': 'init',
            'acceptance': ['The guide defines the total.'], 'presentation': {'source': 'controlled-formal-plan', 'text': text}}})
        execution = self.cli(target=self.plan['change_id'])['data']['execution']
        self.assertEqual((execution['action'], execution['method']), ('init', 'baseline.propose'))
        self.assertEqual(execution['request_input']['delivery']['task_id'], self.plan['task_id'])
        self.assertEqual(execution['request_input']['delivery']['acceptance_ids'], [])
        self.assertEqual(execution['delivery_subject']['acceptance'], self.plan['acceptance'])

    def test_external_task_prepares_exact_external_branch(self):
        from external_fixture import ExternalFixture
        fixture = ExternalFixture(with_work=True)
        self.addCleanup(fixture.close)
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'runtime/evolve.py'),
            '--project', str(fixture.root), 'next'], capture_output=True, text=True, timeout=30)
        response = json.loads(result.stdout)
        self.assertTrue(response['ok'], response)
        execution = response['data']['execution']
        self.assertEqual((execution['action'], execution['method']), ('apply', 'external.execute'))
        self.assertEqual(execution['request_input']['stage'], 'prepare')
