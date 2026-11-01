#!/usr/bin/env python3
"""Fresh native Codex journeys for guidance, closure, repair and an actual old release update."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import model_acceptance as transport
from model_data_acceptance import main, save

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'tests/fixtures/evolve-0.2.0-protocol17.zip'
FILES = {'calc.py': 'def total(values):\n    return len(values)\n',
         'test_calc.py': 'import unittest\nfrom calc import total\nclass Totals(unittest.TestCase):\n'
             '    def test_literals(self):\n        self.assertEqual(total([2,3]),5)\n'
             '        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n',
         'README.md': '# 临时整数项目\n\n目标是求和，空输入为零；原测试为独立字面预期，保持只读。\n'}
WORK = {
    'guide': '我第一次用 Evolve，想修改这个已有的小项目，应该怎样开始？本轮只解释用法和建议，不接入、不留档、不运行测试、不修改任何项目文件。',
    'plan': '使用 Evolve 规划 calc.py 的总计修复。先读取相关代码和原测试，接入必要记录设施，登记 original 检查 '
        'python3 -B -m unittest test_calc -v，cwd=点，timeout=15。只呈现并保存短方案，scope 仅 calc.py，'
        '原测试只读。本轮不实施、不运行检查、不建立完整知识基线。说明阶段结束及下一步。',
    'pause': '接受已保存的准确求和修复方案；授权通过 Evolve 只修改 calc.py，保持原测试及 README。'
        '本轮实现后正常暂停，暂不运行检查、不验收、不封存；保存已做、剩余项与下一步。'
        '后续原检查、必要修正、双维审查、验收及封存已经在同一范围授权，后续继续时复用本授权。',
    'finish': '使用 Evolve 继续刚才暂停的求和修复。核对原范围和现场，运行原检查，按原独立预期完成逐项 AC、'
        '规格与规范审查、最新整体验收并封存。必要修正在原范围继续，不新增测试、不申请重复授权。'
        '检查可复用发现，按真实来源保存或记录实际无新发现。完整闭环后给出明确状态与后续指引。',
    'diagnose': '控制侧已删除此临时项目的 checks.json、external.json 和 init.json，保留数据库、guard、managed及所有业务文件。'
        '使用 Evolve 只读诊断当前还能执行哪些动作、修复需要什么条件，给出可直接发送的接手指令；本轮不修复、不写档案、不执行检查。',
    'repair': '授权在这个临时项目中使用 Evolve 准备并核对缺失控制资料的 maintain.repair 准确方案。'
        '若完整原历史与当前保护足以证明安全，本次明确接受该范围的重建并应用；这是控制侧依据本次人类完整验收授权给出的具体临时修复决定。'
        '保留业务正文、全部旧任务、运行、验收和知识；不得手写控制资料或数据库。完成后核对新 epoch 的执行条件，'
        '实际运行原独立检查证明仍可工作。检查与已有目标复验按实际结果记录，原封存历史保留。说明修复完成与原业务目标状态。',
}
UPDATE = {
    'update_inspect': '控制侧已在隔离宿主中使用真实完整 0.2.0 包建立旧项目和正式规则，再通过宿主原生安装命令切换到本次新包。'
        '使用 Evolve 只读核对候选包、实际加载根、会话摘要、档案兼容、控制资料与旧正式知识。'
        '本会话是新会话，旧包及原始安装回执只读位于 .agents/evolve-acceptance/update/。'
        '用旧包摘要调用一次 status，实际观察 SESSION_PACKAGE_MISMATCH；然后沿本新会话实际摘要核对。'
        '不迁移同协议档案、不重新初始化、不修改正文、不写项目记录，明确各项完成范围和接手指令。',
    'update_continue': '使用更新后的 Evolve 完成 calc.py 总计修复：接受本轮展示的具体短方案，授权仅修改 calc.py，'
        '保留 test_calc.py、README.md 和已登记正式规则。运行 original 检查，完成逐 AC、规格与规范审查、'
        '必要知识收尾、最新整体验收与封存。规则的求和定义保持不变，按现场声明知识影响和实际观察。'
        '这是完整实施验收授权，范围内连续接力；保留旧包产生的全部事实。',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def scope_for(package, journey='work'):
    from evolve_core.package import canonical, check_package
    manifest = check_package(package)
    if (manifest['schema_version'], manifest['protocol_version']) != (4, 17):
        raise ValueError('Workflow acceptance requires actual schema 4 / protocol 17')
    body = {'slice': 'workflow-closure', 'journey': journey, 'host': 'codex', 'first_files': FILES,
        'package_version': manifest['package_version'], 'content_digest': manifest['content_digest'],
        'cases': WORK if journey == 'work' else UPDATE, 'fresh_conversation_per_case': True,
        'business_write_paths': ['calc.py'], 'readonly_paths': ['test_calc.py', 'README.md'],
        'parent_mutations': ['After finish, remove only checks.json, external.json and init.json'] if journey == 'work' else
            ['Install actual 0.2.0 package in isolated profile, connect and register exact temporary rule',
             'Replace isolated registered source with current complete package and refresh native installation'],
        'old_fixture_sha256': sha(OLD.read_bytes()) if journey == 'update' else None,
        'model_selection': 'Native model/list isDefault; account authentication stays in the host',
        'runner_files': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in (
            Path(__file__).resolve(), ROOT / 'scripts/model_data_acceptance.py', ROOT / 'scripts/model_acceptance.py',
            ROOT / 'scripts/verify_hosts.py')}}
    return {**body, 'scope_digest': sha(canonical(body))}


class Checks:
    def __init__(self, project, evidence, scope, package, registered):
        self.project, self.evidence, self.scope = project, evidence, scope
        self.package, self.registered = package, registered
        self.base = project / '.agents/evolve-acceptance'
        self.receipts = project / '.evolve-local/control/requests'
        self.receipts.mkdir(parents=True)
        (self.receipts / 'headless-staging.json').write_text('{"purpose":"controlled host JSON request and receipt staging"}')
        transport.digest = sha
        self.bridge = self.base / 'workflow_bridge.py'
        code = transport.HEADLESS_BRIDGE.replace('__RUNTIME__', repr(str(package / 'runtime/evolve.py'))).replace('__PROJECT__', repr(str(project)))
        code = code.replace("'error':response.get('error'),", "'workflow':response.get('workflow'),'error':response.get('error'),")
        self.bridge.write_text(code)
        self.bridge_digest = sha(self.bridge.read_bytes())
        self.next_case = 0
        if scope['journey'] == 'update':
            self.prepare_old_update()
        self.settings = {str(p): p.read_bytes() for p in (project / '.codex/config.toml', self.base / 'profile/config.toml')}

    def call(self, runtime, action, method=None, data=None, auth=None):
        argv = [sys.executable, '-B', str(runtime), '--project', str(self.project), action]
        if method:
            argv += ['--method', method]
        request = None
        if data is not None:
            argv += ['--request', '-']
            request = {'authorization': auth or {'source': 'controlled old-release fixture under actual user acceptance authorization',
                'text': 'In this disposable project only, connect, register the exact temporary rule, then verify a native package update.',
                'effect_kinds': ['project_records', 'knowledge'], 'paths': ['evolve/guides/rules.md']}, 'input': data}
        result = subprocess.run(argv, input=json.dumps(request) if request else None, capture_output=True, text=True, timeout=40)
        response = json.loads(result.stdout)
        self.update_commands.append({'argv': argv, 'request': request, 'response': response, 'exit_code': result.returncode})
        save(self.evidence / 'update-commands.json', self.update_commands)
        if not response['ok']:
            raise AssertionError(response)
        return response['data']

    def prepare_old_update(self):
        update = self.base / 'update'; update.mkdir()
        old = update / 'old-package'
        with zipfile.ZipFile(OLD) as archive:
            archive.extractall(old)
        env = {**os.environ, 'CODEX_HOME': str(self.base / 'profile')}
        settings = (self.base / 'profile/config.toml').read_bytes()
        self.update_commands = []
        def native(args, label):
            return transport.shell(['codex', 'plugin', *args, '--json'], env=env, cwd=self.project, log=self.evidence / (label + '.json'))
        current = update / 'new-package'
        self.registered.rename(current)
        shutil.copytree(old, self.registered)
        native(['remove', 'evolve@evolve-local'], 'remove-current-before-old')
        installed = native(['add', 'evolve@evolve-local'], 'install-actual-old')
        old_runtime = Path(installed['installedPath']) / 'runtime/evolve.py'
        self.old_identity = self.call(old_runtime, 'init', 'connect', {'checks': [
            {'id': 'original', 'argv': [sys.executable, '-B', '-m', 'unittest', 'test_calc', '-v'], 'cwd': '.', 'timeout': 15}]})
        self.rule = '# 求和约定\n\n## 适用范围\n本地整数 total。\n## 规则\n求和保留符号，空输入为零；原测试是独立预期。\n## 依据与例外\n只覆盖固定整数样例；其他类型未约定。\n'
        criteria = [{'key': k, 'text': v} for k, v in (
            ('structure', '完整说明本地求和范围和边界。'), ('sources', '依据当前只读原测试，无远端声明。'),
            ('consistency', '与独立字面预期一致，实际缺陷另行修复。'), ('usefulness', '读者可以判断求和目标及未约定范围。'))]
        candidate = self.call(old_runtime, 'init', 'baseline.propose', {'path': 'evolve/guides/rules.md', 'expected_digest': None,
            'content': self.rule, 'presentation': {'source': 'controlled exact fixture', 'text': self.rule}, 'topic': 'sum-contract',
            'reason': 'Preserve actual old-release approved knowledge across update.', 'acceptance': criteria,
            'document': {'kind': 'rule', 'topic': 'sum-contract', 'scope': 'Only integer sum and independent literal examples.',
                         'mode': 'managed', 'sources': [{'path': 'test_calc.py', 'expected_digest': sha((self.project / 'test_calc.py').read_bytes())}]}})
        ref = {k: candidate[k] for k in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}
        observations = [{'criterion_key': c['key'], 'status': 'passed', 'observer': 'controlled-parent-literal-inspection', 'basis': c['text']} for c in criteria]
        self.call(old_runtime, 'sync', 'check', {'proposal': ref, 'observations': observations})
        reviewed = self.call(old_runtime, 'sync', 'review', {'decisions': [{'proposal': ref, 'decision': 'approved',
            'source': 'controlled exact rule under actual user full-acceptance authorization', 'text': self.rule, 'reason': 'Exact independent temporary rule.'}]})
        app = self.call(old_runtime, 'init', 'baseline.apply', {'proposal': ref, 'approved_event_id': reviewed['decisions'][0]['decision_event_id']})
        self.call(old_runtime, 'verify', 'knowledge', {'application_id': app['application_id'], 'observations': observations})
        self.old_rows = self.rows()
        old_manifest = json.loads((old / 'evolve-package.json').read_text())
        native(['remove', 'evolve@evolve-local'], 'remove-old-for-update')
        shutil.rmtree(self.registered)
        current.rename(self.registered)
        installed = native(['add', 'evolve@evolve-local'], 'install-current-update')
        if Path(installed['installedPath']).resolve() != self.package.resolve():
            raise AssertionError('Native update did not return the actual cache used by fresh sessions')
        (self.base / 'profile/config.toml').write_bytes(settings)
        save(update / 'update-context.json', {'old_version': old_manifest['package_version'], 'old_digest': old_manifest['content_digest'],
            'new_version': self.scope['package_version'], 'new_digest': self.scope['content_digest'],
            'project_id': self.old_identity['project_id'], 'old_package': str(old), 'current_package': str(self.package),
            'native_installation_receipts': [str(self.evidence / (label + '.json')) for label in ('install-actual-old', 'install-current-update')]})

    def rows(self):
        if not (self.project / 'evolve/history.db').is_file():
            return {}
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection, _):
            return {table: {r['resource' if table == 'resource_claims' else 'id']: dict(r) for r in connection.execute('SELECT * FROM ' + table)}
                    for table in ('phase_runs', 'changes', 'tasks', 'verifications', 'artifact_versions', 'events', 'resource_claims')}

    def project_snapshot(self):
        return {str(p.relative_to(self.project)): sha(p.read_bytes()) for name in ('evolve', '.evolve-local')
                for p in (self.project / name).rglob('*') if p.is_file() and '.evolve-local/control/requests/' not in str(p.relative_to(self.project))}

    def before(self, case):
        if case != list(self.scope['cases'])[self.next_case]:
            raise AssertionError('Cases must execute in their declared order')
        if case == 'diagnose':
            for name in ('checks.json', 'external.json', 'init.json'):
                (self.project / '.evolve-local/control' / name).unlink()
        self.before_rows = self.rows()
        self.before_project = self.project_snapshot()
        self.before_calc = (self.project / 'calc.py').read_bytes()
        self.before_receipts = set(self.receipts.glob('cli-receipt-*.json'))
        self.event_offset = (self.evidence / 'model-events.jsonl').stat().st_size if (self.evidence / 'model-events.jsonl').exists() else 0

    def context_for(self, case):
        return '\n本轮所有 Evolve CLI 经控制侧只读桥接脚本 python3 -B ' + str(self.bridge) + \
            ' <action> [--method <method>] [其他CLI参数] 调用；桥接输出真实 receipt 路径和 workflow，可读全文。' \
            '桥接只在 .evolve-local/control/requests 保存控制侧验收回执；此暂存不代表运行时查询创建记录。' \
            '写请求文件按共享协议放 .evolve-local/control/requests，实际业务和知识变化经 Evolve 动作。' \
            '插件、宿主设置、桥接、测试与 README 只读。'

    def after(self, case):
        from evolve_core.package import check_package
        for package in (self.package, self.registered):
            assert check_package(package)['content_digest'] == self.scope['content_digest']
        assert sha(self.bridge.read_bytes()) == self.bridge_digest
        assert all(Path(p).read_bytes() == content for p, content in self.settings.items())
        for name in ('README.md', 'test_calc.py'):
            assert (self.project / name).read_text() == FILES[name], 'Independent fixture changed'
        if case not in ('pause', 'finish', 'update_continue'):
            assert (self.project / 'calc.py').read_bytes() == self.before_calc
        receipts = [json.loads(p.read_text()) for p in set(self.receipts.glob('cli-receipt-*.json')) - self.before_receipts]
        assert receipts, 'Actual CLI usage is required'
        assert all(r['response'].get('workflow', {}).get('next_steps') for r in receipts)
        events = (self.evidence / 'model-events.jsonl').read_bytes()[self.event_offset:].decode()
        messages = []
        for line in events.splitlines():
            event = json.loads(line)
            item = event.get('params', {}).get('item', {})
            if event.get('method') == 'item/completed' and item.get('type') == 'agentMessage':
                messages.append(item.get('text', ''))
        save(self.evidence / (case + '-visible-messages.json'), messages)
        assert messages and any('[Evolve' in text for text in messages[:-1]) and '[Evolve' in messages[-1], 'Visible start/end markers missing'
        assert 'evolve-' in messages[-1], 'Final handoff skill missing'
        rows = self.rows()
        for table in ('phase_runs', 'verifications', 'artifact_versions', 'events'):
            assert all(rows.get(table, {}).get(key) == value for key, value in self.before_rows.get(table, {}).items()), 'Historical facts changed'
        assert not rows.get('resource_claims') and all(r['status'] != 'started' for r in rows.get('phase_runs', {}).values())
        if case in ('guide', 'diagnose', 'update_inspect'):
            assert self.project_snapshot() == self.before_project, 'Read-only stage changed product files'
        if case == 'guide':
            assert not rows
            assert any(r['response'].get('data', {}).get('project', {}).get('state') == 'not_connected' for r in receipts)
        elif case == 'plan':
            assert len(rows['changes']) == 1 and next(iter(rows['tasks'].values()))['state'] == 'todo'
            assert not rows['verifications']
        elif case == 'pause':
            assert next(iter(rows['tasks'].values()))['state'] == 'in_progress' and not rows['verifications']
            assert any(r['response'].get('workflow', {}).get('phase_status') == 'paused' for r in receipts)
        elif case in ('finish', 'update_continue'):
            assert len(rows['changes']) == 1 and next(iter(rows['changes'].values()))['state'] == 'archived'
            assert next(iter(rows['tasks'].values()))['state'] == 'done'
            assert any(r['response'].get('workflow', {}).get('goal_complete') for r in receipts)
        elif case == 'diagnose':
            assert any(r['response'].get('data', {}).get('readiness', {}).get('actions', {}).get('checks', {}).get('status') == 'blocked' for r in receipts)
        elif case == 'repair':
            assert any(r['response'].get('data', {}).get('outcome') == 'repaired' for r in receipts)
            assert any(r['kind'] == 'check_process_finished' for key, r in rows['events'].items()
                       if key not in self.before_rows['events']), 'Actual post-repair check receipt missing'
        elif case == 'update_inspect':
            assert any(r['response'].get('error', {}).get('code') == 'SESSION_PACKAGE_MISMATCH' for r in receipts)
            assert (self.project / 'evolve/guides/rules.md').read_text() == self.rule
            assert all(rows[t].get(k) == v for t, values in self.old_rows.items() for k, v in values.items())
        if case in ('finish', 'repair', 'update_continue'):
            checked = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_calc', '-v'], cwd=self.project,
                                     capture_output=True, text=True, timeout=20)
            save(self.evidence / (case + '-independent-check.json'), {'exit_code': checked.returncode, 'stdout': checked.stdout, 'stderr': checked.stderr})
            assert checked.returncode == 0
        self.next_case += 1
        return {'case': case, 'passed_parent_checks': True, 'actual_cli_receipts': len(receipts),
                'visible_messages': len(messages), 'counts': {t: len(v) for t, v in rows.items()}, 'semantic_trace_review': 'pending'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--journey', choices=('work', 'update'), default='work')
    selected, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    main(scope_factory=lambda package: scope_for(package, selected.journey), checker_type=Checks,
         prompts=WORK if selected.journey == 'work' else UPDATE, description=__doc__)
