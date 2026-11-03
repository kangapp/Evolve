#!/usr/bin/env python3
"""Four fresh Codex conversations for real engineering, knowledge and closure."""
import difflib
import json
import os
from pathlib import Path
import sys

import model_acceptance as transport
from model_data_acceptance import main, save
from engineering_smoke import READONLY, Runtime, checks, fixture_files, prepare_project, sha

ROOT = Path(__file__).resolve().parents[1]
FILES = {'ACCEPTANCE.md': '# 受控工程验收\n\n仅操作本临时 Next 工程。原测试、页面、依赖和工具配置只读；不部署、不提交。\n'}
PROMPTS = {
    'implement': '使用 Evolve 核对已有临时工程、检查与正式 codemap。目标是将 total 的实现移到 '
        'src/math/total.ts，src/total.ts 保留相同公开导出，原 Node 测试及 Next 页面继续工作；'
        '新实现用显式循环求和，原整数数组语义保持。形成准确完整复杂方案，两项 Task：'
        'CORE 仅修改 src/total.ts、src/math/total.ts，pre_refactor，保留原断言与 READONLY 输入；'
        '使用已登记 environment、unit、types、build，前后原检查真实执行。'
        'MAP 仅负责 sync 更新 evolve/codemap.md（topic=code-navigation），required_deliverables 为该文档，'
        '依赖 CORE verification_passed，context_paths 明确消费两个新源码。MAP 明确 review_policy=self_allowed；'
        'CORE 与整项 review_policy=independent。knowledge_impact 的 code-navigation 为 required；'
        'knowledge_review 按八类实际视角判断，codemap changed 必须落实 MAP，其余按现场依据。'
        '本轮已明确接受上述准确边界的方案，授权在临时项目连续推进 CORE 的前后证明和实施；'
        '原 READONLY、依赖、页面、桥接和宿主设置只读。不要验收 CORE、不要实施 MAP 或封存。'
        '结束时报告实际阶段及下一 Skill，保留真实失败，不改原断言换通过。',
    'independent_core': '这是新的独立 Codex 会话。先恢复准确工作与 CORE 现场，自行阅读源码、原断言、'
        '方案及实际前后证据，按接受的 independent 要求完成 CORE 的规格及规范审查和逐 AC 验收；'
        'mode=independent，source 用 native-engineering:independent_core，independence_basis 如实说明 '
        'CORE 由前一新会话实施，本会话没有修改业务文件，原生轨迹另有真实 thread ID 可核对。'
        '配置允许的 types/build 可以引用同输入实际后检查，不将引用称为本次执行。'
        'CORE 验收通过后仅为 MAP 提出具体 sync 候选：地图反映 app/page.tsx → src/total.ts 公开门面 '
        '→ src/math/total.ts 实现，包含原测试、真实来源及边界；不要批准或应用正式文档。'
        '另从本次实际 CORE apply／verify 来源记录一条有界经验候选：facade extraction 后应核对新实现、'
        '门面与调用者，再更新 codemap；记录适用范围和限制，不晋升正式规则。不要整项验收或封存。',
    'knowledge': '恢复 MAP 与下方控制侧准确候选决定；本轮在受控临时验收范围接受该具体文档。'
        '先检索前一轮 facade extraction 经验，核对 MAP 范围后记录实际 adopted 决定和 influence：'
        '具体影响源码引用核对及 MAP 文档验收，affected_items 指向真实 Task／AC／检查。'
        '随后检查候选、记录下方具体决定、由 sync owner 应用，并验收实际正式文档。'
        '完成 MAP 自身 verify.run，mode=self，如实标明本会话的正式交付自审；MAP 的 self_allowed 不充当 '
        'CORE 或整项独立审查。随后用采用之后同一 MAP Task 定义的实际 verify.run 来源反馈效果；'
        '可以记录 unknown，解释无法归因，不能用 standalone verify.knowledge 冒充 Task 效果。'
        '不要修改业务、原断言或工具配置，不做最终整项验收或封存。',
    'finish': '这是另一新的 Codex 会话，先独立阅读当前全部源码、原测试、两项任务、正式 codemap 和真实证据。'
        '按接受的 independent 要求完成整项规格及规范审查和每项 AC，mode=independent，'
        'source=native-engineering:finish，independence_basis 如实说明前面业务与正式交付由其他新会话完成。'
        '本次明确重新运行 types 与 build，在最终 verify.run 给 fresh_checks，其他检查按配置；'
        '核对八类知识及 required code-navigation 的实际交付与目标核验，必要复验后封存。'
        '随后使用 maintain.export kind=review_copy 导出本次整体验收的原回执副本，查看 materials，'
        '按准确 plan／apply 仅清理本次新建、已结束、无引用、可重建的辅助副本；'
        '本轮完整授权覆盖该具体受控副本整理，不处理手工、未知、候选、失败或恢复资料。'
        '保留控制侧 manual.md，核对原回执不变。无新经验可有依据地记录 no_new_learning。'
        '不修改业务、正式正文或原断言，最终明确整体完成状态、剩余事项与接手入口。',
}


