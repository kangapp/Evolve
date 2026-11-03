#!/usr/bin/env python3
"""Prepare a bounded Codex-only IMP-008 acceptance; dispatch needs exact human scope."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
import model_acceptance as transport
from verify_hosts import codex_skills

PROMPTS = {
    'investigate': ('使用 Evolve 只调查并独立留档当前订单 SQL 的日期／口径错误，不修复。先核对 orders.json、model.sql、'
        'test_reconciliation.py 的真实材料和局限；执行 python3 -B -m unittest test_reconciliation -v，保留真实失败、'
        '独立预期及原完整检查定义，登记检查 id=reconcile、cwd=点、timeout=15。业务日期为 2026-10-30、2026-10-31、'
        '2026-11-01；粒度为每业务日期每订单最新版本后汇总金额和数量，最新空金额排除，负数退款计入，空日期为零。'
        '保存 data_context 及每个所用来源的实际 data_scope，区分业务日期和观察时间。只限固定夹具，不保证生产数据时效。'
        '本轮仅可建立记录设施和分析记录，不创建 Change／Task，不写正式知识或业务文件。'),
    'repair': ('从 Evolve 恢复上一轮订单调查，另呈现并保存短方案“订单 SQL 日期与口径修复”，本轮明确接受符合这些固定边界的方案。'
        '引用真实 analysis_basis 和原症状判据，只允许经 apply 修改 model.sql。保留 orders.json 和 test_reconciliation.py 原字节。'
        '按指定日期过滤、每日期／订单选最新版本，再排除空金额；退款、重复和空日期按原独立断言核对。'
        '运行原 reconcile 检查，完成真实逐 AC、规格和规范审查、原症状复验及封存；原范围内发现必需问题可修复复验。'
        '只在内存 SQLite 固定样例验证，不执行正式数据补数，不批准正式知识。'),
    'lineage': ('使用 Evolve 为“订单有限关系调查”另建独立分析主题，保留原 SQL 错误调查及已封存 Change。'
        '只读当前修复后的 SQL 和固定订单材料，保存相同三个业务日期的范围／粒度／口径、真实来源与观察时间。'
        '将 orders→daily_totals 的本地 SQL 转换保存为有来源的 observed 关系；未调查生产上游，保持 partial 和明确覆盖限制，'
        '不把局部关系称完整血缘。独立分析不创建业务 Change。随后从此底稿导出 '
        '.evolve-local/exports/lineage.md 和 .evolve-local/exports/lineage.json；图和正文来自同一底稿，导出不重查业务数据。'
        '不改 SQL、输入或测试，不批准或写正式知识。'),
    'reexport': ('控制侧已移走 orders.json 和 model.sql，本轮仅从给定已保存分析引用重新导出，'
        '不读取、重建或重新查询业务来源，不运行 status／resume 或业务检查，也不新增分析。'
        '直接用 maintain.export 输出 .evolve-local/exports/reexport.md 与 .evolve-local/exports/reexport.json。'
        '说明原观察时点、生成时点、partial 和来源覆盖限制，源文件缺失不补成当前数据已验证。'),
    'verify': ('控制侧已恢复 SQL 和输入，并将订单 A 在 2026-10-30 的两条最新版本金额改为 99，形成真实数据变化。'
        '使用 Evolve 仅验收已封存的“订单 SQL 日期与口径修复”当前现场，保留原判据和历史通过／封存。'
        '运行原检查并如实追加当前失败或受阻验收，不修复 SQL、数据或测试，不重开 Change，不把旧来源当当前数据仍通过。'
        '说明历史完成与当前变化的区别和后续方案；不批准正式知识。'),
}


def sha(content):
    return hashlib.sha256(content).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def scope_for(package):
    from evolve_core.package import check_package, canonical
    manifest = check_package(package)
    if (manifest['schema_version'], manifest['protocol_version']) not in ((4, 12), (4, 13), (4, 14), (4, 15), (4, 16), (4, 17), (4, 18)):
        raise ValueError('IMP-008 scope requires the actual schema-4/protocol-12-to-14 package')
    sys.path.insert(0, str(ROOT / 'tests'))
    import test_sql_workflow as fixture
    files = {'orders.json': json.dumps(fixture.ORDERS), 'model.sql': fixture.BROKEN,
             'test_reconciliation.py': fixture.CHECK}
    body = {'slice': 'IMP-008', 'host': 'codex', 'package_version': manifest['package_version'],
        'content_digest': manifest['content_digest'], 'protocol_version': manifest['protocol_version'], 'schema_version': 4,
        'first_files': files, 'business_write_paths': ['model.sql'],
        'readonly_paths': ['orders.json', 'test_reconciliation.py'], 'cases': PROMPTS,
        'fresh_conversation_per_case': True, 'maximum_sessions': 5,
        'parent_mutations': ['After lineage remove orders.json and model.sql for saved-only export',
                             'Before verify restore both and set the two latest A amounts on 2026-10-30 to 99'],
        'model_selection': 'model/list isDefault at dispatch; no manual model replacement',
        'authorization_limits': ['Disposable fixture and its records only; no formal knowledge approval or production data execution',
            'Stop on quota, permission, transport or parent failure; no automatic retry',
            'No personal config or credential changes, external apps, nested agents, commits, publication or deployment'],
        'runner_files': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in (
            Path(__file__).resolve(), ROOT / 'scripts/model_acceptance.py', ROOT / 'scripts/verify_hosts.py',
            ROOT / 'tests/test_sql_workflow.py')}}
    return {**body, 'scope_digest': sha(canonical(body))}


class Checks:
    def __init__(self, project, evidence, scope, package, registered):
        self.project, self.evidence, self.scope = project, evidence, scope
        self.package, self.registered = package, registered
        self.original = {name: (project / name).read_bytes() for name in scope['first_files']}
        self.verifications, self.saved_sql, self.relation = {}, None, None

    def rows(self, table):
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection, _):
            return [dict(row) for row in connection.execute('SELECT * FROM ' + table)]

    def test(self, label):
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_reconciliation', '-v'],
            cwd=self.project, capture_output=True, text=True, timeout=30)
        save(self.evidence / (label + '-literal-check.json'), {'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr})
        return result.returncode

    def before(self, case):
        if case == 'reexport':
            self.saved_sql = (self.project / 'model.sql').read_bytes()
            for name in ('orders.json', 'model.sql'):
                (self.project / name).unlink()
        elif case == 'verify':
            (self.project / 'model.sql').write_bytes(self.saved_sql)
            data = json.loads(self.original['orders.json'])
            data[1][3] = data[2][3] = 99
            (self.project / 'orders.json').write_text(json.dumps(data))
            assert self.test('controlled-later-red') == 1
        self.before_business = {name: (self.project / name).read_bytes() if (self.project / name).exists() else None
                                for name in self.original}
        if case != 'investigate':
            self.verifications = {row['id']: row for row in self.rows('verifications')}
            self.old_analyses = [row for row in self.rows('phase_runs') if row['action'] == 'analyze']

    def after(self, case):
        from evolve_core.package import check_package
        for package in (self.package, self.registered):
            assert check_package(package)['content_digest'] == self.scope['content_digest']
        for name, content in self.before_business.items():
            if case == 'repair' and name == 'model.sql':
                continue
            current = (self.project / name).read_bytes() if (self.project / name).exists() else None
            assert current == content, 'Unexpected business change: ' + name
        changes, tasks = self.rows('changes'), self.rows('tasks')
        runs = self.rows('phase_runs')
        analyses = [row for row in runs if row['action'] == 'analyze' and row['status'] == 'completed']
        fresh_ver = {row['id']: row for row in self.rows('verifications')}
        for key, row in self.verifications.items():
            assert fresh_ver[key] == row, 'Historical verification changed'
        assert not self.rows('resource_claims') and all(row['status'] != 'started' for row in runs)
        assert not self.rows('knowledge_proposals') and not self.rows('spec_applications')
        assert all(row['kind'] in ('config', 'short_plan', 'source_result') for row in self.rows('artifacts'))
        if case == 'investigate':
            assert not changes and not tasks and len(analyses) == 1
            analysis = json.loads(analyses[0]['result_json'])['analysis']
            assert analysis['symptom']['status'] == 'reproduced' and set(analysis['data_context']['business_dates']) == {'2026-10-30', '2026-10-31', '2026-11-01'}
            assert self.test('original-red') == 1
        else:
            assert len(changes) == len(tasks) == 1 and changes[0]['state'] == 'archived' and tasks[0]['state'] == 'done'
            if case == 'repair':
                assert self.test('original-green') == 0
                assert any(row['status'] == 'passed' for row in fresh_ver.values())
                assert len(analyses) == 1
            elif case == 'lineage':
                assert len(analyses) == 2
                old_ids = {row['id'] for row in self.old_analyses}
                relation = next(row for row in analyses if row['id'] not in old_ids)
                analysis = json.loads(relation['result_json'])['analysis']
                assert analysis['answer_status'] == 'partial' and analysis['relationships'] and analysis['limitations']
                self.relation = {'run_id': relation['id'], 'result_digest': relation['result_digest']}
            elif case == 'reexport':
                assert len(analyses) == 2
                new_runs = [row for row in runs if row['id'] not in self.before_run_ids]
                assert len(new_runs) == 2 and all(row['action'] == 'maintain' and row['method'] == 'export' for row in new_runs)
            elif case == 'verify':
                assert len(analyses) == 2
                added = [row for key, row in fresh_ver.items() if key not in self.verifications]
                assert added and any(row['status'] in ('failed', 'blocked') for row in added)
        if case in ('lineage', 'reexport'):
            name = 'lineage' if case == 'lineage' else 'reexport'
            report = json.loads((self.project / ('.evolve-local/exports/' + name + '.json')).read_text())
            assert report['source'] == self.relation and report['business_sources_reobserved'] is False
            md = (self.project / ('.evolve-local/exports/' + name + '.md')).read_text()
            assert '```mermaid' in md and 'partial' in md and 'not reobserved' in md
        self.before_run_ids = {row['id'] for row in runs}
        return {'case': case, 'changes': len(changes), 'analyses': len(analyses), 'verifications': len(fresh_ver),
                'business_boundary_preserved': True, 'package_integrity': True,
                'pending_runs': 0, 'active_claims': 0, 'semantic_model_review': 'pending'}


def main(*, scope_factory=scope_for, checker_type=Checks, prompts=PROMPTS, description=__doc__):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--authorization-text')
    parser.add_argument('--expected-scope-digest')
    args = parser.parse_args()
    package = args.package.resolve()
    sys.path.insert(0, str(package / 'runtime'))
    from evolve_core.privacy import redact
    transport.redact = redact
    scope = scope_factory(package)
    if args.preflight_only:
        print(json.dumps({'model_requests_sent': False, 'expanded_scope': scope}, ensure_ascii=False))
        return
    if not args.prepare_only and (not (args.authorization_text or '').strip() or args.expected_scope_digest != scope['scope_digest']):
        parser.error('Native dispatch requires actual human authorization and this exact scope digest')
    if not args.out:
        parser.error('--out is required')
    lab = args.out.resolve()
    lab.mkdir(parents=True, exist_ok=False)
    project, evidence = lab / 'business', lab / 'evidence'
    base = project / '.agents/evolve-acceptance'
    profile, registered = base / 'profile', base / 'installed-source'
    for directory in (project, evidence, profile):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, registered)
    for name, body in scope['first_files'].items():
        (project / name).write_text(body)
    save(evidence / 'expanded-scope.json', scope)
    env = {**os.environ, 'CODEX_HOME': str(profile)}
    transport.shell(['codex', 'plugin', 'marketplace', 'add', str(registered), '--json'], env=env, cwd=project, log=evidence / 'marketplace.json')
    installed = transport.shell(['codex', 'plugin', 'add', 'evolve@evolve-local', '--json'], env=env, cwd=project, log=evidence / 'installation.json')
    cache = Path(installed['installedPath'])
    cache.resolve().relative_to(project)
    (project / '.codex').mkdir()
    (project / '.codex/config.toml').write_text('[plugins."evolve@evolve-local"]\nenabled=true\n')
    config = profile / 'config.toml'
    config.write_text(config.read_text().replace('enabled = true', 'enabled = false') +
        '\n[projects.' + json.dumps(str(project)) + ']\ntrust_level="trusted"\n')
    other = lab / 'other-project'
    other.mkdir()
    discovery = codex_skills(env, project, other)
    save(evidence / 'discovery.json', discovery)
    assert len(discovery[0]['skills']) == 8 and not discovery[1]['skills']
    for case, prompt in prompts.items():
        (evidence / (case + '-prompt.txt')).write_text(prompt + '\n' + transport.LIMITS)
    summary = {'package': str(package), 'registered_root': str(registered), 'cache': str(cache),
        'content_digest': scope['content_digest'], 'scope_digest': scope['scope_digest'],
        'model_requests_sent': False, 'automated_checks_passed': False, 'review_status': 'pending', 'passed': False, 'cases': []}
    save(evidence / 'summary.json', summary)
    if args.prepare_only:
        summary['preparation_status'] = 'installed_and_discovered_no_model_dispatch'
        save(evidence / 'summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False))
        return
    client = None
    try:
        summary['authorization'] = {'source': 'actual human reply in this chat', 'text': args.authorization_text}
        checker = checker_type(project, evidence, scope, cache, registered)
        client = transport.CodexSession(project, evidence)
        for case, prompt in prompts.items():
            checker.before(case)
            if hasattr(checker, 'context_for'):
                prompt += checker.context_for(case)
            if case == 'reexport':
                prompt += '\n本轮已保存的准确分析引用：' + json.dumps(checker.relation, ensure_ascii=False)
            (evidence / (case + '-actual-prompt.txt')).write_text(prompt + '\n' + transport.LIMITS)
            summary['model_requests_sent'] = True
            save(evidence / 'summary.json', summary)
            print(json.dumps({'case': case, 'state': 'started'}), flush=True)
            result = client.run(prompt, cache)
            observation = checker.after(case)
            save(evidence / (case + '-parent-observation.json'), observation)
            summary['cases'].append({'case': case, 'model_result': result, 'parent_observation': observation})
            save(evidence / 'summary.json', summary)
            print(json.dumps({'case': case, 'state': 'observed'}), flush=True)
        summary['automated_checks_passed'] = True
    except BaseException as error:
        summary['failure'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        if client:
            client.close()
        save(evidence / 'summary.json', summary)


if __name__ == '__main__':
    main()
