"""Apply proves implementation facts and task checks without claiming overall acceptance."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
from evolve_core.workspace import durable_write, install_files, prepare_files


class ApplyTests(WorkflowFixture):
    def test_real_failure_is_repaired_and_task_checks_do_not_claim_overall_verification(self):
        before = subprocess.run(self.checks[0]['argv'], cwd=self.root, capture_output=True)
        self.assertEqual(before.returncode, 1)
        result = implement(self.root, self.apply_request())
        self.assertEqual(result['outcome'], 'implemented')
        self.assertEqual(result['overall_verification'], 'not_run')
        self.assertEqual(result['task_checks'][0]['status'], 'passed')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'done')
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'active')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM verifications')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)

    def test_same_request_reuses_original_effects_and_evidence(self):
        request = self.apply_request()
        first = implement(self.root, request)
        before = self.rows('SELECT COUNT(*) n FROM evidence')[0]['n']
        stamp = (self.root / 'total.py').stat().st_mtime_ns
        self.assertEqual(implement(self.root, request), first)
        self.assertEqual((self.root / 'total.py').stat().st_mtime_ns, stamp)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], before)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM operations WHERE effect_kind=?', ('business_files',))[0]['n'], 1)

    def test_failure_of_task_checks_preserves_modified_source_without_marking_done(self):
        result = implement(self.root, self.apply_request('def total(values):\n    return 99\n'))
        self.assertEqual(result['outcome'], 'checks_not_passed')
        self.assertEqual(result['task_checks'][0]['status'], 'failed')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'in_progress')
        self.assertIn('99', (self.root / 'total.py').read_text())
        repaired = implement(self.root, self.apply_request())
        self.assertEqual(repaired['outcome'], 'implemented')

    def test_unapproved_source_scope_does_not_modify_files(self):
        request = self.apply_request()
        request['input']['files'][0]['path'] = 'other.py'
        request['authorization'] = {**self.auth, 'paths': self.auth['paths'] + ['other.py']}
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'SCOPE')
        self.assertFalse((self.root / 'other.py').exists())
        self.assertIn('len(values)', (self.root / 'total.py').read_text())

    def test_records_authorization_does_not_authorize_business_modification(self):
        request = self.apply_request()
        request['authorization'] = {**self.auth, 'effect_kinds': ['project_records']}
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'AUTHORIZATION')
        self.assertIn('len(values)', (self.root / 'total.py').read_text())

    def test_stale_versions_are_rejected_before_business_effects(self):
        request = self.apply_request()
        request['expected_versions']['task'] = 999
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'VERSION')
        self.assertIn('len(values)', (self.root / 'total.py').read_text())
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)

    def test_acceptance_is_bound_to_exact_presented_plan(self):
        request = self.apply_request()
        request['input']['accepted_plan_digest'] = 'another-plan'
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'PLAN_ACCEPTANCE')
        self.assertIsNone(self.rows('SELECT accepted_event_id FROM plan_revisions')[0]['accepted_event_id'])

    def test_external_edit_after_file_prepare_is_preserved_with_pending_recovery(self):
        def edited(root, journal, **kwargs):
            (root / 'total.py').write_text('external edit')
            install_files(root, journal, **kwargs)
        with patch('evolve_core.apply.install_files', side_effect=edited):
            with self.assertRaises(EvolveError) as caught:
                implement(self.root, self.apply_request())
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        self.assertEqual((self.root / 'total.py').read_text(), 'external edit')
        operation = self.rows("SELECT * FROM operations WHERE effect_kind='business_files'")[0]
        self.assertEqual(operation['state'], 'needs_recovery')
        self.assertGreater(self.rows('SELECT COUNT(*) n FROM resource_claims')[0]['n'], 0)
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE id=?', (operation['run_id'],))[0]['status'], 'started')

    def test_new_unobserved_edit_cannot_be_silently_adopted(self):
        (self.root / 'total.py').write_text('external edit')
        request = self.apply_request()
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'FILE_CONFLICT')
        self.assertEqual((self.root / 'total.py').read_text(), 'external edit')

    def test_done_task_requires_actual_failure_before_same_revision_repair(self):
        implement(self.root, self.apply_request())
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, self.apply_request())
        self.assertEqual(caught.exception.code, 'TASK_DONE')

    def test_committed_completion_is_not_rewritten_if_only_guard_receipt_fails(self):
        request = self.apply_request()
        failed_once = False
        def guard_failure(path, content, **kwargs):
            nonlocal failed_once
            rows = self.rows("SELECT status FROM phase_runs WHERE request_id=?", (request['request_id'],))
            if rows and rows[0]['status'] == 'completed' and not failed_once:
                failed_once = True
                raise OSError('injected receipt failure after commit')
            return durable_write(path, content, **kwargs)
        with patch('evolve_core.protection.durable_write', side_effect=guard_failure):
            with self.assertRaises(EvolveError) as caught:
                implement(self.root, request)
        self.assertEqual(caught.exception.code, 'NEEDS_RECOVERY')
        self.assertTrue(caught.exception.committed)
        result = implement(self.root, request)
        self.assertEqual(result['outcome'], 'implemented')
        self.assertEqual(self.rows('SELECT status FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]['status'], 'completed')

    def test_caller_cannot_expand_files_by_mutating_its_request_after_start(self):
        request = self.apply_request()
        def mutate_original(root, operation_id, candidates):
            request['input']['files'].append({'path': 'unapproved.py', 'expected_digest': None, 'content': 'outside approved scope'})
            return prepare_files(root, operation_id, candidates)
        with patch('evolve_core.apply.prepare_files', side_effect=mutate_original):
            result = implement(self.root, request)
        self.assertEqual(result['outcome'], 'implemented')
        self.assertFalse((self.root / 'unapproved.py').exists())
