"""Canonical file targets retain their authority and identity through directory aliases."""
import importlib
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.errors import EvolveError
from evolve_core.knowledge import apply_baseline, propose_baseline
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.recover import recover
from evolve_core.store import Store
from evolve_core.work import claim_resources, fingerprint

app = importlib.import_module('evolve_core.apply')


@unittest.skipUnless(hasattr(Path, 'symlink_to'), 'Requires directory symlinks')
class ScopeAliasTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        probe = self.root / 'symlink-probe'
        try:
            probe.symlink_to(self.root / 'evolve', target_is_directory=True)
        except OSError as error:
            self.skipTest('Native symlink creation unavailable: ' + str(error))
        probe.unlink()

    def plan_for(self, path):
        self.auth = {**self.auth, 'paths': [path]}
        text = 'Repair the explicitly selected file while preserving its actual target.'
        self.plan = propose(self.root, {**self.identity(), 'request_id': str(uuid.uuid4()), 'authorization': self.auth,
            'input': {'title': 'Repair selected target', 'plan': text, 'completion': 'Selected target is corrected.',
                      'scope': [path], 'acceptance': ['The selected file contains the intended repair.'],
                      'required_checks': [], 'presentation': {'text': text, 'source': 'controlled-alias-plan'}}})

    def directories(self):
        for name in ('source-a', 'source-b'):
            path = self.root / name
            path.mkdir()
            (path / 'total.py').write_text('def total(values):\n    return len(values)\n')
        alias = self.root / 'selected'
        try:
            alias.symlink_to(self.root / 'source-a', target_is_directory=True)
        except OSError as error:
            self.skipTest('Native symlink creation unavailable: ' + str(error))
        return alias

    def implementation(self):
        path = self.root / 'selected/total.py'
        return self.request({'accepted_plan_digest': self.plan['plan_digest'], 'files': [
            {'path': 'selected/total.py', 'expected_digest': digest(path.read_bytes()),
             'content': 'def total(values):\n    return sum(values)\n'}]})

    def test_directory_alias_cannot_make_tool_configuration_a_business_target(self):
        alias = self.root / 'records-alias'
        alias.symlink_to(self.root / 'evolve', target_is_directory=True)
        before = (self.root / 'evolve/config.toml').read_bytes()
        with self.assertRaises(EvolveError) as caught:
            self.plan_for('records-alias/config.toml')
        self.assertEqual(caught.exception.code, 'SCOPE')
        self.assertEqual((self.root / 'evolve/config.toml').read_bytes(), before)

    def test_formal_baseline_cannot_target_control_files_through_a_directory_alias(self):
        alias = self.root / 'control-alias'
        alias.symlink_to(self.root / '.evolve-local', target_is_directory=True)
        text = '# Not a formal document location\n'
        with self.assertRaises(EvolveError) as caught:
            propose_baseline(self.root, self.request({'path': 'control-alias/notes.md', 'expected_digest': None,
                'content': text, 'presentation': {'text': text, 'source': 'controlled-candidate'}}))
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_PATH')
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM knowledge_proposals')[0]['n'], 0)

    def test_a_stable_in_project_directory_alias_remains_supported(self):
        self.directories()
        self.plan_for('selected/total.py')
        result = app.implement(self.root, self.implementation())
        self.assertEqual(result['outcome'], 'implemented')
        self.assertIn('sum(values)', (self.root / 'source-a/total.py').read_text())
        self.assertIn('len(values)', (self.root / 'source-b/total.py').read_text())

    def test_target_redirection_after_prepare_cannot_write_an_identical_other_file(self):
        alias = self.directories()
        self.plan_for('selected/total.py')
        original = app.prepare_files
        def redirected(*args, **kwargs):
            journal = original(*args, **kwargs)
            alias.unlink()
            alias.symlink_to(self.root / 'source-b', target_is_directory=True)
            return journal
        with patch.object(app, 'prepare_files', side_effect=redirected), self.assertRaises(EvolveError) as caught:
            app.implement(self.root, self.implementation())
        self.assertEqual(caught.exception.code, 'FILE_TARGET_CHANGED')
        for name in ('source-a', 'source-b'):
            self.assertIn('len(values)', (self.root / name / 'total.py').read_text())
        operation = self.rows("SELECT * FROM operations WHERE effect_kind='business_files'")[0]
        with self.assertRaises(EvolveError) as caught:
            recover(self.root, self.request({'operation_id': operation['id']}))
        self.assertEqual(caught.exception.code, 'FILE_TARGET_CHANGED')
        alias.unlink()
        alias.symlink_to(self.root / 'source-a', target_is_directory=True)
        self.assertEqual(recover(self.root, self.request({'operation_id': operation['id']}))['outcome'], 'recovered_local')
        self.assertIn('sum(values)', (self.root / 'source-a/total.py').read_text())
        self.assertIn('len(values)', (self.root / 'source-b/total.py').read_text())

    def test_directory_symlink_target_changes_the_workspace_fingerprint(self):
        alias = self.directories()
        definition = {'scope': ['total.py'], 'checks_basis': [], 'required_checks': []}
        before = fingerprint(self.root, definition)
        alias.unlink()
        alias.symlink_to(self.root / 'source-b', target_is_directory=True)
        self.assertNotEqual(fingerprint(self.root, definition)['digest'], before['digest'])

    def test_project_move_does_not_allow_a_second_claim_on_the_same_canonical_file(self):
        run_id = self.rows("SELECT id FROM phase_runs WHERE action='propose'")[0]['id']
        store = Store(self.root)
        try:
            claim_resources(store, run_id, str(uuid.uuid4()), {}, None, ['total.py'], 'business_files')
        finally:
            store.close()
        destination = tempfile.TemporaryDirectory(prefix='evolve-moved-claim-')
        self.addCleanup(destination.cleanup)
        moved = Path(destination.name).resolve() / 'project'
        self.root.rename(moved)
        self.root = moved
        store = Store(self.root)
        try:
            with self.assertRaises(EvolveError) as caught:
                claim_resources(store, run_id, str(uuid.uuid4()), {}, None, ['total.py'], 'business_files')
            self.assertEqual(caught.exception.code, 'CLAIM')
            self.assertEqual(store.one('SELECT COUNT(*) FROM resource_claims')[0], 1)
        finally:
            store.close()

    def test_alias_of_registered_formal_knowledge_still_requires_its_owner(self):
        folder = self.root / 'docs'
        folder.mkdir()
        text = '# Approved project meaning\n'
        proposal = propose_baseline(self.root, self.request({'path': 'docs/CONTEXT.md', 'expected_digest': None,
            'content': text, 'presentation': {'text': text, 'source': 'controlled-context'}}))
        request = self.request({'proposal_id': proposal['proposal_id'], 'approval': {
            'proposal_version': proposal['proposal_version'], 'candidate_digest': proposal['candidate_digest'],
            'expected_digest': proposal['expected_digest'], 'source': 'controlled-specific-approval', 'text': 'Approve this exact baseline.'}})
        request['authorization'] = {**self.auth, 'effect_kinds': ['project_records', 'knowledge'], 'paths': ['docs/CONTEXT.md']}
        apply_baseline(self.root, request)
        (self.root / 'documentation').symlink_to(folder, target_is_directory=True)
        self.plan_for('documentation/CONTEXT.md')
        request = self.request({'accepted_plan_digest': self.plan['plan_digest'], 'files': [
            {'path': 'documentation/CONTEXT.md', 'expected_digest': digest(text.encode()), 'content': '# Unapproved replacement\n'}]})
        with self.assertRaises(EvolveError) as caught:
            app.implement(self.root, request)
        self.assertEqual(caught.exception.code, 'KNOWLEDGE_OWNER')
        self.assertEqual((folder / 'CONTEXT.md').read_text(), text)
