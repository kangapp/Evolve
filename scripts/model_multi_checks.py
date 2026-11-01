"""Concrete IMP-009 scope and parent checks; no model transport here."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = '# 术语\n\n总额：计数。\n\n审查约定：尚无。\n'
RULE = '核对整数求和时使用独立字面量样例，注明观察范围。'
FINAL = BASE.replace('总额：计数。', '总额：数值之和。').replace('审查约定：尚无。', '审查约定：' + RULE)
FILES = {'total.py': 'def total(values):\n    return len(values)\n',
    'report.py': 'def render_total(values):\n    return "pending"\n', 'terms.md': BASE,
    'test_total.py': ('import unittest\nfrom total import total\nclass Totals(unittest.TestCase):\n'
        '    def test_literals(self):\n        self.assertEqual(total([2,3]),5)\n'
        '        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n'),
    'test_report.py': ('import unittest\nfrom report import render_total\nclass Reports(unittest.TestCase):\n'
        '    def test_literals(self):\n        self.assertEqual(render_total([2,3]),"5")\n'
        '        self.assertEqual(render_total([]),"0")\n        self.assertEqual(render_total([-2,3]),"1")\n'),
    'test_integration.py': ('import unittest\nfrom report import render_total\nclass Integration(unittest.TestCase):\n'
        '    def test_generator(self): self.assertEqual(render_total(iter([5,-2])),"3")\n')}
PROMPTS = {
    'producer_a': ('使用 Evolve 接入当前临时项目，登记 sum、report、integration 检查，命令分别为 '
        'python3 -B -m unittest test_total -v、python3 -B -m unittest test_report -v、python3 -B -m unittest discover -v，cwd=点。'
        '先实际观察原 sum 失败，并独立留档“总额错误调查”，区分事实、推断、限制，不为调查造业务 Change。'
        '再呈现并保存复杂方案“总额接口 A”，本轮具体接受符合固定边界的完整方案：只有任务 SUM，scope 仅 total.py，'
        '按原独立断言把计数改成求和，空／负数保持，Task 必需 sum，context_paths 包含 test_total.py；全部测试只读。'
        '方案最终必需 integration，明确该最终检查是与此目录中后续报告 B 的联合现场，不声称 A 独立隔离完成报告。'
        '只完成 SUM 的 apply 和独立 Task 验收，保留真实 red／green和规格／规范审查。A 仍活动，不做整体验收或封存；'
        '本轮不改 report.py 或 terms.md，不批准正式知识。'),
    'pause_b': ('另建复杂方案“报告交付 B”，本轮具体接受符合这些边界的方案。只有任务 REPORT，scope 仅 report.py，'
        'render_total 调用真实 total 接口并返回其十进制字符串，保留空值／负数和一次性迭代器输入；Task 必需 report，最终 integration。'
        'context_paths 包含 total.py、test_report.py、test_integration.py；在 REPORT.external_dependencies 精确引用另一工作项 '
        'A 的 SUM Task、当前 REV／定义，condition_kind=verification_passed，依据是报告消费经真实验收的总额接口。'
        '不要把跨项引用塞进同 Change 的 dependencies，也不要只凭 done 放行。'
        '仅经 apply 完成 report.py 文件段并正常暂停，本轮不运行后检查、不验收、不封存，不改 total.py、terms.md 或测试。'
        '授权覆盖此临时 B 范围后续续接、必要修正和原检查，本轮仍保持无检查暂停边界。'),
    'cancel_a_adopt_c': ('本轮明确取消工作项“总额接口 A”，原因是后续总额职责改由独立 C 承接；使用 maintain.cancel，'
        '保留已发生文件、done SUM 和旧验收，不恢复成错误代码。读取 B 的当前条件，说明取消 A 后原引用为何受阻，不修改 B。'
        '另呈现并保存复杂方案“接续总额接口 C”，本轮具体接受：只有 SUM，scope total.py，Task sum、context test_total.py，'
        '最终 integration，明确后续与 B 的联合现场。只观察并采用当前已经正确的 total.py，apply files=[] 真实运行 sum，'
        '完成 C 的独立 SUM Task 验收；不重写 total.py，也不声称取消 A 自动授权或完成 C。'
        '本轮 C 仍活动，不整体验收或封存，不改 report.py、terms.md、测试，也不偷偷把 B 追到最新 C。'),
    'rebind_finish': ('从档案恢复 B 的正常暂停和 A 已取消／C 实际 SUM 验收。明确呈现完整新 REV：B 的 REPORT 原目标、文件、'
        'AC 和检查含义保持，只将外部固定前置由取消 A 的 SUM 替换为 C 的实际 SUM／REV／定义／verification_passed。'
        '本轮具体接受这个重新绑定，不将它称排版修改；保留旧 REV、部分结果和旧授权来源。'
        '新请求按本轮真实确认准备，不能伪造同定义继承或借旧 continuation 跳过变化。沿当前报告文件完成 B 的原检查、Task／'
        '整体验收及封存，report.py 必要修正限原范围，total.py 和测试保持。再完成 C 的联合 integration、实际审查和封存，'
        '保留 A cancelled 和原 done／VER。说明本次实际包含的关联工作，不能称单项独立隔离通过。不改 terms.md 或正式知识。'),
    'formal_candidates': ('本轮只准备正式候选，不批准或应用后两项。先使用 init 将 terms.md 当前原文具体登记为初次正式基线；'
        '本轮已具体批准的初次全文仅为“# 术语”、空行、“总额：计数。”、空行、“审查约定：尚无。”及现有换行，保留原字节。'
        '然后分别呈现并保存两个独立复杂工作项：A“正式总额含义”，只有 DOC、owner sync、scope terms.md，'
        'AC 是总额表达数值之和；B“独立审查规则”，只有 RULE、owner learn、scope terms.md，AC 是上述限定审查规则实际存在。'
        'RULE.external_dependencies 固定引用 DOC 的实际 Task／REV／定义，条件 verification_passed，不能用批准代替上游应用及验收。'
        '从总额工作的真实 red／green／验收来源记录一条有范围的 observed 项目候选经验，建议恰为“' + RULE + '”，'
        '限定本临时项目整数求和审查，保留来源、反例、局限，不声称普遍因果收益。'
        '基于同一当前原基线 terms.md 保存并实际检查两项必需文档候选：sync topic=numeric-definition 仅将“总额：计数。”'
        '改成“总额：数值之和。”；learn.promote topic=literal-review-rule 仅将“审查约定：尚无。”改成“审查约定：' + RULE + '”。'
        '分别声明确切 UTF-8 范围和独立 semantic_target，绑定各自 Task／AC，规则引用实际经验及最新状态／全部反例。'
        '呈现两项完整正文及明确批次；只保存实际内容检查，不批准、不应用、不验收或封存这两个工作项。代码和测试只读。'),
    'formal_apply': ('本轮具体批准上一轮已呈现、符合以下固定边界的两项准确候选：numeric-definition 只将“总额：计数。”'
        '改为“总额：数值之和。”；literal-review-rule 只将“审查约定：尚无。”改为“审查约定：' + RULE + '”。'
        '从档案核对完整正文、版本、基线及实际内容检查，按本轮真实来源集中逐项保存批准，不转移或扩大批准。'
        '由 sync 完成 DOC 的真实应用和独立 Task 内容验收后，才由 learn 通过同文件批准差异链完成 RULE；检查实际完整组合，'
        '保留前项含义，不重复批准未变内容。各项再做实际目标及 Task／整项验收，通过后封存两个正式工作项；'
        '必要复验不得把重新观察换 VER ID 当成必须重写原成果，不改业务代码或测试。'),
    'verify': ('控制侧已将 total.py 改回 len，并在 terms.md 末尾追加“外部未批准内容。”，这是受控外部变化。'
        '本轮仅验收：对已封存的“报告交付 B”通过 verify.run 追加当前失败／受阻观察；对已应用的审查规则通过 '
        'verify.knowledge 重新观察实际目标，不用旧应用后绿灯替代当前结论。保留工作项／Task 终态、原通过及封存截点。'
        '不修复代码、测试或文档，不重开工作项，不新增分析、正式候选或批准。说明相关前置与外部变化的影响，保留实际文件。'),
}


def scope_for(package):
    from evolve_core.package import canonical, check_package
    manifest = check_package(package)
    if (manifest['schema_version'], manifest['protocol_version']) not in ((4, 13), (4, 14), (4, 15), (4, 16)):
        raise ValueError('Multi-work acceptance requires the actual schema-4/protocol-13-or-14 package')
    required = {'maintain.cancel', 'propose.create', 'update.revise', 'verify.run', 'learn.promote', 'sync.apply'}
    if not required.issubset(manifest['available_methods']):
        raise ValueError('Required multi-work owners are not implemented by this package')
    helpers = [ROOT / 'scripts' / name for name in ('model_multi_acceptance.py', 'model_multi_checks.py',
        'model_data_acceptance.py', 'model_acceptance.py', 'verify_hosts.py')]
    body = {'slice': 'IMP-009', 'host': 'codex', 'package_version': manifest['package_version'],
        'content_digest': manifest['content_digest'], 'schema_version': 4, 'protocol_version': manifest['protocol_version'],
        'first_files': FILES, 'business_write_paths': ['total.py', 'report.py'], 'formal_write_paths': ['terms.md'],
        'readonly_paths': ['test_total.py', 'test_report.py', 'test_integration.py'],
        'cases': PROMPTS, 'fresh_conversation_per_case': True, 'maximum_sessions': 7,
        'model_selection': 'model/list isDefault at actual dispatch, no replacement',
        'specific_formal_decisions': {'initial_baseline': BASE,
            'numeric_definition_candidate': BASE.replace('总额：计数。', '总额：数值之和。'),
            'literal_rule_candidate': BASE.replace('审查约定：尚无。', '审查约定：' + RULE), 'final_composed_text': FINAL},
        'parent_mutations': ['Before final verify replace total.py with original len bug and append external unapproved text to terms.md'],
        'authorization_limits': ['Only this disposable fixture, its installed plugin and records',
            'Tests are read-only; terms.md changes only through specifically approved init/sync/learn owners',
            'Stop on permission, quota, transport or parent failure; no automatic retry or alternate model',
            'No personal config or credential changes, nested agents, external apps, commits, publication or deployment'],
        'runner_files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers}}
    return {**body, 'scope_digest': hashlib.sha256(canonical(body)).hexdigest()}


class MultiChecks:
    def __init__(self, project, evidence, scope, package, registered):
        self.project, self.evidence, self.scope = project, evidence, scope
        self.package, self.registered = package, registered
        self.original_tests = {name: ((project / name).read_bytes(), (project / name).stat().st_mtime_ns)
                               for name in scope['readonly_paths']}
        self.old_verifications = {}
        self.old_runs = {}
        self.package_files = {str(root): self.inventory(root) for root in (package, registered)}
        self.protected_config = {path: path.read_bytes() for path in (
            project / '.codex/config.toml', registered.parent / 'profile/config.toml')}

    @staticmethod
    def inventory(root):
        return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob('*') if path.is_file() and '__pycache__' not in path.parts}

    def rows(self, table):
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection, _):
            return [dict(row) for row in connection.execute('SELECT * FROM ' + table)]

    def change(self, title):
        matches = [row for row in self.rows('changes') if row['title'] == title]
        assert len(matches) == 1, 'Missing/ambiguous actual work: ' + title
        return matches[0]

    def task(self, title, key):
        change = self.change(title)
        matches = [row for row in self.rows('tasks') if row['change_id'] == change['id'] and row['revision_id'] == change['current_revision']
                   and json.loads(row['definition_json'])['local_key'] == key]
        assert len(matches) == 1
        return matches[0]

    def check(self, name):
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-v'], cwd=self.project,
                                capture_output=True, text=True, timeout=30)
        (self.evidence / (name + '-parent-literal-check.json')).write_text(json.dumps({
            'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}, ensure_ascii=False, indent=2))
        return result.returncode

    def task_verified(self, task):
        matches = [row for row in self.rows('verifications') if row['change_id'] == task['change_id']
                   and json.loads(row['items_json']).get('task_id') == task['id']]
        matches.sort(key=lambda row: (row['observed_at'], row['id']))
        assert matches and matches[-1]['status'] == 'passed', 'Actual Task acceptance is required'

    def before(self, case):
        if case == 'verify':
            (self.project / 'total.py').write_text(FILES['total.py'])
            (self.project / 'terms.md').write_text(FINAL + '\n外部未批准内容。\n')
            assert self.check('controlled-final-red') == 1
        self.before_files = {name: ((self.project / name).read_bytes(), (self.project / name).stat().st_mtime_ns)
                             for name in FILES}
        if case != 'producer_a':
            self.old_verifications = {row['id']: row for row in self.rows('verifications')}
            self.old_runs = {row['id']: row for row in self.rows('phase_runs') if row['status'] != 'started'}

    def after(self, case):
        from evolve_core.package import check_package
        for root in (self.package, self.registered):
            assert check_package(root)['content_digest'] == self.scope['content_digest']
            assert self.inventory(root) == self.package_files[str(root)]
        assert all(path.read_bytes() == content for path, content in self.protected_config.items())
        for name, observed in self.original_tests.items():
            assert ((self.project / name).read_bytes(), (self.project / name).stat().st_mtime_ns) == observed
        allowed = {'producer_a': {'total.py'}, 'pause_b': {'report.py'}, 'rebind_finish': {'report.py'},
                   'formal_apply': {'terms.md'}}.get(case, set())
        for name, (before, _) in self.before_files.items():
            if name not in allowed:
                assert (self.project / name).read_bytes() == before, 'Unexpected bytes changed: ' + name
        verifications = {row['id']: row for row in self.rows('verifications')}
        runs = {row['id']: row for row in self.rows('phase_runs')}
        assert all(verifications[key] == row for key, row in self.old_verifications.items())
        assert all(runs[key] == row for key, row in self.old_runs.items())
        assert all(row['status'] != 'started' for row in runs.values()) and not self.rows('resource_claims')
        analyses = [row for row in runs.values() if row['action'] == 'analyze' and row['status'] == 'completed']
        assert len(analyses) == 1, 'Independent analysis must coexist without being recreated or overwritten'
        if case == 'producer_a':
            assert len(self.rows('changes')) == 1 and self.change('总额接口 A')['state'] != 'archived'
            task = self.task('总额接口 A', 'SUM')
            assert task['state'] == 'done'
            self.task_verified(task)
            assert (self.project / 'report.py').read_text() == FILES['report.py']
        elif case == 'pause_b':
            task = self.task('报告交付 B', 'REPORT')
            assert task['state'] == 'in_progress'
            definition, result = json.loads(task['definition_json']), json.loads(task['result_json'])
            assert len(definition['external_dependencies']) == 1 and definition['external_dependencies'][0]['upstream_task_id'] == self.task('总额接口 A', 'SUM')['id']
            assert result.get('progress') and result['progress']['remaining']
            assert not [row for row in verifications.values() if row['change_id'] == task['change_id']]
            applied = [row for row in runs.values() if row['action'] == 'apply' and json.loads(row['input_json'])['request']['input'].get('change_id') == task['change_id']]
            assert applied and json.loads(applied[-1]['result_json'])['outcome'] == 'partial'
            from evolve_core.reading import history_snapshot
            with history_snapshot(self.project) as (connection, _):
                assert not connection.execute("SELECT id FROM events WHERE run_id=? AND kind='check_dispatch_prepared'", (applied[-1]['id'],)).fetchall()
        elif case == 'cancel_a_adopt_c':
            assert self.change('总额接口 A')['state'] == 'cancelled' and self.task('总额接口 A', 'SUM')['state'] == 'done'
            for name in ('total.py', 'report.py'):
                assert (self.project / name).stat().st_mtime_ns == self.before_files[name][1]
            c = self.task('接续总额接口 C', 'SUM')
            assert c['state'] == 'done' and json.loads(c['result_json'])['implementation_source'] == 'observed_existing_files'
            self.task_verified(c)
            b = self.task('报告交付 B', 'REPORT')
            assert json.loads(b['definition_json'])['external_dependencies'][0]['upstream_change_id'] == self.change('总额接口 A')['id']
        elif case == 'rebind_finish':
            for title in ('报告交付 B', '接续总额接口 C'):
                assert self.change(title)['state'] == 'archived'
            assert self.change('总额接口 A')['state'] == 'cancelled'
            b, c = self.task('报告交付 B', 'REPORT'), self.task('接续总额接口 C', 'SUM')
            refs = json.loads(b['definition_json'])['external_dependencies']
            assert refs[0]['upstream_task_id'] == c['id'] and refs[0]['required_revision_id'] == c['revision_id']
            assert len([row for row in self.rows('plan_revisions') if row['change_id'] == b['change_id']]) >= 2
            assert self.check(case) == 0
        elif case == 'formal_candidates':
            from evolve_core.knowledge_proposals import metadata, latest_check
            from evolve_core.reading import history_snapshot
            selected = []
            for row in self.rows('knowledge_proposals'):
                body = metadata(row)
                if body and (body.get('delivery') or {}).get('role') == 'required':
                    selected.append(row)
            assert len(selected) == 2 and {row['owner_skill'] for row in selected} == {'evolve-archive', 'evolve-learn'}
            assert all(row['state'] == 'proposed' and row['approved_event_id'] is None and row['applied_operation_id'] is None for row in selected)
            with history_snapshot(self.project) as (connection, _):
                assert all(latest_check(connection, row)['recorded_status'] == 'passed' and not latest_check(connection, row)['source_pending'] for row in selected)
            assert self.task('正式总额含义', 'DOC')['state'] == 'todo' and self.task('独立审查规则', 'RULE')['state'] == 'todo'
        elif case == 'formal_apply':
            assert (self.project / 'terms.md').read_text() == FINAL
            for title, key in (('正式总额含义', 'DOC'), ('独立审查规则', 'RULE')):
                assert self.change(title)['state'] == 'archived'
                self.task_verified(self.task(title, key))
            assert len(self.rows('rule_bindings')) == 1
        elif case == 'verify':
            b = self.change('报告交付 B')
            added = [row for key, row in verifications.items() if key not in self.old_verifications]
            assert any(row['change_id'] == b['id'] and row['status'] in ('failed', 'blocked') for row in added)
            rule = self.task('独立审查规则', 'RULE')
            app = json.loads(rule['result_json'])['document_applications']['terms.md']
            assert any(json.loads(row['items_json']).get('application_id') == app and row['status'] == 'blocked' for row in added)
            assert all(self.change(title)['state'] == 'archived' for title in ('报告交付 B', '接续总额接口 C', '正式总额含义', '独立审查规则'))
        return {'case': case, 'business_boundary_preserved': True, 'readonly_test_bytes_and_mtimes': True,
                'changes': len(self.rows('changes')), 'analyses': len(analyses), 'verifications': len(verifications),
                'pending_runs': 0, 'claims': 0, 'semantic_model_review': 'pending'}