def scope_for(package):
    from evolve_core.package import canonical, check_package
    manifest = check_package(package)
    if (manifest['schema_version'], manifest['protocol_version']) != (4, 18):
        raise ValueError('Engineering acceptance requires schema 4 / protocol 18')
    body = {'slice': 'engineering-closure', 'host': 'codex', 'first_files': FILES,
        'package_version': manifest['package_version'], 'content_digest': manifest['content_digest'],
        'schema_version': 4, 'protocol_version': 18, 'cases': PROMPTS,
        'maximum_sessions': 4, 'fresh_conversation_per_case': True,
        'business_write_paths': ['src/total.ts', 'src/math/total.ts'],
        'knowledge_write_paths': ['evolve/codemap.md'], 'readonly_paths': [*READONLY, *FILES],
        'fixture_files': {name: sha(content) for name, content in fixture_files().items()},
        'checks': checks(), 'fixture_install': 'npm ci --offline --ignore-scripts --no-audit --no-fund',
        'parent_mutations': ['Copy fixed fixture into disposable project, install from npm cache and build baseline',
            'Connect exact checks and establish the fixed temporary old codemap by its actual formal-owner chain',
            'Provide the precise MAP candidate and diff under actual full temporary-acceptance authorization',
            'Create manual.md before final material cleanup; preserve it'],
        'model_selection': 'Native model/list isDefault; account authentication remains in the host',
        'runner_files': {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in (
            Path(__file__).resolve(), ROOT / 'scripts/engineering_smoke.py', ROOT / 'scripts/model_acceptance.py',
            ROOT / 'scripts/model_data_acceptance.py', ROOT / 'scripts/verify_hosts.py')}}
    return {**body, 'scope_digest': sha(canonical(body))}


