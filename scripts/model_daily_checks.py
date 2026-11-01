"""Eight fresh sessions compose four daily cases without formal knowledge approval."""
import hashlib
import json
import os
from pathlib import Path
import tomllib

from daily_inputs import FILES, CHECKS, GUIDE, CASES, EXTERNAL_REPORT
from model_learning_checks import LearningChecks

ROOT = Path(__file__).resolve().parents[1]
APP = 'Correct total and report'
SQL = 'Repair daily order SQL'

PROMPTS = {
    'prepare': ('使用 Evolve 接入本八文件临时项目，仅登记固定 sum、report、integration、reconcile 四检查，原定义见实际输入；'
        'integration 必须显式运行 test_total、test_report、test_integration、test_reconciliation 四模块，不用 discover 静默跳过缺失模块。'
        '本轮只实际调查 SQL 的日期／粒度／去重错误，保留 reconcile 三项真实 red 和独立字面量预期：'
        '2026-10-30=(10,2)、2026-10-31=(8,2)、2026-11-01=(0,0)。每日期每订单取最新版本后排空金额，计入负数退款；'
        '版本并列的固定输入金额相同。保存带原 criterion/check、真实资料时点、三日期 data_scope/data_context 的独立分析。'
        '呈现并保存未接受的简单方案“Repair daily order SQL”，scope 仅 model.sql，必需 reconcile，绑定真实 analysis_basis 和原症状。'
        '另呈现并保存未接受的复杂方案“Correct total and report”：scope total.py、report.py，最终必需 integration；'
        'AC key=sum 为原三个列表字面量，key=report 为报告 [2,3]→"5"、[-2,3]→"1"。'
        '唯一两 Task：SUM 仅 total.py，必需 sum、context test_total.py；REPORT 仅 report.py，必需 report，context test_report.py、test_integration.py，'
        '固定依赖同项 SUM verification_passed；分别引用 spec.test_decisions。最终检查包含尚未修复 SQL，单 Task 通过不能冒充整项成功。'
        '两方案只保存不接受／执行；不改八文件，不批准或应用正式知识。\n四检查完整定义：' + json.dumps(CHECKS, ensure_ascii=False)),
    'application': ('恢复并具体接受当前“Correct total and report”的实际复杂候选／版本／摘要，固定边界如前：'
        'SUM 原字面量 sum Task，REPORT 报告 Task 且依赖 SUM 真实 Task 验收。按原依赖先 apply 仅 total.py 恢复 sum、实际双轴验收 SUM；'
        '再 apply 仅 report.py 使 render_total 返回 str(total(values))、实际验收 REPORT。当前 SQL 尚错，整项 verify.run 应真实 failed／blocked，'
        '不改 SQL、不封存应用项，不用单 Task 绿冒充整体。'
        '另仅由 init.baseline.propose 保存附带 daily-guide.md 候选，topic=日常样例观察，acceptance key=bounds，完整正文准确为：\n' + GUIDE +
        '\n保存 exact presentation，expected_digest=null；由 sync.review 对该准确引用记录 deferred，理由为附带知识后续集中审阅。'
        '不批准、不写正文、不建立正式权威或必需文档 Task；此延期不构成实现验收阻碍。SQL 方案仍未接受、未执行。'),
    'missing_check': ('控制侧已暂时移走 test_reconciliation.py。仅验收“Correct total and report”当前整项，'
        '实际执行原 integration 四模块检查，保存缺模块环境的 failed／blocked 与具体缺口。只 verify，不创建／补写测试、源码或持久夹具，'
        '不改检查配置、AC 或范围，不修 SQL、不封存或批准知识。历史结果和现场保留。'),
    'sql_repair': ('控制侧已原字节恢复 test_reconciliation.py。恢复原 SQL 调查和未接受的“Repair daily order SQL”简单方案，'
        '核对真实 analysis_basis／原症状和当前未变输入后具体接受其实际摘要；只由 apply 修改 model.sql，'
        '按三日期／最新订单版本／先最新后排空／负数退款的原口径修复。保留五份输入及独立测试原字节。'
        '实际 reconcile、原症状后验、逐 AC 和规格／规范双轴验收通过后封存 SQL 项。'
        '不执行正式数据，不处理应用整体验收／封存、不改 total.py 或 report.py、不批准正式知识。'),
    'integration': ('本轮不改任何业务文件。恢复“Correct total and report”，核对 SUM／REPORT 的真实 Task VER 和当前 SQL 修复现场；'
        '运行原 integration 四模块，保存逐 AC 与规格／规范双轴实际整体验收；必需成果通过后封存应用项。'
        '解释实际整个工作目录包含另一个 SQL 项的修复，不伪称单 Task 隔离。附带 daily-guide.md 仍 deferred、未写正文／建立权威，'
        '不因它延期阻碍已通过实现，不覆盖原 failed／blocked，不批准任何正式知识。'),
    'lineage': ('两实现项已封存。本轮只读当前 SQL／固定订单／原独立检查，另存独立“日常有限关系”分析主题，'
        '三业务日期、范围、粒度、口径、真实来源与观察时点保持。保存 observed orders→daily_totals，依据实际 model.sql，'
        '转换为按日期取最新订单版本再排空、金额与数量汇总。生产上游和时效未调查，answer_status=partial，清晰列覆盖局限。'
        '不修代码、不创建业务 Change 或正式知识候选。随后从该保存底稿分别 maintain.export 到 '
        '.evolve-local/exports/lineage.md 与 lineage.json；Mermaid／正文／JSON 同源，导出不重查业务。'),
    'reexport': ('控制侧已移走 orders.json 与 model.sql。本轮仅从给定实际保存分析引用导出，'
        '不读／重建业务来源，不调用 status／resume／业务检查，不新增分析；直接 maintain.export 到 '
        '.evolve-local/exports/reexport.md 与 reexport.json。保留原观察时点、生成时点、partial 和覆盖局限；'
        '源文件缺失不能说当前数据已核实，不批准知识。'),
    'external_verify': ('控制侧已原字节恢复 SQL／输入，并手工把 report.py 的返回值改为 "external:" + str(total(values))。'
        '本轮只验收已封存“Correct total and report”当前现场：原 integration、原 AC 与当前双轴审查，'
        '如实保存报告格式不符的 failed／blocked，不修复或还原外部代码、不改测试／配置／判据、不重开已封存项。'
        '保留原历史通过和封存，说明当前不再适用与后续修复方案；daily-guide.md 仍仅延期候选，不批准或应用正式知识。'),
}


