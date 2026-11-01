"""Actual same-project M2 composition; controlled observations, no model calls."""
import copy
import json
import sys
from pathlib import Path

import test_sql_workflow as sql
import test_structured_execution as app
from evolve_core.analysis import investigate
from evolve_core.connect import connect
from evolve_core.exporting import export_analysis
from evolve_core.knowledge import propose_baseline
from evolve_core.knowledge_proposals import review_candidates
from evolve_core.package import canonical, digest
from evolve_core.reading import current_state
from evolve_core.resume import resume_view
from evolve_core.store import now

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from daily_inputs import FILES, CHECKS, GUIDE, CASES, EXTERNAL_REPORT


class CombinedApplication(app.StructuredExecutionTests):
    def propose(self, data=None):
        if not hasattr(self, 'sql_check'):
            for name, content in FILES.items():
                (self.root / name).write_text(content)
            self.checks = copy.deepcopy(CHECKS)
            self.sql_check = self.checks[-1]
            request = {**self.identity(), 'authorization': self.auth, 'input': {'checks': self.checks}}
            candidate = connect(self.root, request)
            connect(self.root, {**self.identity(), 'authorization': self.auth, 'input': {'checks': self.checks,
                'expected_config_digest': candidate['expected_config_digest'],
                'presentation': {'text': candidate['candidate'], 'source': 'controlled-explicit-combined-check-setup'}}})
            self.data['spec']['constraints'].append('Final integration explicitly includes local SQL reconciliation; another unfinished Change can keep this shared check red.')
        return super().propose(data)