class Checks:
    def __init__(self, project, evidence, scope, package, registered):
        from evolve_core.reading import history_snapshot
        self.project, self.evidence, self.scope, self.package, self.registered = project, evidence, scope, package, registered
        os.environ['NEXT_TELEMETRY_DISABLED'] = '1'
        self.original = prepare_project(project, evidence, offline=True)
        self.original.update({name: (project / name).read_bytes() for name in FILES})
        self.receipts = project / '.evolve-local/control/requests'
        self.receipts.mkdir(parents=True, exist_ok=True)
        (self.receipts / 'headless-staging.json').write_text('{"purpose":"controlled request and receipt staging"}')
        self.base = project / '.agents/evolve-acceptance'
        self.bridge = self.base / 'engineering_bridge.py'
        template = transport.HEADLESS_BRIDGE.replace('__RUNTIME__', repr(str(package / 'runtime/evolve.py'))).replace('__PROJECT__', repr(str(project)))
        template = template.replace("'error':response.get('error'),", "'workflow':response.get('workflow'),'error':response.get('error'),")
        self.bridge.write_text(template)
        self.bridge_digest = sha(self.bridge.read_bytes())
        transport.digest = sha
        auth = {'source': 'actual user full controlled-acceptance goal; deterministic temporary baseline',
            'text': '按批次逐步实施完整方案，并通过codex完成最终验收。本段只建立已固定的临时工程检查和准确旧代码地图。',
            'effect_kinds': ['project_records', 'knowledge', 'checks'], 'paths': ['evolve/codemap.md']}
        self.runtime = Runtime(package, project, evidence, auth)
        self.runtime.history_snapshot = history_snapshot
        self.seed()
        self.settings = {str(path): path.read_bytes() for path in (project / '.codex/config.toml', self.base / 'profile/config.toml')}
        self.next_case = 0

    def rows(self):
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection, _):
            return {name: {row['id']: dict(row) for row in connection.execute('SELECT * FROM ' + name)}
                for name in ('changes', 'tasks', 'phase_runs', 'events', 'verifications', 'artifact_versions', 'knowledge_proposals', 'resource_claims')}

    def seed(self):
        call = self.runtime.call
        call('init', {'checks': self.scope['checks']})
        self.old_codemap = '# 代码地图\n\n适用范围：固定的本地整数数组求和工程。\n\n## 范围\n\n只覆盖页面、公开 total 及原字面测试；没有持久化或远端业务操作。\n\n## 运行入口\n\n`app/page.tsx` 显示总计，`app/layout.tsx` 提供页面外壳；`tests/total.test.ts` 为 Node 测试入口。\n\n## 模块职责\n\n`src/total.ts` 同时提供公开 total 和 reduce 求和实现；页面及原测试复用该函数。\n\n## 关键链路\n\n页面与原测试调用 total，输入整数数组并返回总和；空数组返回零。\n\n## 数据与依赖\n\nNext／React 页面与 Node 测试共用函数；依赖及脚本由 `package.json` 固定，类型约束见 `tsconfig.json`。\n\n## 检查与修改入口\n\nnpm run test／typecheck／build 是当前检查入口；改动 total 时保留原独立断言和页面输入。\n\n## 未覆盖范围\n\n未约定其他输入类型、非有限数、浏览器或生产环境行为；发现检查入口不等于已经执行所有检查。\n\n## 来源与关联\n\n依据当前页面、原实现、配置和独立测试的实际源码；后续模块归属变化需要复核本地图。\n'
        criteria = [{'key': key, 'text': value} for key, value in (
            ('structure', '入口、职责、链路、边界和来源均有具体正文。'),
            ('sources', '引用当前页面、原实现和独立测试，不引用未观察执行。'),
            ('consistency', '只说明整数数组 total 的既有实现与边界。'),
            ('usefulness', '读者能找到入口、实现和原测试。'))]
        sources = [{'path': name, 'expected_digest': sha((self.project / name).read_bytes())}
                   for name in ('app/page.tsx', 'app/layout.tsx', 'src/total.ts', 'tests/total.test.ts', 'package.json', 'tsconfig.json')]
        candidate = call('init', {'path': 'evolve/codemap.md', 'expected_digest': None, 'content': self.old_codemap,
            'topic': 'code-navigation', 'reason': 'Establish exact temporary baseline before extraction.',
            'presentation': {'source': 'controlled-fixed-initial-codemap', 'text': self.old_codemap}, 'acceptance': criteria,
            'document': {'kind': 'codemap', 'topic': 'code-navigation', 'scope': 'Only the fixed local integer-array fixture.',
                         'mode': 'managed', 'sources': sources}}, method='baseline.propose')
        ref = {key: candidate[key] for key in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}
        observations = [{'criterion_key': item['key'], 'status': 'passed', 'observer': 'controlled-parent-fixed-source-inspection',
                         'basis': item['text']} for item in criteria]
        call('sync', {'proposal': ref, 'observations': observations}, method='check')
        decision = call('sync', {'decisions': [{'proposal': ref, 'decision': 'approved', 'source': 'actual controlled fixture scope',
            'text': self.old_codemap, 'reason': 'Exact temporary baseline with fixed source bytes; not real business knowledge.'}]}, method='review')
        applied = call('init', {'proposal': ref, 'approved_event_id': decision['decisions'][0]['decision_event_id']}, method='baseline.apply')
        call('verify', {'application_id': applied['application_id'], 'observations': observations}, method='knowledge')

    def before(self, case):
        if case != list(PROMPTS)[self.next_case]:
            raise AssertionError('Run only the frozen ordered cases')
        if case == 'finish':
            path = self.project / '.evolve-local/review/manual.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Parent manual observation; preserve this unknown material.\n')
        self.before_rows = self.rows()
        self.before_business = self.business_snapshot()
        self.before_code = {name: (self.project / name).read_bytes() if (self.project / name).exists() else None
                            for name in self.scope['business_write_paths']}
        self.before_receipts = set(self.receipts.glob('cli-receipt-*.json'))
        events = self.evidence / 'model-events.jsonl'
        self.event_offset = events.stat().st_size if events.exists() else 0

    def business_snapshot(self):
        result = {}
        excluded = {'.next', 'node_modules', '.git', '.codex', '.agents', 'evolve', '.evolve-local', '__pycache__'}
        for directory, subdirs, names in os.walk(self.project):
            subdirs[:] = [name for name in subdirs if name not in excluded]
            for name in names:
                if not name.endswith(('.tsbuildinfo', '.pyc', '.pyo')):
                    path = Path(directory) / name
                    result[path.relative_to(self.project).as_posix()] = sha(path.read_bytes())
        return result

    def context_for(self, case):
        context = '\n准确只读输入：' + json.dumps(self.scope['readonly_paths'], ensure_ascii=False)
        context += '\n全部 Evolve CLI 经控制侧桥接 python3 -B ' + str(self.bridge) + \
            ' <action> [--method <method>] [其余CLI参数] 调用。桥接只保存真实控制回执，返回准确 receipt 路径和 workflow；可读全文。' \
            '写请求放 .evolve-local/control/requests，按公开协议准备，不阅读运行时源码，不修改桥接、宿主配置、安装包或检查定义。'
        if case == 'knowledge':
            from evolve_core.reading import history_snapshot
            with history_snapshot(self.project) as (connection, _):
                rows = connection.execute("SELECT * FROM knowledge_proposals WHERE target_path='evolve/codemap.md' ORDER BY rowid DESC").fetchall()
                candidate = rows[0]
                body = connection.execute('SELECT content FROM blobs WHERE digest=?', (candidate['candidate_digest'],)).fetchone()[0].decode()
            assert body != self.old_codemap and 'src/math/total.ts' in body and 'src/total.ts' in body
            ref = {key: candidate[key] for key in ('candidate_digest', 'expected_digest')}
            ref.update(proposal_id=candidate['id'], proposal_version=candidate['version'])
            diff = '\n'.join(difflib.unified_diff(self.old_codemap.splitlines(), body.splitlines(), fromfile='old codemap', tofile='candidate codemap'))
            decision = {'proposal': ref, 'decision': 'approved',
                'source': 'controlled parent exact candidate decision under actual user full temporary-acceptance goal',
                'text': body, 'reason': 'Exact temporary map names the actual facade and new implementation; original tests and scope remain. This does not claim a human read every generated word.'}
            save(self.evidence / 'exact-map-decision.json', {'decision': decision, 'diff': diff})
            context += '\n本次准确候选差异：\n' + diff + '\n本次具体决定：\n' + json.dumps(decision, ensure_ascii=False)
        return context

    def after(self, case):
        from evolve_core.package import check_package
        for package in (self.package, self.registered):
            assert check_package(package)['content_digest'] == self.scope['content_digest']
        assert sha(self.bridge.read_bytes()) == self.bridge_digest
        assert all(Path(name).read_bytes() == content for name, content in self.settings.items())
        assert all((self.project / name).read_bytes() == content for name, content in self.original.items())
        if case != 'implement':
            assert all(((self.project / name).read_bytes() if (self.project / name).exists() else None) == content
                       for name, content in self.before_code.items())
        business = self.business_snapshot()
        changed = {name for name in set(business) | set(self.before_business) if business.get(name) != self.before_business.get(name)}
        assert changed.issubset(set(self.scope['business_write_paths']) if case == 'implement' else set()), 'Unexpected business file change'
        rows = self.rows()
        assert not rows['resource_claims'] and all(row['status'] != 'started' for row in rows['phase_runs'].values())
        for table in ('phase_runs', 'events', 'verifications', 'artifact_versions'):
            assert all(rows[table].get(key) == value for key, value in self.before_rows[table].items()), 'Saved history changed'
        receipts = [json.loads(path.read_text()) for path in set(self.receipts.glob('cli-receipt-*.json')) - self.before_receipts]
        assert receipts and all(item['response'].get('workflow', {}).get('next_steps') for item in receipts)
        changes = list(rows['changes'].values())
        assert len(changes) == 1 and changes[0]['complexity'] == 'complex'
        tasks = {json.loads(row['definition_json'])['local_key']: row for row in rows['tasks'].values()
                 if row['revision_id'] == changes[0]['current_revision']}
        assert set(tasks) == {'CORE', 'MAP'}
        core, mapping = (json.loads(tasks[key]['definition_json']) for key in ('CORE', 'MAP'))
        assert core.get('pre_refactor') is True and core.get('review_policy') == 'independent'
        assert set(core['scope']) == set(self.scope['business_write_paths'])
        assert set(READONLY).issubset(core.get('preservation_inputs', []))
        assert mapping.get('responsible_action') == 'sync' and mapping.get('review_policy') == 'self_allowed'
        assert mapping['scope'] == ['evolve/codemap.md']
        assert any(item['upstream_task'] == 'CORE' and item['condition_kind'] == 'verification_passed' for item in mapping['dependencies'])
        recent = [row for key, row in rows['phase_runs'].items() if key not in self.before_rows['phase_runs']]
        results = [json.loads(row['result_json']) for row in recent if row['result_json']]
        if case == 'implement':
            assert tasks['CORE']['state'] == 'done' and tasks['MAP']['state'] == 'todo'
            proof = json.loads(tasks['CORE']['result_json'])['preservation']
            assert proof['status'] == 'passed'
            assert (self.project / 'src/math/total.ts').is_file()
            assert not any(row['change_id'] == changes[0]['id'] for row in rows['verifications'].values())
        elif case == 'independent_core':
            assert any(row['status'] == 'passed' and json.loads(row['items_json']).get('task_id') == tasks['CORE']['id'] for row in rows['verifications'].values())
            assert any(item.get('checks') and {'types', 'build'}.issubset({check['check_id'] for check in item['checks'] if check.get('reused')}) for item in results)
            assert (self.project / 'evolve/codemap.md').read_text() == self.old_codemap
            assert any(item.get('kind') == 'experience' for item in results)
        elif case == 'knowledge':
            assert tasks['MAP']['state'] == 'done'
            assert 'src/math/total.ts' in (self.project / 'evolve/codemap.md').read_text()
            assert any(item.get('kind') == 'decision' and item.get('decision') == 'adopted' and item.get('influence') for item in results)
            assert any(item.get('kind') == 'feedback' and item.get('outcome') in ('unknown', 'helped', 'not_helped') for item in results)
        else:
            assert changes[0]['state'] == 'archived' and all(row['state'] == 'done' for row in tasks.values())
            assert any(item.get('outcome') == 'review_cleanup_completed' for item in results)
            assert (self.project / '.evolve-local/review/manual.md').read_text() == 'Parent manual observation; preserve this unknown material.\n'
            whole = [row for row in rows['verifications'].values() if row['change_id'] == changes[0]['id']
                     and json.loads(row['items_json']).get('verification_scope') == 'change']
            assert whole and whole[-1]['status'] == 'passed'
            details = json.loads(whole[-1]['items_json'])
            assert all(item['mode'] == 'independent' for item in details['review_provenance'])
            assert all(item.get('executed') for item in details['checks'] if item['check_id'] in ('types', 'build'))
        if case != 'finish':
            assert changes[0]['state'] != 'archived'
        messages, threads, source_reads = [], set(), []
        for line in (self.evidence / 'model-events.jsonl').read_bytes()[self.event_offset:].decode().splitlines():
            event = json.loads(line)
            params = event.get('params', {})
            if params.get('threadId'):
                threads.add(params['threadId'])
            item = params.get('item', {})
            if event.get('method') == 'item/completed' and item.get('type') == 'commandExecution' and '/runtime/evolve_core/' in item.get('command', ''):
                source_reads.append(item['command'])
            if event.get('method') == 'item/completed' and item.get('type') == 'agentMessage':
                messages.append(item.get('text', ''))
        save(self.evidence / (case + '-visible-messages.json'), messages)
        assert not source_reads, 'Ordinary engineering workflow must use public routing and protocol: ' + repr(source_reads)
        assert messages and '[Evolve' in messages[-1] and any('[Evolve' in text for text in messages[:-1])
        self.next_case += 1
        return {'case': case, 'passed_parent_checks': True, 'actual_cli_receipts': len(receipts),
                'observed_thread_ids': sorted(threads), 'semantic_trace_review': 'pending'}


if __name__ == '__main__':
    main(scope_factory=scope_for, checker_type=Checks, prompts=PROMPTS, description=__doc__)
