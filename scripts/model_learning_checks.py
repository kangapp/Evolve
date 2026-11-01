"""Concrete four-file learning-cycle scope and actual native parent boundaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

from learning_fixture import FILES, CHECKS, BASE, FINAL, ITERATOR_BUG

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {
    'seed': ('接入当前四文件临时项目，精确登记 unit 和 guard，定义见下文。guard.py 只读，不是待修代码；'
        '原 test_total.py 的 Totals.test_literals 三个独立字面量与方法必须保留，本轮测试全文只读。'
        '先保存并具体接受简单方案“列表求和 A”，scope 仅 total.py，required_checks 仅 unit，本轮只交付原三个列表样例。'
        '经 apply files=[] 实际留原 unit red，再仅修 total.py 为真实求和，原 unit、双轴实际自审及整体验收通过后封存 A。'
        '根据 A 真实 red／green／验收来源记录一条 observed 项目候选经验，限定原整数列表样例，未验证迭代器，复用先核对新输入域；'
        '不把候选或引用次数当授权／普遍正确性。先将 guide.md 原全文具体批准为初次正式基线，保留原字节。'
        '另保存并具体接受简单工作项“列表审查规则 R”，scope guide.md，responsible_action=learn，必需成果为下文准确规则。'
        '由 learn 提出 topic=literal-review-rule、criterion_key=RULE 的准确候选，完整呈现／内容检查后按下文具体决定批准和实际应用，'
        'rule_scope 仅 ["本临时项目整数列表求和审查"]，绑定刚才真实经验的最新状态与全部反例；目标／工作验收后封存 R。'
        '再只呈现并保存未接受的复杂方案“待执行列表复查 C”：唯一 LISTS，scope total.py，Task／最终 unit，'
        'context_paths 为 test_total.py、guard.py，只核对原列表域。记录该计划对原经验的实际 adopted 决定及限制，效果 unknown；'
        '不接受或执行 C。本轮不解决 guard 的迭代器覆盖缺口，不新增独立分析。'),
    'counterexample': ('控制侧已将 total.py 换成列表求和正确、一次性迭代器返回 0 的固定错误实现。'
        '建立并具体接受简单方案“迭代器求和 B”：scope 仅 total.py，required_checks 为 unit、guard；原列表求和与 '
        'iter([5,-2]) 返回独立字面量 3 均是必需 AC。先检索旧经验、核对真实范围，记录实际采用／拒绝理由，不声称新域已被证明。'
        '本轮不修任何业务文件：apply files=[] 实际保存 unit 绿而 guard 红的结果；实际运行生成器独立断言并用 verify.run '
        '保存当前 failed／blocked，不伪称检查全绿。用本次决定之后、同 B Task 定义的真实结果反馈 counterexample，保留原列表事实。'
        '核对已应用规则来源及 C 的 learning_context，原经验须不再当可靠建议；规则实际目标重验，保留正文和历史通过。'
        '不复用旧绿灯强行 active，不自动执行 C，不新增正式候选、批准、分析或修改检查配置。'),
    'propose_check': ('只调查已有 unit／guard 的实际覆盖并提出检查改进，不写 total.py、test_total.py、guide.md 或 guard.py。'
        '实际运行现有 guard，说明为何原列表测试漏了 iterator_zero 变体。基于 B 的真实失败来源保存一条新的有范围 observed 候选经验：'
        '保留原列表断言并补迭代器独立字面量，旧经验及反例不删除。'
        '完整呈现并用 update.revise 保存 B 的新复杂方案：scope 为 test_total.py、total.py，最终 unit＋guard，'
        '保留原 LISTS／ITERATOR 需求，另有 COVERAGE；CHECK 仅 test_total.py，必需 guard、context guard.py；'
        'FIX 仅 total.py，必需 unit＋guard，context test_total.py、guard.py，固定同 Change CHECK 的 verification_passed 前置。'
        'CHECK 只保留原 Totals.test_literals 并新增 total(iter([5,-2])) == 3 的独立测试，不检查实现源码或计算预期；'
        'FIX 修真实求和。说明 learn 不能代改测试／CI／hook。本轮只保存未接受的新 REV／范围候选，保留旧失败，不批准或实施。'),
    'implement_check': ('本轮具体接受上一轮完整、符合固定 CHECK／FIX 边界的新 B REV／范围候选，使用实际 candidate 摘要；'
        '新 scope 允许 apply 修改 test_total.py、total.py，原需求和原检查含义不降低。本轮只完成 CHECK，不执行 FIX。'
        '先按当前 CHECK Task 定义实际记录对新候选经验的 adopted 决定及适用限制，再由 apply 只改 test_total.py：'
        '保留原字面量方法，增加一次性迭代器 [5,-2] 结果 3。运行原只读 guard、完成 CHECK 的实际 Task 验收。'
        'guard 应显示正确实现绿、两个错误变体红；当前 total.py 仍错误，实际 unit 应红，不称源码已修好。'
        '不记录采用效果反馈，不改 total.py、guide.md、guard.py、配置、CI 或 hook。'),
    'fix_and_archive': ('从真实档案恢复 B 的已接受复杂 REV、CHECK 的实际通过与 FIX 前置。'
        '只由 apply 完成 FIX 的 total.py，在原列表与一次性迭代器范围恢复真实求和，不改测试、guard 或正式正文。'
        '执行原 unit／guard、独立 Task 及整体验收、双轴实际自审后封存 B，保留旧 REV 和原失败。'
        'C 仍未执行；旧经验／规则的待复审不因本次成功自动消失，新候选不自动 active。本轮不填写学习效果或批准规则。'),
    'feedback_and_resume': ('仅做真实学习反馈和只读续接，不改四份文件、不执行 C、不新增规则或批准。'
        '对已实际采用的新经验，使用 CHECK Task 定义下、采用之后的实际 apply／verify 来源记录有界 helped／not_helped／unknown，'
        '说明 guard 的真实区分结果；不要用 B 整项 VER 冒充 CHECK 来源，也不把整单成功归功于所有引用，不自动 active。'
        '恢复 C 的原采用及当前 learning_context，展示旧经验反例、规则来源待复审以及原测试上下文已变化，C 保持未接受／未执行。'
        '对规则真实目标再次 verify.knowledge，区分正文仍正确保存与来源需要复审；保留原通过、正文、决定和历史。'),
}
PROMPTS['seed'] += ('\n原检查完整定义：' + json.dumps(CHECKS, ensure_ascii=False)
    + '\n具体初次全文批准仅为：\n' + BASE + '\n后续具体规则批准仅为：\n' + FINAL
    + '\n两次批准均须实际呈现、当前内容检查和准确版本绑定；没有其他知识决定。')


def scope_for(package):
    from evolve_core.package import canonical, check_package
    manifest = check_package(package)
    if (manifest['schema_version'], manifest['protocol_version']) not in ((4, 14), (4, 15), (4, 16), (4, 17)):
        raise ValueError('Learning-cycle acceptance requires actual schema4/protocol14-or-15')
    required = {'learn.record', 'learn.search', 'learn.review', 'learn.promote', 'update.revise', 'verify.knowledge', 'apply.implement'}
    if not required.issubset(manifest['available_methods']):
        raise ValueError('Required original learning and modification owners are unavailable')
    names = ['model_learning_acceptance.py', 'model_learning_checks.py', 'learning_fixture.py',
             'model_data_acceptance.py', 'model_acceptance.py', 'verify_hosts.py']
    body = {'slice': 'IMP-010', 'host': 'codex', 'package_version': manifest['package_version'],
        'content_digest': manifest['content_digest'], 'schema_version': 4, 'protocol_version': manifest['protocol_version'],
        'first_files': FILES, 'checks': CHECKS, 'business_write_paths': ['total.py', 'test_total.py'],
        'formal_write_paths': ['guide.md'], 'readonly_paths': ['guard.py'],
        'preserved_test_contract': 'Original Totals.test_literals AST and its three independent literals never change',
        'specific_formal_decisions': {'initial_baseline': BASE, 'exact_rule_candidate': FINAL,
            'rule_scope': ['本临时项目整数列表求和审查'], 'later_rule_rewrite_or_rebinding': 'not authorized'},
        'cases': PROMPTS, 'maximum_sessions': 6, 'fresh_conversation_per_case': True,
        'model_selection': 'model/list isDefault at actual dispatch; no replacement',
        'parent_mutations': ['Before counterexample only replace total.py with the fixed iterator-zero implementation'],
        'authorization_limits': ['Only this disposable project and actual installed plugin; original literal method and guard read-only',
            'Guide only exact initial baseline and specifically approved first rule via init/learn; no later rewrite',
            'Initial init registers only unit and guard; later configuration, CI and hook changes prohibited',
            'No Claude, personal config or credential changes, nested agents, external apps, production data, publication or deployment',
            'Stop on permission, quota, transport or parent failure; no automatic retry or alternate model'],
        'runner_files': {'scripts/' + name: hashlib.sha256((ROOT / 'scripts' / name).read_bytes()).hexdigest() for name in names}}
    return {**body, 'scope_digest': hashlib.sha256(canonical(body)).hexdigest()}


class LearningChecks:
    def __init__(self, project, evidence, scope, package, registered):
        self.project, self.evidence, self.scope = project, evidence, scope
        self.package, self.registered = package, registered
        self.guard_original = ((project / 'guard.py').read_bytes(), (project / 'guard.py').stat().st_mtime_ns)
        self.packages = {str(p): self.inventory(p) for p in (package, registered)}
        self.configs = {p: p.read_bytes() for p in (project / '.codex/config.toml', registered.parent / 'profile/config.toml')}
        self.old_verifications, self.old_runs = {}, {}

    @staticmethod
    def inventory(root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

    def rows(self, table):
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection, _):
            return [dict(row) for row in connection.execute('SELECT * FROM ' + table)]

    def entries(self):
        from evolve_core.learning import catalog
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection, _):
            return catalog(connection)

    def change(self, title):
        found = [r for r in self.rows('changes') if r['title'] == title]
        assert len(found) == 1, 'Missing or ambiguous actual Change: ' + title
        return found[0]

    def tasks(self, title):
        change = self.change(title)
        return [r for r in self.rows('tasks') if r['revision_id'] == change['current_revision']]

    def task(self, title, key=None):
        found = [r for r in self.tasks(title) if key is None or json.loads(r['definition_json'])['local_key'] == key]
        assert len(found) == 1
        return found[0]

    def verified_task(self, task):
        structured = json.loads(task['definition_json']).get('structured', False)
        found = [r for r in self.rows('verifications') if r['change_id'] == task['change_id']
                 and json.loads(r['items_json']).get('task_id') == (task['id'] if structured else None)]
        found.sort(key=lambda r: (r['observed_at'], r['id']))
        assert found and found[-1]['status'] == 'passed'

    def guard(self, case):
        r = subprocess.run([sys.executable, '-B', 'guard.py'], cwd=self.project, capture_output=True, text=True, timeout=40)
        result = {'exit_code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}
        (self.evidence / (case + '-parent-guard.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        assert r.returncode in (0, 1), result
        return r.returncode

    def before(self, case):
        if case == 'counterexample':
            (self.project / 'total.py').write_text(ITERATOR_BUG)
        self.before_files = {n: ((self.project / n).read_bytes(), (self.project / n).stat().st_mtime_ns) for n in FILES}
        if case != 'seed':
            self.old_verifications = {r['id']: r for r in self.rows('verifications')}
            self.old_runs = {r['id']: r for r in self.rows('phase_runs') if r['status'] != 'started'}

    def after(self, case):
        from evolve_core.package import check_package
        for root in (self.package, self.registered):
            assert check_package(root)['content_digest'] == self.scope['content_digest']
            assert self.inventory(root) == self.packages[str(root)]
        assert all(p.read_bytes() == content for p, content in self.configs.items())
        visible = set()
        for directory, subdirs, names in os.walk(self.project):
            subdirs[:] = [n for n in subdirs if n not in {'evolve', '.evolve-local', '.agents', '.codex', '__pycache__'}]
            visible.update((Path(directory) / name).relative_to(self.project).as_posix() for name in names)
        assert visible == set(FILES), 'Unexpected business files: ' + str(sorted(visible ^ set(FILES)))
        allowed = {'seed': {'total.py', 'guide.md'}, 'implement_check': {'test_total.py'},
                   'fix_and_archive': {'total.py'}}.get(case, set())
        for name, observed in self.before_files.items():
            if name not in allowed:
                assert ((self.project / name).read_bytes(), (self.project / name).stat().st_mtime_ns) == observed, name
        assert ((self.project / 'guard.py').read_bytes(), (self.project / 'guard.py').stat().st_mtime_ns) == self.guard_original
        actual = tomllib.loads((self.project / 'evolve/config.toml').read_text())['verification']['checks']
        assert sorted(actual, key=lambda c: c['id']) == sorted(CHECKS, key=lambda c: c['id'])
        if case == 'seed':
            self.check_config = (self.project / 'evolve/config.toml').read_bytes()
        assert (self.project / 'evolve/config.toml').read_bytes() == self.check_config
        runs = {r['id']: r for r in self.rows('phase_runs')}
        verifications = {r['id']: r for r in self.rows('verifications')}
        assert all(r['package_digest'] == self.scope['content_digest'] for r in runs.values()), 'Unexpected runtime package origin'
        assert all(runs[key] == row for key, row in self.old_runs.items())
        assert all(verifications[key] == row for key, row in self.old_verifications.items())
        assert not self.rows('resource_claims') and all(r['status'] != 'started' for r in runs.values())
        assert len(self.rows('knowledge_proposals')) == 2 and len(self.rows('rule_bindings')) == 1
        assert (self.project / 'guide.md').read_text() == FINAL
        entries = self.entries()
        if case == 'seed':
            assert len(entries) == 1
            self.old_experience_id = next(iter(entries))
            old = entries[self.old_experience_id]
            assert old['state'] == 'candidate' and old['experience']['cause']['confidence'] == 'observed'
            assert len(old['sources']) >= 2
            assert self.change('列表求和 A')['state'] == self.change('列表审查规则 R')['state'] == 'archived'
            assert self.task('待执行列表复查 C', 'LISTS')['state'] == 'todo'
            self.pending_change = self.change('待执行列表复查 C')
            self.pending_revision = next(r for r in self.rows('plan_revisions') if r['id'] == self.pending_change['current_revision'])
            assert self.pending_revision['accepted_event_id'] is None
            assert json.loads(self.rows('rule_bindings')[0]['scope_json']) == self.scope['specific_formal_decisions']['rule_scope']
            c = [d for d in old['applications'] if d['change_id'] == self.change('待执行列表复查 C')['id']]
            assert len(c) == 1 and c[0]['decision'] == 'adopted' and c[0]['effect'] == 'unknown' and not c[0].get('feedback')
            self.pending_tasks = self.tasks('待执行列表复查 C')
        else:
            old = entries[self.old_experience_id]
            assert old['state'] == 'needs_review' and old['counterexamples'] and not old['recommendation_allowed']
            assert self.tasks('待执行列表复查 C') == self.pending_tasks
            assert self.change('待执行列表复查 C') == self.pending_change
            assert next(r for r in self.rows('plan_revisions') if r['id'] == self.pending_revision['id']) == self.pending_revision
            assert not any(r['action'] == 'apply' and json.loads(r['input_json'])['request']['input'].get('change_id') == self.change('待执行列表复查 C')['id'] for r in runs.values())
        if case == 'counterexample':
            assert len(entries) == 1 and self.change('迭代器求和 B')['state'] != 'archived'
            assert any(r['change_id'] == self.change('迭代器求和 B')['id'] and r['status'] in ('failed', 'blocked') for r in verifications.values())
        if case in ('counterexample', 'feedback_and_resume'):
            application_id = self.rows('rule_bindings')[0]['application_id']
            added = [r for key, r in verifications.items() if key not in self.old_verifications]
            observed = [r for r in added if json.loads(r['items_json']).get('application_id') == application_id]
            assert observed and observed[-1]['status'] == 'blocked'
            item = json.loads(observed[-1]['items_json'])
            assert item['current_matches_application'] is True and item['implementation_basis_error'] is not None
        if case == 'propose_check':
            assert len(entries) == 2
            self.new_experience_id = next(key for key in entries if key != self.old_experience_id)
            change = self.change('迭代器求和 B')
            revision = next(r for r in self.rows('plan_revisions') if r['id'] == change['current_revision'])
            if change['complexity'] == 'complex':
                assert revision['accepted_event_id'] is None and all(t['state'] == 'todo' for t in self.tasks('迭代器求和 B'))
            else:
                assert any(r['action'] == 'update' and json.loads(r['result_json']).get('outcome') == 'scope_confirmation_required' for r in runs.values())
        if case in ('implement_check', 'fix_and_archive', 'feedback_and_resume'):
            check = self.task('迭代器求和 B', 'CHECK')
            assert check['state'] == 'done'
            self.verified_task(check)
            adopted = [d for d in entries[self.new_experience_id]['applications'] if d['definition_digest'] == check['definition_digest'] and d['decision'] == 'adopted']
            assert len(adopted) == 1
            if case != 'feedback_and_resume':
                assert not adopted[0].get('feedback')
            else:
                assert adopted[0].get('feedback', {}).get('outcome') in ('helped', 'not_helped', 'unknown')
                assert entries[self.new_experience_id]['state'] == 'candidate'
        if case == 'implement_check':
            assert self.task('迭代器求和 B', 'FIX')['state'] == 'todo'
            assert (self.project / 'total.py').read_text() == ITERATOR_BUG
        if case in ('fix_and_archive', 'feedback_and_resume'):
            assert self.change('迭代器求和 B')['state'] == 'archived'
            assert self.task('迭代器求和 B', 'FIX')['state'] == 'done'
            self.verified_task(self.task('迭代器求和 B', 'FIX'))
        assert self.guard(case) == (1 if case in ('seed', 'counterexample', 'propose_check') else 0)
        return {'case': case, 'business_boundary_preserved': True, 'guard_and_original_literals_preserved': True,
            'changes': len(self.rows('changes')), 'experiences': len(entries), 'verifications': len(verifications),
            'pending_runs': 0, 'claims': 0, 'semantic_model_review': 'pending'}
