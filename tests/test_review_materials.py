"""Review cleanup affects only known reproducible copies, retaining real history."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.exporting import export_analysis
from evolve_core.plans import propose
from evolve_core.recover import recover
from evolve_core.review_materials import clean, query
from evolve_core.verify import verify


class ReviewMaterialTests(WorkflowFixture):
    def ref(self, run_id):
        row = self.rows('SELECT result_digest FROM phase_runs WHERE id=?', (run_id,))[0]
        return {'run_id': run_id, 'result_digest': row['result_digest']}

    def request_material(self, data):
        request = self.request(data)
        request['input'] = data
        return request

    def copy(self, source):
        return export_analysis(self.root, self.request_material({'kind': 'review_copy', 'source': self.ref(source)}))

    def close_work(self):
        applied = implement(self.root, self.apply_request())
        verified = verify(self.root, self.verification_request())
        archive(self.root, self.request({'verification_id': verified['verification_id']}))
        return applied, verified

    def cleanup_request(self, paths):
        planned = clean(self.root, self.request_material({'stage': 'plan', 'paths': paths}))
        return self.request_material({'stage': 'apply', 'paths': paths, 'plan_source': self.ref(planned['run_id'])})

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def test_copy_generates_index_and_query_remains_read_only(self):
        applied = implement(self.root, self.apply_request())
        copied = self.copy(applied['run_id'])
        self.assertEqual(copied['index_status'], 'written')
        index = json.loads((self.root / '.evolve-local/review/index.json').read_text())
        self.assertEqual(index['copies'][0]['path'], copied['output'])
        before = self.snapshot()
        report = query(self.root)['materials']
        self.assertIn('work_not_closed', report['copies'][0]['retain_reasons'])
        self.assertFalse(report['cleanup_candidates'])
        self.assertEqual(self.snapshot(), before)

    def test_closed_unreferenced_copy_can_be_removed_without_mutating_source(self):
        _, verified = self.close_work()
        source = self.rows('SELECT result_json FROM phase_runs WHERE id=?', (verified['run_id'],))[0]['result_json']
        business = (self.root / 'total.py').read_bytes()
        copied = self.copy(verified['run_id'])
        request = self.cleanup_request([copied['output']])
        result = clean(self.root, request)
        self.assertEqual(result['outcome'], 'review_cleanup_completed')
        self.assertEqual(result['removed'], [copied['output']])
        self.assertFalse((self.root / copied['output']).exists())
        self.assertEqual(clean(self.root, request), result)
        self.assertEqual((self.root / 'total.py').read_bytes(), business)
        self.assertEqual(self.rows('SELECT result_json FROM phase_runs WHERE id=?', (verified['run_id'],))[0]['result_json'], source)

    def test_manual_unknown_and_linked_materials_are_retained(self):
        _, verified = self.close_work()
        copied = self.copy(verified['run_id'])
        path = self.root / copied['output']
        path.write_text('Manual review with additional reasoning.')
        unknown = self.root / '.evolve-local/review/manual.md'
        unknown.write_text('Unknown ownership must remain.')
        linked = self.root / '.evolve-local/review/source-link'
        linked.symlink_to(self.root / 'total.py')
        report = query(self.root)['materials']
        self.assertFalse(report['cleanup_candidates'])
        self.assertEqual(len(report['copies']), 3)
        for selected in (copied['output'], unknown.relative_to(self.root).as_posix(), linked.relative_to(self.root).as_posix()):
            with self.assertRaises(EvolveError) as caught:
                clean(self.root, self.request_material({'stage': 'plan', 'paths': [selected]}))
            self.assertEqual(caught.exception.code, 'REVIEW_RETAIN')
        self.assertTrue(linked.is_symlink())

    def test_change_after_plan_prevents_any_deletion(self):
        _, verified = self.close_work()
        copies = [self.copy(verified['run_id']) for _ in range(2)]
        request = self.cleanup_request([item['output'] for item in copies])
        (self.root / copies[1]['output']).write_text('Later manual observation.')
        with self.assertRaises(EvolveError):
            clean(self.root, request)
        self.assertTrue(all((self.root / item['output']).exists() for item in copies))

    def test_saved_work_reference_keeps_copy(self):
        _, verified = self.close_work()
        copied = self.copy(verified['run_id'])
        text = 'Inspect the saved review at ' + copied['output'] + ' before another repair.'
        propose(self.root, {**self.identity(), 'authorization': self.auth, 'input': {
            'title': 'Work referring to saved review', 'plan': text, 'completion': 'Inspect the original literals.',
            'scope': ['total.py'], 'required_checks': ['unit'], 'acceptance': ['Preserve original sum.'],
            'presentation': {'source': 'actual-reference-fixture', 'text': text}}})
        item = query(self.root)['materials']['copies'][0]
        self.assertIn('referenced', item['retain_reasons'])
        self.assertTrue(item['references'])

    def test_manual_relative_review_link_keeps_copy(self):
        _, verified = self.close_work()
        copied = self.copy(verified['run_id'])
        note = (self.root / copied['output']).parent.parent / 'notes.md'
        note.write_text('[Original verification](results/' + Path(copied['output']).name + ')\n')
        item = next(item for item in query(self.root)['materials']['copies'] if item['path'] == copied['output'])
        self.assertFalse(item['cleanup_eligible'])
        self.assertIn({'kind': 'project_text', 'path': note.relative_to(self.root).as_posix()}, item['references'])

    def test_unregistered_project_document_keeps_referenced_copy(self):
        _, verified = self.close_work()
        copied = self.copy(verified['run_id'])
        (self.root / 'README.md').write_text('[Verification](' + copied['output'] + ')\n')
        item = next(item for item in query(self.root)['materials']['copies'] if item['path'] == copied['output'])
        self.assertIn({'kind': 'project_text', 'path': 'README.md'}, item['references'])
        self.assertFalse(item['cleanup_eligible'])

    def test_manual_index_reference_is_not_ignored_as_runtime_bookkeeping(self):
        _, verified = self.close_work()
        copied = self.copy(verified['run_id'])
        (self.root / '.evolve-local/review/index.json').write_text('Manual note: retain ' + copied['output'])
        item = next(item for item in query(self.root)['materials']['copies'] if item['path'] == copied['output'])
        self.assertIn({'kind': 'project_text', 'path': '.evolve-local/review/index.json'}, item['references'])
        self.assertFalse(item['cleanup_eligible'])

    def test_new_reference_after_plan_prevents_deletion(self):
        _, verified = self.close_work()
        copied = self.copy(verified['run_id'])
        request = self.cleanup_request([copied['output']])
        (self.root / '.evolve-local/review/manual.md').write_text('Retain ' + copied['output'])
        with self.assertRaises(EvolveError) as caught:
            clean(self.root, request)
        self.assertEqual(caught.exception.code, 'REVIEW_RETAIN')
        self.assertTrue((self.root / copied['output']).is_file())

    def test_index_manual_edit_is_preserved_and_reported(self):
        _, verified = self.close_work()
        self.copy(verified['run_id'])
        path = self.root / '.evolve-local/review/index.json'
        path.write_text('Manual index notes.')
        copied = self.copy(verified['run_id'])
        self.assertEqual(copied['index_status'], 'manual_conflict')
        self.assertEqual(path.read_text(), 'Manual index notes.')
        self.assertTrue((self.root / copied['output']).exists())

    def test_partial_cleanup_is_terminal_and_does_not_repeat_deletion(self):
        _, verified = self.close_work()
        copies = [self.copy(verified['run_id']) for _ in range(2)]
        paths = sorted(item['output'] for item in copies)
        request = self.cleanup_request(paths)
        original = Path.unlink
        def fail_second(path, *args, **kwargs):
            if path == self.root / paths[1]:
                raise OSError('Controlled second-copy deletion failure')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_second):
            result = clean(self.root, request)
        self.assertEqual(result['outcome'], 'review_cleanup_partial')
        self.assertEqual(result['removed'], paths[:1])
        self.assertEqual(result['remaining'], paths[1:])
        self.assertEqual(clean(self.root, request), result)
        self.assertTrue((self.root / paths[1]).exists())

    def test_real_interrupted_cleanup_recovery_only_observes_original_intent(self):
        _, verified = self.close_work()
        copies = [self.copy(verified['run_id']) for _ in range(2)]
        paths = sorted(item['output'] for item in copies)
        request = self.cleanup_request(paths)
        runtime = str(Path(__file__).resolve().parents[1] / 'runtime')
        program = '''import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from evolve_core.review_materials import clean
original = Path.unlink
def stop_after_unlink(path, *args, **kwargs):
    value = original(path, *args, **kwargs)
    if str(path) == sys.argv[3]:
        os._exit(83)
    return value
Path.unlink = stop_after_unlink
clean(Path(sys.argv[2]), json.load(sys.stdin))
'''
        child = subprocess.run([sys.executable, '-B', '-c', program, runtime, str(self.root), str(self.root / paths[0])],
                               input=json.dumps(request), capture_output=True, text=True)
        self.assertEqual(child.returncode, 83, child.stderr)
        original_run = self.rows('SELECT id FROM phase_runs WHERE request_id=?', (request['request_id'],))[0]['id']
        result = recover(self.root, self.request_material({'run_id': original_run}))
        self.assertFalse(result['business_commands_run'])
        self.assertFalse((self.root / paths[0]).exists())
        self.assertTrue((self.root / paths[1]).exists())
        saved = json.loads(self.rows('SELECT result_json FROM phase_runs WHERE id=?', (original_run,))[0]['result_json'])
        self.assertFalse(saved['cleanup_replayed'])
        self.assertEqual([item['status'] for item in saved['observations']], ['absent', 'present'])
