"""Behavioral acceptance and completion cutoff, including failures after green tests."""
import json
import sqlite3

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.verify import verify
from evolve_core.knowledge import propose_baseline


class AcceptanceTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        implement(self.root, self.apply_request())

    def test_verified_and_archived_results_are_bound_to_actual_cutoff(self):
        verified = verify(self.root, self.verification_request())
        self.assertEqual(verified['status'], 'passed')
        archived = archive(self.root, self.request({'verification_id': verified['verification_id']}))
        self.assertEqual(archived['outcome'], 'archived')
        self.assertEqual(archived['completion_fingerprint'], verified['fingerprint_digest'])
        self.assertEqual(archived['knowledge'], 'not_proposed')
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'archived')
        self.assertFalse((self.root / 'evolve/project.md').exists())

    def test_receipt_for_a_different_verification_cannot_support_archive(self):
        from evolve_core.package import canonical, digest
        verified = verify(self.root, self.verification_request())
        with sqlite3.connect(self.root / 'evolve/history.db') as connection:
            row = connection.execute('SELECT result_json FROM phase_runs WHERE id=?', (verified['run_id'],)).fetchone()
            changed = {**json.loads(row[0]), 'verification_id': 'different-verification'}
            connection.execute('UPDATE phase_runs SET result_json=?,result_digest=? WHERE id=?',
                (canonical(changed).decode(), digest(canonical(changed)), verified['run_id']))
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.request({'verification_id': verified['verification_id']}))
        self.assertEqual(caught.exception.code, 'VERIFICATION')
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'active')

    def test_verify_alone_does_not_change_task_state_or_business_sources(self):
        before = {p: (self.root / p).read_bytes() for p in self.auth['paths']}
        task = self.rows('SELECT state,row_version FROM tasks')[0]
        verify(self.root, self.verification_request())
        self.assertEqual(self.rows('SELECT state,row_version FROM tasks')[0], task)
        self.assertEqual({p: (self.root / p).read_bytes() for p in self.auth['paths']}, before)

    def test_executable_verification_requires_its_check_authorization(self):
        request = self.verification_request()
        request['authorization'] = {**self.auth, 'effect_kinds': ['project_records']}
        task = self.rows('SELECT * FROM tasks')[0]
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, request)
        self.assertEqual(caught.exception.code, 'AUTHORIZATION')
        self.assertEqual(self.rows('SELECT * FROM tasks')[0], task)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM verifications')[0]['n'], 0)

    def test_green_tests_do_not_override_a_required_review_finding(self):
        request = self.verification_request()
        request['input']['reviews'][0]['findings'] = [self.finding()]
        result = verify(self.root, request)
        self.assertEqual(result['checks'][0]['status'], 'passed')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'done')
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.request({'verification_id': result['verification_id']}))
        self.assertEqual(caught.exception.code, 'VERIFICATION')

    def finding(self):
        return {'id': 'missing-condition', 'path': 'total.py', 'basis': 'Fixture review regression scenario',
                'impact': 'A required behavior needs explicit reinspection', 'blocking': True}

    def test_new_empty_review_cannot_forget_an_unresolved_prior_finding(self):
        failed = self.verification_request()
        failed['input']['reviews'][0]['findings'] = [self.finding()]
        first = verify(self.root, failed)
        second = verify(self.root, self.verification_request())
        self.assertEqual(second['status'], 'failed')
        self.assertEqual(second['unresolved_prior_findings'][0]['verification_id'], first['verification_id'])

    def test_actual_same_revision_repair_can_resolve_prior_review_with_fresh_evidence(self):
        failed = self.verification_request()
        failed['input']['reviews'][0]['findings'] = [self.finding()]
        first = verify(self.root, failed)
        revision = self.plan['revision_id']
        repair = self.apply_request('def total(values):\n    # Inspected empty and negative cases.\n    return sum(values)\n')
        repair['input']['reopen_verification_id'] = first['verification_id']
        implement(self.root, repair)
        request = self.verification_request()
        request['input']['reviews'][0]['resolutions'] = [
            {'verification_id': first['verification_id'], 'finding_id': 'missing-condition',
             'basis': 'Fresh inspection of total.py and actual unit results addresses the prior observation'}]
        second = verify(self.root, request)
        self.assertEqual(second['status'], 'passed')
        self.assertEqual(self.rows('SELECT current_revision FROM changes')[0]['current_revision'], revision)
        old = self.rows('SELECT status FROM verifications WHERE id=?', (first['verification_id'],))[0]['status']
        self.assertEqual(old, 'failed')

    def test_missing_acceptance_observation_is_rejected(self):
        request = self.verification_request()
        request['input']['reviews'][0]['acceptance_results'].pop()
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, request)
        self.assertEqual(caught.exception.code, 'ACCEPTANCE')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM verifications')[0]['n'], 0)

    def test_review_against_an_old_workspace_is_rejected(self):
        request = self.verification_request()
        (self.root / 'total.py').write_text('def total(values): return sum(values) + 1\n')
        with self.assertRaises(EvolveError) as caught:
            verify(self.root, request)
        self.assertEqual(caught.exception.code, 'STALE_REVIEW')
        self.assertIn('+ 1', (self.root / 'total.py').read_text())

    def test_archive_rechecks_source_after_verification(self):
        result = verify(self.root, self.verification_request())
        (self.root / 'total.py').write_text('def total(values): return 100\n')
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.request({'verification_id': result['verification_id']}))
        self.assertEqual(caught.exception.code, 'STALE_VERIFICATION')
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'active')

    def test_archive_rechecks_untracked_business_inputs(self):
        result = verify(self.root, self.verification_request())
        (self.root / 'dependency.py').write_text('new untracked implementation input')
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.request({'verification_id': result['verification_id']}))
        self.assertEqual(caught.exception.code, 'STALE_VERIFICATION')

    def test_newest_failed_verification_prevents_using_an_older_passing_result(self):
        passed = verify(self.root, self.verification_request())
        request = self.verification_request()
        request['input']['reviews'][1]['findings'] = [self.finding()]
        self.assertEqual(verify(self.root, request)['status'], 'failed')
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.request({'verification_id': passed['verification_id']}))
        self.assertEqual(caught.exception.code, 'VERIFICATION')

    def test_same_archive_request_does_not_repeat_closure(self):
        result = verify(self.root, self.verification_request())
        request = self.request({'verification_id': result['verification_id']})
        first = archive(self.root, request)
        self.assertEqual(archive(self.root, request), first)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='change_archived'")[0]['n'], 1)

    def test_changed_check_configuration_cannot_reuse_old_passing_evidence(self):
        result = verify(self.root, self.verification_request())
        config = self.root / 'evolve/config.toml'
        config.write_text(config.read_text().replace('timeout = 10', 'timeout = 11'))
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.request({'verification_id': result['verification_id']}))
        self.assertEqual(caught.exception.code, 'CHECK_CONFIG')

    def test_display_language_and_comments_keep_prior_acceptance_without_rerunning_checks(self):
        result = verify(self.root, self.verification_request())
        previous = self.rows('SELECT * FROM verifications WHERE id=?', (result['verification_id'],))[0]
        checks = self.rows("SELECT * FROM events WHERE kind LIKE 'check_%'")
        config = self.root / 'evolve/config.toml'
        config.write_text(config.read_text().replace('language = "zh-CN"', 'language = "en"') + '\n# Display-only comment\n')
        closed = archive(self.root, self.request({'verification_id': result['verification_id']}))
        self.assertEqual(closed['outcome'], 'archived')
        self.assertEqual(self.rows('SELECT * FROM verifications WHERE id=?', (result['verification_id'],))[0], previous)
        self.assertEqual(self.rows("SELECT * FROM events WHERE kind LIKE 'check_%'"), checks)

    def test_fresh_verification_after_unrelated_document_change_preserves_completed_task(self):
        first = verify(self.root, self.verification_request())
        task = self.rows('SELECT * FROM tasks')[0]
        (self.root / 'NOTES.md').write_text('An unrelated display label changed.\n')
        with self.assertRaises(EvolveError) as caught:
            archive(self.root, self.request({'verification_id': first['verification_id']}))
        self.assertEqual(caught.exception.code, 'STALE_VERIFICATION')
        request = self.verification_request()
        request['input']['reviews'][1]['summary'] = 'Inspected the current arithmetic sources and NOTES.md; the note is display text outside the task, with no implementation change.'
        second = verify(self.root, request)
        self.assertEqual(second['status'], 'passed')
        self.assertNotEqual(second['fingerprint_digest'], first['fingerprint_digest'])
        self.assertEqual(self.rows('SELECT * FROM tasks')[0], task)
        self.assertEqual(self.rows('SELECT status FROM verifications WHERE id=?', (first['verification_id'],))[0]['status'], 'passed')
        self.assertEqual(archive(self.root, self.request({'verification_id': second['verification_id']}))['outcome'], 'archived')

    def test_project_knowledge_candidate_stays_visible_without_implicit_approval(self):
        text = '# Candidate context\n\nThis is not yet formal knowledge.\n'
        proposal = propose_baseline(self.root, self.request({'path': 'evolve/project.md', 'expected_digest': None,
                                    'content': text, 'presentation': {'source': 'fixture-candidate', 'text': text}}))
        verified = verify(self.root, self.verification_request())
        result = archive(self.root, self.request({'verification_id': verified['verification_id']}))
        self.assertEqual(result['knowledge'], 'pending_project_proposals')
        self.assertEqual(result['knowledge_scope'], 'project')
        self.assertEqual(result['pending_knowledge'][0]['id'], proposal['proposal_id'])
        self.assertFalse((self.root / 'evolve/project.md').exists())
        self.assertEqual(self.rows('SELECT state FROM knowledge_proposals')[0]['state'], 'proposed')

    def test_archived_work_can_be_reverified_without_reopening_or_rewriting_its_cutoff(self):
        first = verify(self.root, self.verification_request())
        archive(self.root, self.request({'verification_id': first['verification_id']}))
        change = self.rows('SELECT * FROM changes')[0]
        task = self.rows('SELECT * FROM tasks')[0]
        old_verification = self.rows('SELECT * FROM verifications WHERE id=?', (first['verification_id'],))[0]
        second = verify(self.root, self.verification_request())
        self.assertEqual(second['status'], 'passed')
        self.assertEqual(self.rows('SELECT * FROM changes')[0], change)
        self.assertEqual(self.rows('SELECT * FROM tasks')[0], task)
        self.assertEqual(self.rows('SELECT * FROM verifications WHERE id=?', (first['verification_id'],))[0], old_verification)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='change_archived'")[0]['n'], 1)

    def test_current_failure_after_archival_adds_evidence_and_preserves_historical_success(self):
        first = verify(self.root, self.verification_request())
        archive(self.root, self.request({'verification_id': first['verification_id']}))
        task = self.rows('SELECT * FROM tasks')[0]
        text = 'def total(values): return len(values)\n'
        (self.root / 'total.py').write_text(text)
        request = self.verification_request()
        for result in request['input']['reviews'][0]['acceptance_results']:
            result['status'] = 'failed' if result['ac_id'] != self.plan['acceptance'][1]['id'] else 'passed'
            result['basis'] = 'Current len implementation gives 2 for both nonempty examples; empty input still gives zero.'
        second = verify(self.root, request)
        self.assertEqual(second['status'], 'blocked')
        self.assertEqual(second['checks'][0]['status'], 'failed')
        self.assertEqual((self.root / 'total.py').read_text(), text)
        self.assertEqual(self.rows('SELECT * FROM tasks')[0], task)
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'], 'archived')
        self.assertEqual(self.rows('SELECT status FROM verifications WHERE id=?', (first['verification_id'],))[0]['status'], 'passed')
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, self.apply_request())
        self.assertEqual(caught.exception.code, 'TERMINAL_CHANGE')

    def test_same_sealed_result_is_checked_for_two_consumers_without_copying_the_source(self):
        from evolve_core.learning import learn
        verified = verify(self.root, self.verification_request())
        source = self.rows('SELECT * FROM phase_runs WHERE id=?', (verified['run_id'],))[0]
        archived = archive(self.root, self.request({'verification_id': verified['verification_id']}))
        retrospective = learn(self.root, self.request({'source': {'run_id': source['id'], 'result_digest': source['result_digest']},
            'checked_basis': 'Actually inspected this verification and its literal check; no new reusable finding.',
            'observer': 'actual-controlled-input-check-fixture'}), method='retro')
        checks = self.rows('SELECT * FROM input_checks WHERE target_type=? AND target_id=?', ('phase_run', source['id']))
        self.assertEqual({r['run_id'] for r in checks}, {archived['run_id'], retrospective['run_id']})
        self.assertEqual({r['purpose'] for r in checks}, {'completion_basis', 'learning_no_new_learning'})
        self.assertTrue(all(r['expected_digest'] == source['result_digest'] and json.loads(r['result'])['status'] == 'passed' for r in checks))
        self.assertEqual(self.rows('SELECT * FROM phase_runs WHERE id=?', (source['id'],))[0], source)
        self.assertEqual(len(self.rows('SELECT * FROM source_runs WHERE source_run_id=?', (source['id'],))), 2)
        self.assertTrue(all('source_body' not in json.loads(r['result']) for r in checks))

    def test_rejected_source_check_retains_the_actual_expected_digest_and_reason(self):
        from evolve_core.learning import learn
        verified = verify(self.root, self.verification_request())
        request = self.request({'source': {'run_id': verified['run_id'], 'result_digest': 'f' * 64},
            'checked_basis': 'This intentionally wrong source must be rejected without inventing a review.',
            'observer': 'actual-controlled-input-check-fixture'})
        with self.assertRaises(EvolveError) as error:
            learn(self.root, request, method='retro')
        self.assertEqual(error.exception.code, 'LEARNING_SOURCE')
        consumer = self.rows('SELECT * FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]
        self.assertEqual(consumer['status'], 'blocked')
        checks = self.rows('SELECT * FROM input_checks WHERE run_id=? AND target_id=?', (consumer['id'], verified['run_id']))
        self.assertEqual(len(checks), 1)
        observed = json.loads(checks[0]['result'])
        self.assertEqual(observed['status'], 'rejected')
        self.assertEqual(observed['code'], 'LEARNING_SOURCE')
        self.assertEqual(checks[0]['expected_digest'], 'f' * 64)
        self.assertFalse(self.rows('SELECT * FROM source_runs WHERE run_id=?', (consumer['id'],)))
        self.assertFalse(self.rows("SELECT * FROM phase_runs WHERE action='learn' AND status='completed'"))