class DailyCycleFixture:
    def __init__(self):
        self.app = CombinedApplication('test_real_two_task_checks_reviews_and_whole_change_closure')
        self.app.setUp()
        self.root = self.app.root
        self.sql = sql.SQLWorkflowTests('test_real_sql_fix_reconciles_original_literals_and_archives_without_formal_data_execution')
        self.sql.root = self.root
        self.checks = self.app.checks
        self.sql.check = self.app.sql_check
        self.sql.auth = {**self.app.auth, 'text': 'Only repair model.sql under its original literal SQL criterion.', 'paths': ['model.sql']}
        self.sql.identity = self.app.identity()
        self.readonly = {**self.app.auth, 'effect_kinds': ['project_records'], 'paths': []}
        self.original = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.negative = {}

    def close(self):
        self.app.doCleanups()

    def prepare(self):
        self.sql.prepare()
        assert self.sql.observed['analysis']['symptom']['status'] == 'reproduced'
        assert all(r['state'] == 'todo' for r in self.app.rows('SELECT * FROM tasks'))

    def application(self):
        self.app.complete_sum()
        assert self.app.apply('REPORT', {'report.py': app.REPORT})['outcome'] == 'implemented'
        assert self.app.verify('REPORT')['status'] == 'passed'
        result = self.app.verify()
        assert result['status'] in ('failed', 'blocked')
        self.negative['broken_sql'] = result['verification_id']
        content = GUIDE
        candidate = propose_baseline(self.root, {**self.app.identity(), 'authorization': self.readonly, 'input': {
            'path': 'daily-guide.md', 'topic': '日常样例观察', 'reason': '附带文档候选，尚未批准正式基线。',
            'expected_digest': None, 'content': content,
            'acceptance': [{'key': 'bounds', 'text': '仅描述内存固定样例和时效限制。'}],
            'presentation': {'text': content, 'source': 'controlled-presented-optional-guide'}}})
        reference = {k: candidate[k] for k in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}
        review_candidates(self.root, {**self.app.identity(), 'authorization': self.readonly, 'input': {'decisions': [{
            'proposal': reference, 'decision': 'deferred', 'source': 'controlled-specific-deferral',
            'text': '本次只保存并延期该准确候选，不批准或应用。', 'reason': '附带知识不影响本次实现；后续集中审阅。'}]}})
        assert not (self.root / 'daily-guide.md').exists()
        self.proposal = candidate

    def missing_check(self, inject=True):
        target = self.root / 'test_reconciliation.py'
        saved = target.read_bytes() if inject else None
        if inject:
            target.unlink()
        try:
            result = self.app.verify()
            assert result['status'] in ('failed', 'blocked')
            self.negative['missing_check'] = result['verification_id']
        finally:
            if inject:
                target.write_bytes(saved)

    def sql_repair(self):
        applied = sql.implement(self.root, self.sql.request({'accepted_plan_digest': self.sql.plan['plan_digest'],
            'files': [{'path': 'model.sql', 'expected_digest': digest((self.root / 'model.sql').read_bytes()), 'content': sql.FIXED}]}))
        assert applied['outcome'] == 'implemented'
        assert self.sql.literal_check().returncode == 0
        checked = sql.verify(self.root, self.sql.verify_request())
        assert checked['status'] == 'passed'
        assert sql.archive(self.root, self.sql.request({'verification_id': checked['verification_id']}))['outcome'] == 'archived'

    def integration(self):
        checked = self.app.verify()
        assert checked['status'] == 'passed'
        assert self.app.close(checked)['outcome'] == 'archived'
        self.app_passed = checked['verification_id']
        assert self.app.rows('SELECT state FROM knowledge_proposals')[0]['state'] == 'deferred'
        assert not self.app.rows("SELECT * FROM artifacts WHERE kind='knowledge'")

    def lineage(self):
        original = self.app.rows("SELECT input_json FROM phase_runs WHERE action='analyze' ORDER BY rowid LIMIT 1")[0]
        request = copy.deepcopy(json.loads(original['input_json'])['request'])
        request.pop('request_id', None)
        request['authorization'] = self.readonly
        data = request['input']
        data['question'] = 'What finite relationship is visible in the repaired local daily SQL?'
        data['sources'] = [s for s in data['sources'] if s['kind'] == 'file']
        for source in data['sources']:
            source.update(expected_digest=digest((self.root / source['path']).read_bytes()), observed_at=now())
        data['analysis'].pop('symptom')
        data['analysis'].update(answer_status='partial', conclusion='Local SQL derives daily totals from fixed orders.',
            remaining_questions=['Production upstream and freshness were not observed.'],
            observations=[{'local_key': 'F1', 'statement': 'Current SQL filters date, selects latest revision before excluding nulls, and aggregates.', 'sources': ['S2']}])
        data['analysis']['relationships'][0]['transformation'] = 'Filter date; latest order revision; exclude null; aggregate amount and count.'
        observed = investigate(self.root, request)
        self.relation = {'run_id': observed['run_id'], 'result_digest': digest(canonical(observed))}
        self.saved_relation = observed['analysis']
        self.export('lineage')

    def export(self, prefix):
        for form, suffix in (('markdown', 'md'), ('json', 'json')):
            result = export_analysis(self.root, {**self.app.identity(), 'authorization': self.readonly, 'input': {
                'source': self.relation, 'output': '.evolve-local/exports/' + prefix + '.' + suffix, 'format': form}})
            assert result['business_sources_reobserved'] is False
        output = self.root / '.evolve-local/exports'
        report = (output / (prefix + '.md')).read_text()
        assert '```mermaid' in report and 'partial' in report and 'not reobserved' in report
        assert json.loads((output / (prefix + '.json')).read_text())['analysis'] == self.saved_relation

    def reexport(self, inject=True):
        saved = {n: (self.root / n).read_bytes() for n in ('orders.json', 'model.sql')} if inject else {}
        for n in saved:
            (self.root / n).unlink()
        try:
            self.export('reexport')
        finally:
            for n, data in saved.items():
                (self.root / n).write_bytes(data)

    def external_verify(self, inject=True):
        if inject:
            (self.root / 'report.py').write_text(EXTERNAL_REPORT)
        before = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        result = self.app.verify(failed_ac='report')
        assert result['status'] in ('failed', 'blocked')
        self.negative['external_report'] = result['verification_id']
        assert before == {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        assert self.app.context()[0]['state'] == 'archived'
        assert self.app.rows('SELECT status FROM verifications WHERE id=?', (self.app_passed,))[0]['status'] == 'passed'
        assert resume_view(self.root, self.app.plan['change_id'])['authorization_granted'] is False
        assert len(current_state(self.root)['analyses']) == 2
