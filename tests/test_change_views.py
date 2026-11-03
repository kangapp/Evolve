"""Derived Markdown follows sealed work without replacing primary facts or edits."""
from unittest.mock import patch

from workflow_fixture import WorkflowFixture
from evolve_core.apply import implement
from evolve_core.change_views import observe
from evolve_core.exporting import export_analysis


class ChangeViewTests(WorkflowFixture):
    def summary(self):
        return self.root / 'evolve/changes' / self.plan['change_id'] / 'summary.md'

    def rebuild(self):
        return export_analysis(self.root, {**self.identity(), 'authorization': self.auth,
            'input': {'kind': 'change', 'change_id': self.plan['change_id']}})

    def test_short_plan_creates_one_readable_summary_with_exact_sealed_source(self):
        path = self.summary()
        self.assertTrue(path.is_file())
        self.assertEqual([item.name for item in path.parent.iterdir()], ['summary.md'])
        self.assertIn('Correct arithmetic total', path.read_text())
        self.assertIn('## 验收条件', path.read_text())
        view = observe(self.root, self.plan['change_id'])
        source = self.rows('SELECT result_digest FROM phase_runs WHERE id=?', (self.plan['run_id'],))[0]
        self.assertEqual(view['status'], 'ready')
        self.assertEqual(view['source']['result_digest'], source['result_digest'])
        self.assertNotIn(str(path.relative_to(self.root)), [row['path'] for row in self.rows('SELECT path FROM artifacts')])

    def test_actual_implementation_updates_summary_without_claiming_final_acceptance(self):
        result = implement(self.root, self.apply_request())
        text = self.summary().read_text()
        self.assertIn('记录状态 done', text)
        self.assertIn('implemented', text)
        self.assertIn('实施、验收和封存分别处理', text)
        self.assertEqual(observe(self.root, self.plan['change_id'])['source']['run_id'], result['run_id'])

    def test_manual_edit_is_preserved_and_primary_result_still_commits(self):
        path = self.summary()
        manual = path.read_text() + '\nUser-owned reasoning: preserve this exact edit.\n'
        path.write_text(manual)
        result = implement(self.root, self.apply_request())
        self.assertEqual(result['outcome'], 'implemented')
        self.assertEqual(path.read_text(), manual)
        self.assertEqual(observe(self.root, self.plan['change_id'])['files'][0]['status'], 'conflict')
        self.rebuild()
        self.assertEqual(path.read_text(), manual)

    def test_deleted_view_is_not_recreated_by_queries_and_explicit_rebuild_runs_no_checks(self):
        path = self.summary()
        path.unlink()
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}
        observed = observe(self.root, self.plan['change_id'])
        self.assertEqual(observed['files'][0]['status'], 'missing')
        self.assertFalse(path.exists())
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()})
        checks = self.rows("SELECT COUNT(*) n FROM events WHERE kind='check_dispatch_prepared'")[0]['n']
        result = self.rebuild()
        self.assertFalse(result['business_commands_run'])
        self.assertFalse(result['authority_changed'])
        self.assertEqual(observe(self.root, self.plan['change_id'])['status'], 'ready')
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM events WHERE kind='check_dispatch_prepared'")[0]['n'], checks)

    def test_view_io_failure_does_not_change_committed_result_or_replay_effects(self):
        request = self.apply_request()
        with patch('evolve_core.change_views.durable_write', side_effect=OSError('controlled view storage failure')):
            result = implement(self.root, request)
        self.assertEqual(result['outcome'], 'implemented')
        self.assertEqual(self.rows('SELECT state FROM tasks')[0]['state'], 'done')
        self.assertEqual(observe(self.root, self.plan['change_id'])['status'], 'pending')
        checks = self.rows('SELECT COUNT(*) n FROM evidence')[0]['n']
        self.assertEqual(implement(self.root, request), result)
        self.assertEqual(self.rows('SELECT COUNT(*) n FROM evidence')[0]['n'], checks)
        self.rebuild()
        self.assertEqual(observe(self.root, self.plan['change_id'])['status'], 'ready')

    def test_linked_view_path_does_not_redirect_a_derived_write(self):
        path = self.summary()
        path.unlink()
        other = self.root / 'human-notes.md'
        other.write_text('preserve these unrelated notes')
        path.symlink_to(other)
        result = implement(self.root, self.apply_request())
        self.assertEqual(result['outcome'], 'implemented')
        self.assertEqual(other.read_text(), 'preserve these unrelated notes')
        self.assertEqual(observe(self.root, self.plan['change_id'])['status'], 'unavailable')

    def test_old_view_is_not_reported_current_when_preparation_failed(self):
        with patch('evolve_core.change_views.render', side_effect=ValueError('controlled projection failure')):
            result = implement(self.root, self.apply_request())
        self.assertEqual(result['outcome'], 'implemented')
        observed = observe(self.root, self.plan['change_id'])
        self.assertEqual(observed['status'], 'pending')
        self.assertFalse(observed['source_is_latest_record'])

    def test_complex_work_has_readable_spec_dependency_graph_and_actual_review_records(self):
        import test_structured_execution as fixtures
        fixture = fixtures.StructuredExecutionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        folder = fixture.root / 'evolve/changes' / fixture.plan['change_id']
        self.assertIn('## 行为', (folder / 'spec.md').read_text())
        self.assertIn('```mermaid', (folder / 'tasks.md').read_text())
        self.assertIn('verification_passed', (folder / 'tasks.md').read_text())
        self.assertFalse((folder / 'verification.md').exists())
        fixture.complete_sum()
        fixture.apply('REPORT', {'report.py': fixtures.REPORT})
        fixture.verify()
        text = (folder / 'verification.md').read_text()
        self.assertIn('### 验收条件与证据', text)
        self.assertIn('not_recorded', text)
        self.assertIn('sum', text)