def scope_for(package):
    from evolve_core.package import check_package, canonical
    manifest = check_package(package)
    if (manifest['schema_version'], manifest['protocol_version']) not in ((4, 14), (4, 15), (4, 16)):
        raise ValueError('IMP-011 requires actual schema-4/protocol-14-or-15 package')
    names = ['scripts/model_daily_acceptance.py', 'scripts/model_daily_checks.py', 'scripts/daily_inputs.py',
        'scripts/model_learning_checks.py', 'scripts/learning_fixture.py', 'scripts/model_data_acceptance.py',
        'scripts/model_acceptance.py', 'scripts/verify_hosts.py']
    body = {'slice': 'IMP-011', 'host': 'codex', 'package_version': manifest['package_version'],
        'content_digest': manifest['content_digest'], 'protocol_version': manifest['protocol_version'], 'schema_version': 4,
        'first_files': FILES, 'checks': CHECKS, 'business_write_paths': ['total.py', 'report.py', 'model.sql'],
        'readonly_paths': sorted(set(FILES) - {'total.py', 'report.py', 'model.sql'}),
        'cases': PROMPTS, 'fresh_conversation_per_case': True, 'maximum_sessions': 8,
        'formal_decisions': {'candidate_only': GUIDE, 'path': 'daily-guide.md', 'decision': 'deferred',
                             'approval_or_application': 'not authorized'},
        'parent_mutations': ['Before missing_check remove test_reconciliation.py; before sql_repair restore original bytes.',
            'Before reexport remove orders.json/model.sql; before external_verify restore their exact bytes and inject fixed external report string.'],
        'model_selection': 'actual model/list isDefault; no manual replacement',
        'authorization_limits': ['Temporary project only; apply corresponding three production files; five inputs/tests read-only.',
            'No formal approval/application or final guide file; only one exact optional candidate and deferral.',
            'No Claude, personal configuration, CI/hook, nested agents, external apps, production execution, publication or deployment.',
            'Stop on permission, quota, transport or parent failure; necessary same-scope fixes/retests retain all failures.'],
        'runner_files': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}}
    return {**body, 'scope_digest': hashlib.sha256(canonical(body)).hexdigest()}


