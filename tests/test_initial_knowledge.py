"""Initial formal knowledge is approved by concrete content, independently of connection."""
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.errors import EvolveError
from evolve_core.knowledge import apply_baseline, propose_baseline
from evolve_core.recover import recover


class InitialKnowledgeTests(WorkflowFixture):
    def proposal(self, path='evolve/project.md'):
        content = '# Arithmetic fixture\n\nThe total operation adds its input values.\n'
        request = self.request({'path': path, 'content': content, 'expected_digest': None,
                                'presentation': {'text': content, 'source': 'fixture-presented-candidate'}})
        return propose_baseline(self.root, request)

    def application(self, proposal):
        request = self.request({'proposal_id': proposal['proposal_id'], 'approval': {
            'proposal_version': proposal['proposal_version'], 'candidate_digest': proposal['candidate_digest'],
            'expected_digest': proposal['expected_digest'], 'source': 'fixture-explicit-approval',
            'text': 'Approve precisely this candidate as the initial baseline'}})
        request['authorization'] = {**self.auth, 'effect_kinds': ['project_records', 'knowledge'], 'paths': [proposal['path']]}
        return request

    def test_candidate_and_generic_connection_do_not_create_formal_knowledge(self):
        result = self.proposal()
        self.assertFalse(result['applied'])
        self.assertFalse((self.root / result['path']).exists())
        self.assertEqual(self.rows('SELECT state FROM knowledge_proposals')[0]['state'], 'proposed')

    def test_exact_approval_is_applied_and_actual_version_is_recorded(self):
        proposal = self.proposal()
        result = apply_baseline(self.root, self.application(proposal))
        self.assertEqual(result['outcome'], 'baseline_applied')
        self.assertEqual(result['actual_digest'], proposal['candidate_digest'])
        artifact = self.rows("SELECT * FROM artifacts WHERE kind='knowledge'")[0]
        self.assertEqual(artifact['current_version'], result['artifact']['entity_id'])
        self.assertIsNotNone(self.rows('SELECT approved_event_id FROM knowledge_proposals')[0]['approved_event_id'])

    def test_wrong_candidate_hash_does_not_apply_or_approve(self):
        proposal = self.proposal()
        request = self.application(proposal)
        request['input']['approval']['candidate_digest'] = 'unseen content'
        with self.assertRaises(EvolveError) as caught:
            apply_baseline(self.root, request)
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_APPROVAL')
        self.assertFalse((self.root / proposal['path']).exists())
        self.assertEqual(self.rows('SELECT state FROM knowledge_proposals')[0]['state'], 'proposed')

    def test_business_authorization_does_not_approve_formal_knowledge(self):
        proposal = self.proposal()
        request = self.application(proposal)
        request['authorization'] = self.auth
        with self.assertRaises(EvolveError) as caught:
            apply_baseline(self.root, request)
        self.assertEqual(caught.exception.code, 'AUTHORIZATION')
        self.assertFalse((self.root / proposal['path']).exists())

    def test_changed_target_is_preserved_after_concrete_approval(self):
        proposal = self.proposal()
        target = self.root / proposal['path']
        target.write_text('externally created document')
        with self.assertRaises(EvolveError) as caught:
            apply_baseline(self.root, self.application(proposal))
        self.assertEqual(caught.exception.code, 'FILE_CONFLICT')
        self.assertEqual(target.read_text(), 'externally created document')

    def test_same_application_or_new_request_does_not_repeat_formal_application(self):
        proposal = self.proposal()
        request = self.application(proposal)
        first = apply_baseline(self.root, request)
        self.assertEqual(apply_baseline(self.root, request), first)
        repeated = apply_baseline(self.root, self.application(proposal))
        self.assertEqual(repeated['outcome'], 'already_applied')
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='knowledge_applied'")[0]['n'], 1)

    def test_rejected_candidate_cannot_be_applied_by_generic_authorization(self):
        proposal = self.proposal()
        import sqlite3
        connection = sqlite3.connect(self.root / 'evolve/history.db')
        connection.execute("UPDATE knowledge_proposals SET state='rejected' WHERE id=?", (proposal['proposal_id'],))
        connection.commit()
        connection.close()
        with self.assertRaises(EvolveError) as caught:
            apply_baseline(self.root, self.application(proposal))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_STATE')

    def test_interrupted_baseline_recovers_only_the_same_approved_candidate(self):
        proposal = self.proposal()
        with patch('evolve_core.knowledge.install_files', side_effect=OSError('injected knowledge installation failure')):
            with self.assertRaises(EvolveError):
                apply_baseline(self.root, self.application(proposal))
        self.assertFalse((self.root / proposal['path']).exists())
        operation = self.rows("SELECT * FROM operations WHERE effect_kind='knowledge'")[0]
        result = recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(result['outcome'], 'recovered_local')
        self.assertEqual(result['knowledge_proposal_id'], proposal['proposal_id'])
        self.assertTrue((self.root / proposal['path']).is_file())
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='knowledge_approved'")[0]['n'], 1)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='knowledge_applied'")[0]['n'], 1)
