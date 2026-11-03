"""A one-task short plan preserves real original behavior before writing files."""
from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.plans import propose
from evolve_core.verify import verify


class ShortPreservationTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        (self.root / 'total.py').write_text('def total(values):\n    return sum(values)\n')
        self.data = {'title': 'Refactor without changing totals',
            'plan': 'Use an explicit loop and preserve the original literal examples.',
            'completion': 'Original positive, empty and negative examples still pass.',
            'scope': ['total.py'], 'acceptance': ['Preserve positive, empty and negative totals.'],
            'required_checks': ['unit'], 'pre_refactor': True,
            'preservation_checks': ['unit'], 'preservation_inputs': ['test_total.py']}
        self.data['presentation'] = {'source': 'actual-short-fixture-plan', 'text': self.data['plan']}
        self.plan = self.propose(self.data)

    def propose(self, data):
        return propose(self.root, {**self.identity(), 'authorization': self.auth, 'input': data})

    def test_short_refactor_has_actual_before_after_proof_and_can_close(self):
        result = implement(self.root, self.apply_request(
            'def total(values):\n    result = 0\n    for value in values:\n        result += value\n    return result\n'))
        self.assertEqual(result['preservation']['status'], 'passed')
        self.assertNotEqual(result['preservation']['before']['run_id'], None)
        evidence = self.rows("SELECT kind FROM events WHERE run_id=? ORDER BY rowid", (result['run_id'],))
        kinds = [row['kind'] for row in evidence]
        self.assertLess(kinds.index('preservation_before_checked'), kinds.index('files_applied'))
        verified = verify(self.root, self.verification_request())
        self.assertEqual(verified['status'], 'passed')
        self.assertEqual(archive(self.root, self.request({'verification_id': verified['verification_id']}))['outcome'], 'archived')

    def test_short_refactor_cannot_pause_with_files_without_original_proof(self):
        request = self.apply_request()
        request['input']['pause'] = {'reason': 'Pause before checking.', 'completed': [],
            'remaining': ['Original checks.'], 'next_steps': ['Prepare original checks.']}
        before = (self.root / 'total.py').read_bytes()
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, request)
        self.assertEqual(caught.exception.code, 'PRESERVATION_REQUIRED')
        self.assertEqual((self.root / 'total.py').read_bytes(), before)

    def test_invalid_preservation_contract_is_rejected_before_recording(self):
        before = self.rows('SELECT COUNT(*) AS n FROM changes')[0]['n']
        for invalid in ({'preservation_inputs': ['total.py']}, {'preservation_checks': []},
                        {'pre_refactor': False}, {'pre_refactor': 'true'}):
            with self.subTest(invalid=invalid), self.assertRaises(EvolveError):
                self.propose({**self.data, **invalid})
        self.assertEqual(self.rows('SELECT COUNT(*) AS n FROM changes')[0]['n'], before)

    def test_short_context_is_frozen_even_without_preservation(self):
        import json
        data = {key: value for key, value in self.data.items()
                if key not in ('pre_refactor', 'preservation_checks', 'preservation_inputs')}
        planned = self.propose({**data, 'context_paths': ['test_total.py']})
        definition = json.loads(self.rows('SELECT definition_json FROM tasks WHERE id=?', (planned['task_id'],))[0]['definition_json'])
        self.assertEqual(list(definition['context']), ['test_total.py'])

    def test_changed_original_input_blocks_checks_only_continuation(self):
        request = self.apply_request('def total(values):\n    return 99\n')
        result = implement(self.root, request)
        self.assertEqual(result['preservation']['status'], 'failed')
        path = self.root / 'test_total.py'
        path.write_text(path.read_text() + '\n# changed after the original proof\n')
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, self.apply_request())
        self.assertEqual(caught.exception.code, 'CONTEXT_CHANGED')

    def test_changed_original_input_after_planning_cannot_create_a_new_before_proof(self):
        path = self.root / 'test_total.py'
        path.write_text(path.read_text() + '\n# changed after presentation\n')
        before = (self.root / 'total.py').read_bytes()
        with self.assertRaises(EvolveError) as caught:
            implement(self.root, self.apply_request())
        self.assertEqual(caught.exception.code, 'CONTEXT_CHANGED')
        self.assertEqual(caught.exception.details['context_changes'][0]['path'], 'test_total.py')
        self.assertEqual((self.root / 'total.py').read_bytes(), before)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='preservation_before_checked'")[0]['n'], 0)