class DailyChecks(LearningChecks):
    def __init__(self, project, evidence, scope, package, registered):
        self.project, self.evidence, self.scope = project, evidence, scope
        self.package, self.registered = package, registered
        self.packages = {str(p): self.inventory(p) for p in (package, registered)}
        self.configs = {p: p.read_bytes() for p in (project / '.codex/config.toml', registered.parent / 'profile/config.toml')}
        self.old_runs, self.old_verifications = {}, {}
        self.removed = {}

    def before(self, case):
        if case == 'missing_check':
            self.removed['test_reconciliation.py'] = (self.project / 'test_reconciliation.py').read_bytes()
            (self.project / 'test_reconciliation.py').unlink()
        if case == 'sql_repair':
            (self.project / 'test_reconciliation.py').write_bytes(self.removed.pop('test_reconciliation.py'))
        if case == 'reexport':
            for name in ('orders.json', 'model.sql'):
                self.removed[name] = (self.project / name).read_bytes()
                (self.project / name).unlink()
        if case == 'external_verify':
            for name, value in self.removed.items():
                (self.project / name).write_bytes(value)
            self.removed.clear()
            (self.project / 'report.py').write_text(EXTERNAL_REPORT)
        self.before_files = {n: ((self.project / n).read_bytes(), (self.project / n).stat().st_mtime_ns)
                             if (self.project / n).exists() else None for n in FILES}
        if case != 'prepare':
            self.old_runs = {r['id']: r for r in self.rows('phase_runs')}
            self.old_verifications = {r['id']: r for r in self.rows('verifications')}

    def after(self, case):
        from evolve_core.package import check_package
        for root in (self.package, self.registered):
            assert check_package(root)['content_digest'] == self.scope['content_digest']
            assert self.inventory(root) == self.packages[str(root)]
        assert all(p.read_bytes() == data for p, data in self.configs.items())
        visible = set()
        for directory, subdirs, names in os.walk(self.project):
            subdirs[:] = [n for n in subdirs if n not in {'evolve', '.evolve-local', '.agents', '.codex', '__pycache__'}]
            visible.update((Path(directory) / n).relative_to(self.project).as_posix() for n in names)
        assert visible == set(FILES) - set(self.removed), 'Unexpected business files: ' + str(visible ^ (set(FILES) - set(self.removed)))
        allowed = {'application': {'total.py', 'report.py'}, 'sql_repair': {'model.sql'}}.get(case, set())
        for name, original in self.before_files.items():
            if name not in allowed:
                p = self.project / name
                actual = (p.read_bytes(), p.stat().st_mtime_ns) if p.exists() else None
                assert actual == original, name
        actual_checks = tomllib.loads((self.project / 'evolve/config.toml').read_text())['verification']['checks']
        assert sorted(actual_checks, key=lambda v: v['id']) == sorted(CHECKS, key=lambda v: v['id'])
        if case == 'prepare':
            self.check_config = (self.project / 'evolve/config.toml').read_bytes()
        assert (self.project / 'evolve/config.toml').read_bytes() == self.check_config
        runs = {r['id']: r for r in self.rows('phase_runs')}
        vers = {r['id']: r for r in self.rows('verifications')}
        assert all(r['package_digest'] == self.scope['content_digest'] for r in runs.values())
        assert all(runs[key] == row for key, row in self.old_runs.items())
        assert all(vers[key] == row for key, row in self.old_verifications.items())
        assert not self.rows('resource_claims') and not any(r['status'] == 'started' for r in runs.values())
        assert not self.rows('spec_applications') and not self.rows('rule_bindings')
        assert not (self.project / 'daily-guide.md').exists()
        analyses = [r for r in runs.values() if r['action'] == 'analyze' and r['status'] == 'completed']
        assert len(analyses) == (2 if case in ('lineage', 'reexport', 'external_verify') else 1)
        assert len(self.rows('changes')) == 2
        app, sql = self.change(APP), self.change(SQL)
        if case == 'prepare':
            assert not any(r['action'] == 'apply' for r in runs.values())
            for change in (app, sql):
                assert next(r for r in self.rows('plan_revisions') if r['id'] == change['current_revision'])['accepted_event_id'] is None
            assert not self.rows('knowledge_proposals')
            symptom = json.loads(analyses[0]['result_json'])['analysis']['symptom']
            assert symptom['status'] == 'reproduced' and symptom['failures'] >= 1
        else:
            proposals = self.rows('knowledge_proposals')
            assert len(proposals) == 1 and proposals[0]['state'] == 'deferred' and proposals[0]['approved_event_id'] is None
            candidate = self.rows('blobs')
            stored = next(r['content'] for r in candidate if r['digest'] == proposals[0]['candidate_digest'])
            assert stored.decode() == GUIDE
            assert self.task(APP, 'SUM')['state'] == self.task(APP, 'REPORT')['state'] == 'done'
            self.verified_task(self.task(APP, 'SUM'))
            self.verified_task(self.task(APP, 'REPORT'))
            assert app['state'] == ('archived' if case in ('integration', 'lineage', 'reexport', 'external_verify') else 'active')
            assert sql['state'] == ('archived' if case in ('sql_repair', 'integration', 'lineage', 'reexport', 'external_verify') else 'ready')
        if case in ('application', 'missing_check', 'external_verify'):
            added = [r for k, r in vers.items() if k not in self.old_verifications and r['change_id'] == app['id']
                     and json.loads(r['items_json']).get('task_id') is None]
            assert added and added[-1]['status'] in ('failed', 'blocked')
            if case == 'missing_check':
                evidence = [r for r in self.rows('evidence') if r['verification_id'] == added[-1]['id']]
                blobs = {r['digest']: r['content'] for r in self.rows('blobs')}
                assert any(b'ModuleNotFoundError' in blobs[r['content_digest']] and b'test_reconciliation' in blobs[r['content_digest']] for r in evidence)
        if case == 'integration':
            assert any(r['change_id'] == app['id'] and r['status'] == 'passed' and json.loads(r['items_json']).get('task_id') is None for r in vers.values())
        if case == 'lineage':
            relation = next(r for r in analyses if r['id'] != self.original_analysis)
            result = json.loads(relation['result_json'])
            assert result['analysis']['answer_status'] == 'partial' and result['analysis']['relationships']
            self.relation = {'run_id': relation['id'], 'result_digest': relation['result_digest']}
            self.saved_relation = result['analysis']
        if case == 'prepare':
            self.original_analysis = analyses[0]['id']
        if case in ('lineage', 'reexport'):
            prefix = 'lineage' if case == 'lineage' else 'reexport'
            output = self.project / '.evolve-local/exports'
            value = json.loads((output / (prefix + '.json')).read_text())
            assert value['analysis'] == self.saved_relation and value['source'] == self.relation
            report = (output / (prefix + '.md')).read_text()
            assert '```mermaid' in report and 'partial' in report and 'not reobserved' in report
        return {'case': case, 'business_boundary_preserved': True, 'checks_and_history_preserved': True,
                'changes': len(self.rows('changes')), 'verifications': len(vers), 'analyses': len(analyses),
                'pending_runs': 0, 'claims': 0, 'semantic_model_review': 'pending'}
