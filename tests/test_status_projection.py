"""Public read projections expose saved work without inventing current validation."""
import json
from pathlib import Path
import subprocess
import sys

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.knowledge import apply_baseline, propose_baseline
from evolve_core.package import digest
from evolve_core.reading import current_state
from evolve_core.verify import verify


class StatusProjectionTests(WorkflowFixture):
    def files(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def history(self, *arguments):
        process = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'runtime/evolve.py'),
                                  '--project', str(self.root), 'history', *arguments],
                                 capture_output=True, text=True, timeout=15)
        return process.returncode, json.loads(process.stdout)

    def test_public_history_returns_sealed_historical_results_without_writing_or_granting_authority(self):
        implemented = implement(self.root, self.apply_request())
        verified = verify(self.root, self.verification_request())
        (self.root / 'total.py').write_text('def total(values): return 0\n')
        before = self.files()
        code, response = self.history()
        self.assertEqual(code, 0, response)
        view = response['data']['history']
        self.assertFalse(view['authorization_granted'])
        self.assertEqual({r['run_id'] for r in view['runs']}, {r['id'] for r in self.rows('SELECT id FROM phase_runs')})
        code, response = self.history(verified['run_id'])
        self.assertEqual(code, 0, response)
        self.assertEqual(len(response['data']['history']['runs']), 1)
        result = response['data']['history']['runs'][0]
        self.assertEqual(result['result']['verification_id'], verified['verification_id'])
        self.assertEqual(result['result_digest'], self.rows('SELECT result_digest FROM phase_runs WHERE id=?', (verified['run_id'],))[0]['result_digest'])
        self.assertEqual(result['applicability'], 'historical_not_revalidated')
        self.assertEqual(self.history('missing-run')[1]['error']['code'], 'TARGET')
        self.assertEqual(self.history('--request', '-')[1]['error']['code'], 'INPUT')
        self.assertEqual(self.files(), before)

    def test_public_history_rejects_tampered_sealed_results_without_repairing_them(self):
        from evolve_core.store import Store
        store = Store(self.root)
        try:
            with store.transaction():
                store.connection.execute('UPDATE phase_runs SET result_json=? WHERE id=?', ('{}', self.plan['run_id']))
        finally:
            store.close()
        before = self.files()
        code, response = self.history(self.plan['run_id'])
        self.assertEqual(code, 2, response)
        self.assertEqual(response['error']['code'], 'RUN_RESULT_INVALID')
        self.assertEqual(self.files(), before)

    def test_selected_status_exposes_actual_presented_plan_and_task_definition_without_writes(self):
        before = self.files()
        state = current_state(self.root, 'Correct arithmetic total')
        change = state['changes'][0]
        self.assertEqual(change['plan']['text'], 'Return the sum of values, including empty and negative cases.')
        self.assertFalse(change['plan']['accepted'])
        self.assertEqual(change['tasks'][0]['definition']['scope'], self.auth['paths'])
        self.assertEqual(change['tasks'][0]['definition']['acceptance'], self.plan['acceptance'])
        self.assertEqual(self.files(), before)

    def test_status_keeps_recorded_verification_distinct_from_current_applicability(self):
        implement(self.root, self.apply_request())
        verified = verify(self.root, self.verification_request())
        (self.root / 'total.py').write_text('def total(values): return 0\n')
        before = self.files()
        result = current_state(self.root, self.plan['change_id'])['changes'][0]['latest_verification']
        self.assertEqual(result['id'], verified['verification_id'])
        self.assertEqual(result['recorded_status'], 'passed')
        self.assertEqual(result['applicability'], 'unconfirmed')
        self.assertEqual(self.files(), before)

    def test_mapped_formal_document_navigation_reports_external_bytes_without_approving_them(self):
        text = '# Arithmetic context\n\nThe total is the sum.\n'
        proposal = propose_baseline(self.root, self.request({'path': 'CONTEXT.md', 'expected_digest': None,
            'content': text, 'presentation': {'source': 'fixture-context', 'text': text}}))
        request = self.request({'proposal_id': proposal['proposal_id'], 'approval': {
            'proposal_version': proposal['proposal_version'], 'candidate_digest': proposal['candidate_digest'],
            'expected_digest': proposal['expected_digest'], 'source': 'fixture-specific-approval', 'text': 'Approve this exact context.'}})
        request['authorization'] = {**self.auth, 'effect_kinds': ['project_records', 'knowledge'], 'paths': ['CONTEXT.md']}
        apply_baseline(self.root, request)
        reference = current_state(self.root)['knowledge_refs'][0]
        self.assertEqual(reference['confirmation'], 'approved_version')
        self.assertEqual(reference['registered_digest'], digest(text.encode()))
        (self.root / 'CONTEXT.md').write_text('External context, not yet approved.\n')
        before = self.files()
        reference = current_state(self.root)['knowledge_refs'][0]
        self.assertEqual(reference['path'], 'CONTEXT.md')
        self.assertEqual(reference['confirmation'], 'unconfirmed')
        self.assertNotEqual(reference['registered_digest'], reference['observed_digest'])
        self.assertEqual(self.files(), before)
