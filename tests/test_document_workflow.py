"""A text-only correction has content evidence and no invented executable check."""
import json
import uuid

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.verify import verify


class DocumentWorkflowTests(WorkflowFixture):
    def test_typo_correction_closes_with_actual_content_inspection_and_no_code_test_claim(self):
        path = self.root / 'README.md'
        path.write_text('# Arithmetci\n')
        self.auth = {'source': 'controlled-document-fixture', 'text': 'Correct only the heading typo in README.md and inspect the resulting text.',
                     'effect_kinds': ['project_records', 'business_files'], 'paths': ['README.md']}
        text = 'Correct Arithmetci to Arithmetic in the README heading; retain the document structure.'
        self.plan = propose(self.root, {**self.identity(), 'request_id': str(uuid.uuid4()), 'authorization': self.auth,
            'input': {'title': 'Correct documentation heading', 'plan': text, 'completion': 'The heading spells Arithmetic.',
                      'scope': ['README.md'], 'acceptance': ['The heading is exactly # Arithmetic.'], 'required_checks': [],
                      'presentation': {'text': text, 'source': 'controlled-document-plan'}}})
        implemented = implement(self.root, self.request({'accepted_plan_digest': self.plan['plan_digest'], 'files': [
            {'path': 'README.md', 'expected_digest': digest(path.read_bytes()), 'content': '# Arithmetic\n'}]}))
        self.assertEqual(implemented['task_checks'], [])
        self.assertEqual(path.read_text(), '# Arithmetic\n')
        request = self.verification_request()
        for review in request['input']['reviews']:
            review['observer'] = 'controlled-document-content-observer'
            review['summary'] = 'Read README.md and compared the heading with the stated spelling and existing Markdown structure; content inspection, no code review.'
            if review['axis'] == 'spec':
                for item in review['acceptance_results']:
                    item['basis'] = 'Actual README.md bytes are # Arithmetic followed by a newline.'
        verified = verify(self.root, request)
        self.assertEqual(verified['status'], 'passed')
        self.assertEqual(verified['checks'], [])
        self.assertEqual(archive(self.root, self.request({'verification_id': verified['verification_id']}))['outcome'], 'archived')
        checks = self.rows("SELECT * FROM evidence WHERE source_run_id=? AND method='argv-check'", (verified['run_id'],))
        self.assertEqual(checks, [])
        recorded = self.rows('SELECT items_json FROM verifications WHERE id=?', (verified['verification_id'],))[0]
        self.assertIn('content inspection', json.loads(recorded['items_json'])['reviews'][0]['summary'])
