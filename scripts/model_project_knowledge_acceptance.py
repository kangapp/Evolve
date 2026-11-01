#!/usr/bin/env python3
"""Six fresh Codex sessions for project knowledge, required delivery and scoped facts."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import model_acceptance as transport
from model_data_acceptance import main, save

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'calc.py': 'def total(values):\n    return sum(values)\n',
    'navigation_only.py': '"""Reserved local navigation example; no runtime callers."""\n',
    'README.md': '# 整数计算示例\n\n目标：本地整数求和。当前 total 接受可迭代整数并返回总和。\n'
        '没有远端服务或持久化；异常类型和历史设计原因未调查。\n'
        '检查：python3 -B -m unittest test_calc -v。发现此命令不代表已经运行通过。\n',
    'legacy.md': '# 既有资料\n\n## 求和\n输入可迭代整数，返回总和；空输入为零。\n\n## 报告\n当前没有报告输出能力。\n',
    'test_calc.py': 'import unittest\nfrom calc import total\nclass Totals(unittest.TestCase):\n'
        '    def test_literals(self):\n        self.assertEqual(total([2,3]),5)\n'
        '        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n',
}
SUMMARY_TEST = 'import unittest\nfrom calc import summarize\nclass Summary(unittest.TestCase):\n'
SUMMARY_TEST += '    def test_literals(self):\n        self.assertEqual(summarize([2,3]),{"total":5,"count":2})\n'
SUMMARY_TEST += '        self.assertEqual(summarize([]),{"total":0,"count":0})\n'
SUMMARY_TEST += '        self.assertEqual(summarize(iter([-2,3])),{"total":1,"count":2})\n'

PROMPTS = {
    'survey': '使用 Evolve 完整梳理这个临时整数项目。只读业务，接入记录设施，登记 original 检查 '
        'python3 -B -m unittest test_calc -v（cwd=点、timeout=15），实际执行并保留结果。'
        '沿入口、业务和边界调查全部八视角，未知保持未知。准备 evolve/project.md（topic=project）、'
        'evolve/codemap.md（topic=code-navigation），及保留原文字节的 legacy.md 映射（kind=spec、'
        'topic=legacy、topics 的 totals 对应“求和”、reports 对应“报告”）。'
        'codemap 登记 calc.py、navigation_only.py、test_calc.py 的实际来源；正文引用准确代码路径 '
        '`navigation_only.py`，并用一个 Mermaid flowchart 解释真实 total 链路；图源不使用 navigation_only.py。'
        'project 登记 README.md 与 calc.py 的实际来源。其余文档按需，不生成空壳。'
        '候选 content 按应用后的正式正文撰写；候选、批准、检查、未渲染等本次流程状态只放观察和历史记录。'
        'legacy 只映射已经可靠的求和与无报告两项局部约定，scope 与四维 acceptance 对应该实际职责，'
        '完整规格、异常和验收缺口留在 survey，不要求改写原文或声称其已经是完整规格。'
        '本阶段只调查和提出具体候选，可记录候选检查，尚未实际渲染的 diagrams 保持 blocked；'
        '不批准、不应用正式文档，不调用 init.complete，不建立实施 Change。',
    'initial_delivery': '恢复上一轮调查和候选。下面控制侧依据本会话真实用户对完整临时验收的授权，'
        '给出本次准确候选的具体决定和真实 Mermaid 渲染证据；这不是声称人类逐字阅读了模型正文。'
        '先逐项核对来源、范围、四维内容和图文，候选检查通过后记录本次具体批准，按 owner 应用；'
        '全部目标就位后验收实际文档，调用 init.complete。保留真实未知，报告完成范围。'
        '业务和 legacy.md 原字节保持不变；不创建业务 Change。',
    'implement': '新增需求：calc.py 增加 summarize(values)，接受可迭代整数（包括单次迭代器），返回 '
        '{"total":总和,"count":数量}；空输入为 {"total":0,"count":0}。保留 total 的既有行为。'
        '控制侧新增的 test_summary.py 和原测试只读。登记 summary 检查 '
        'python3 -B -m unittest test_summary -v，cwd=点、timeout=15。'
        '使用 Evolve 恢复相关知识，呈现具体方案；本轮明确接受上述边界内方案和必要知识交付。'
        '方案 scope 仅 calc.py；knowledge_impact 声明 project、code-navigation、totals 为 required，'
        '目标分别 evolve/project.md、evolve/codemap.md、evolve/specs/totals/spec.md；reports 为 unchanged。'
        '通过 apply 实现 calc.py，运行 original 与 summary，真实完成逐 AC、规格和规范验收。'
        '准备三个必需知识候选：新 spec 迁入 legacy 的 totals 主题，给准确 replaces，原 reports 仍沿用；'
        'project 与 codemap 反映实际已验收能力，来源摘要采用当前现场。正文需要明确输入、结果、'
        '异常或尚未调查的边界、独立预期；地图保留辅助文件的路径导航。'
        '文件路径持续使用行内代码，链接显示文字若为文件路径也使用行内代码；普通正文中的路径不属于自动维护范围。'
        '原地图的 Mermaid 按新链路增量更新或补图，并声明实际渲染判据；本阶段图形未渲染保持 blocked。'
        '本阶段不批准、不应用正式知识，也不封存；准确报告实现完成而必需文档待交付。',
    'finish': '恢复本次需求和三个必需知识候选。按下面控制侧的准确候选决定和真实渲染证据，'
        '核对后进行候选检查、具体批准、按 owner 应用及实际文档验收。'
        '完整新规格接替 legacy.md 的 totals 主题，reports 和旧文件保留。'
        '核对实现和原测试，记录每项 sync.assess（required→updated、reports→unchanged），'
        '完成最新实际验收和 archive.close。必要修正在原范围继续，不能把必需知识改为 followup。',
    'facts': '控制侧已将 navigation_only.py 原字节移动到 src/navigation_only.py，旧位置消失。'
        '本次具体授权只允许用 sync.facts 自动维护 evolve/codemap.md，effect_kinds 除 project_records、'
        'knowledge 外含 facts_maintenance，fact_moves 精确为 '
        '[{"from_path":"navigation_only.py","to_path":"src/navigation_only.py"}]。'
        '从 status 取得文档当前注册摘要，用该方法保留实际来源、受限差异和自动事实维护依据；'
        '本轮不另批准语义候选，不改变 Mermaid 图源或其他正文。完成后核对结果。',
    'conflict': '控制侧先在 codemap 追加了真实外部编辑，再将辅助文件移到 lib/navigation_only.py。'
        '本轮仍只具体授权 sync.facts 更新 evolve/codemap.md，准确移动为 '
        '[{"from_path":"src/navigation_only.py","to_path":"lib/navigation_only.py"}]。'
        '使用当前正式注册摘要作为 expected_digest（不是外部编辑的现场摘要），执行一次 sync.facts。'
        '预期真实 FILE_CONFLICT，保留外部正文及原应用历史；不要采用外部正文、重建候选或改用其他方法绕过。'
        '如实报告受阻和所保留内容。',
}


def sha(content):
    return hashlib.sha256(content).hexdigest()


def scope_for(package):
    from evolve_core.package import check_package, canonical
    manifest = check_package(package)
    if (manifest['schema_version'], manifest['protocol_version']) != (4, 17):
        raise ValueError('Project knowledge acceptance requires schema 4 / protocol 17')
    body = {'slice': 'project-knowledge', 'host': 'codex', 'first_files': FILES,
        'package_version': manifest['package_version'], 'content_digest': manifest['content_digest'],
        'protocol_version': 17, 'schema_version': 4, 'cases': PROMPTS,
        'fresh_conversation_per_case': True, 'maximum_sessions': 6,
        'business_write_paths': ['calc.py'], 'knowledge_write_paths': ['evolve/**/*.md'],
        'readonly_paths': ['README.md', 'legacy.md', 'test_calc.py', 'test_summary.py'],
        'parent_mutations': ['Add test_summary.py before implement',
            'Move navigation_only.py to src/ before facts',
            'Append external codemap marker and move src/navigation_only.py to lib/ before conflict',
            'Render actual candidate Mermaid using the separately installed host renderer before each specific decision'],
        'renderer': os.environ.get('EVOLVE_ACCEPTANCE_MMDC'),
        'model_selection': 'model/list isDefault, native account authentication; no credential copying',
        'runner_files': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in (
            Path(__file__).resolve(), ROOT / 'scripts/model_data_acceptance.py',
            ROOT / 'scripts/model_acceptance.py', ROOT / 'scripts/verify_hosts.py')}}
    return {**body, 'scope_digest': sha(canonical(body))}


class Checks:
    def __init__(self, project, evidence, scope, package, registered):
        from evolve_core.privacy import redact
        transport.digest, transport.redact = sha, redact
        self.project, self.evidence, self.scope = project, evidence, scope
        self.package, self.registered = package, registered
        self.bridge, self.bridge_digest = transport.prepare_headless_bridge(project, package, evidence)
        self.settings = {str(p): p.read_bytes() for p in (
            project / '.codex/config.toml', project / '.agents/evolve-acceptance/profile/config.toml')}
        self.initial = {name: body.encode() for name, body in FILES.items()}
        self.next_case = 0

    def rows(self):
        from evolve_core.reading import history_snapshot
        if not (self.project / 'evolve/history.db').exists():
            return {}
        with history_snapshot(self.project) as (c, _):
            return {table: {r['id']: dict(r) for r in c.execute('SELECT * FROM ' + table)} for table in (
                'phase_runs', 'verifications', 'knowledge_proposals', 'spec_applications', 'artifact_versions', 'events',
                'changes', 'tasks', 'operations')}

    def state(self):
        from evolve_core.reading import current_state
        return current_state(self.project)

    def before(self, case):
        if case != list(PROMPTS)[self.next_case]:
            raise AssertionError('Native cases must run in their exact declared order')
        if case == 'implement':
            (self.project / 'test_summary.py').write_text(SUMMARY_TEST)
        elif case in ('facts', 'conflict'):
            old, new = ('navigation_only.py', 'src/navigation_only.py') if case == 'facts' else ('src/navigation_only.py', 'lib/navigation_only.py')
            (self.project / new).parent.mkdir(exist_ok=True)
            (self.project / old).rename(self.project / new)
            if case == 'conflict':
                path = self.project / 'evolve/codemap.md'
                path.write_bytes(path.read_bytes() + '\n外部编辑保留标记：不可被旧事实维护覆盖。\n'.encode())
            self.before_map = (self.project / 'evolve/codemap.md').read_bytes()
        self.before_calc = (self.project / 'calc.py').read_bytes()
        self.before_rows = self.rows()
        self.before_receipts = set((self.project / '.evolve-local/control/requests').glob('cli-receipt-*.json'))

    def candidates(self):
        from evolve_core.knowledge_proposals import metadata, reference
        from evolve_core.reading import history_snapshot
        result = []
        with history_snapshot(self.project) as (c, _):
            for p in c.execute("SELECT * FROM knowledge_proposals WHERE state IN ('proposed','approved') AND applied_operation_id IS NULL ORDER BY rowid"):
                meta = metadata(p)
                content = c.execute('SELECT content FROM blobs WHERE digest=?', (p['candidate_digest'],)).fetchone()[0].decode()
                result.append({'proposal': reference(p), 'path': p['target_path'], 'owner': p['owner_skill'],
                    'content': content, 'document': meta.get('document'), 'acceptance': meta['acceptance']})
        return result

    def render(self, candidates, case):
        renderer = self.scope['renderer']
        if not renderer or not Path(renderer).is_file():
            raise RuntimeError('Actual Mermaid renderer is unavailable; preserve blocked diagrams')
        exports = self.project / '.evolve-local/exports'
        exports.mkdir(exist_ok=True)
        config = exports / 'puppeteer.json'
        config.write_text(json.dumps({'executablePath': '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}))
        observations = []
        for item in candidates:
            for index, graph in enumerate(re.findall(r'```mermaid\s*\n(.*?)```', item['content'], re.S)):
                stem = case + '-' + item['proposal']['candidate_digest'][:12] + '-' + str(index)
                source, output = exports / (stem + '.mmd'), exports / (stem + '.png')
                source.write_text(graph)
                result = subprocess.run([renderer, '-p', str(config), '-i', str(source), '-o', str(output)],
                    cwd=self.project, capture_output=True, text=True, timeout=60)
                observation = {'candidate_digest': item['proposal']['candidate_digest'], 'source': str(source),
                    'source_digest': sha(source.read_bytes()), 'output': str(output), 'exit_code': result.returncode,
                    'stdout': result.stdout, 'stderr': result.stderr,
                    'output_digest': sha(output.read_bytes()) if output.exists() else None}
                save(self.evidence / (stem + '-render.json'), observation)
                if result.returncode or not output.is_file():
                    raise RuntimeError('Actual Mermaid rendering failed; inspect retained renderer result')
                observations.append(observation)
        return observations

    def context_for(self, case):
        common = '\n本次全部 Evolve CLI 调用经只读桥接脚本：python3 -B ' + str(self.bridge) + \
            ' <action> [--method <method>] [--request <JSON文件>]；不要直接调用 runtime。请求与辅助脚本仅写 '
        common += str(self.project / '.evolve-local/control/requests') + '。桥接输出 receipt 路径，可读取完整真实 JSON，保留原 exit_code。'
        common += '业务和正式文档均经所属 Evolve 动作写入；不要直接编辑数据库、测试、插件缓存、桥接脚本或宿主设置。'
        if case in ('initial_delivery', 'finish'):
            candidates = self.candidates()
            expected = 3
            if len(candidates) != expected:
                raise AssertionError('Expected three actual pending candidates before the precise controlled decision')
            context = {'decision': 'Approve these exact candidates after checking the actual sources and content.',
                'decision_source': 'controlled-specific-decision under the actual user authorization to implement and fully accept in Codex',
                'candidates': candidates, 'actual_render_observations': self.render(candidates, case)}
            save(self.evidence / (case + '-specific-decisions.json'), context)
            common += '\n准确具体决定及真实渲染证据：\n' + json.dumps(context, ensure_ascii=False)
            common += '\n读取实际渲染图片核对图文关系；图能渲染不替代内容一致性检查。'
        return common

    def after(self, case):
        from evolve_core.package import check_package
        from evolve_core.reading import history_snapshot
        for package in (self.package, self.registered):
            if check_package(package)['content_digest'] != self.scope['content_digest']:
                raise AssertionError('Actual installed package changed')
        if sha(self.bridge.read_bytes()) != self.bridge_digest:
            raise AssertionError('Native model changed the acceptance bridge')
        for name, content in self.settings.items():
            if Path(name).read_bytes() != content:
                raise AssertionError('Native model changed isolated host configuration')
        for name in ('README.md', 'legacy.md', 'test_calc.py'):
            if (self.project / name).read_bytes() != self.initial[name]:
                raise AssertionError('Read-only original changed: ' + name)
        if (self.project / 'test_summary.py').exists() and (self.project / 'test_summary.py').read_bytes() != SUMMARY_TEST.encode():
            raise AssertionError('Independent summary tests changed')
        if case != 'implement' and (self.project / 'calc.py').read_bytes() != self.before_calc:
            raise AssertionError('A knowledge-only stage changed the business implementation')
        expected_files = set(FILES)
        if case in ('implement', 'finish', 'facts', 'conflict'):
            expected_files.add('test_summary.py')
        if case in ('facts', 'conflict'):
            expected_files.remove('navigation_only.py')
            expected_files.add('src/navigation_only.py' if case == 'facts' else 'lib/navigation_only.py')
        actual_files = set()
        excluded = {'evolve', '.evolve-local', '.agents', '.codex', '.git', '__pycache__'}
        for path in self.project.rglob('*'):
            relative = path.relative_to(self.project)
            if not set(relative.parts) & excluded and path.is_file():
                if path.is_symlink():
                    raise AssertionError('Business fixture acquired a symbolic alias')
                actual_files.add(relative.as_posix())
        if actual_files != expected_files:
            raise AssertionError('Unexpected business files: ' + repr(actual_files ^ expected_files))
        rows = self.rows()
        with history_snapshot(self.project) as (c, _):
            if c.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0] or any(r['status'] == 'started' for r in rows['phase_runs'].values()):
                raise AssertionError('Native case left an unfinished operation')
        for table in ('verifications', 'artifact_versions', 'events'):
            if any(rows[table].get(key) != row for key, row in self.before_rows.get(table, {}).items()):
                raise AssertionError('Historical facts changed: ' + table)
        state = self.state()
        knowledge = state['knowledge']
        docs = {d['topic']: d for d in knowledge['documents'] if d['active']}
        receipts = []
        for path in set((self.project / '.evolve-local/control/requests').glob('cli-receipt-*.json')) - self.before_receipts:
            receipts.append(json.loads(path.read_text()))
        if not receipts:
            raise AssertionError('No actual CLI receipts from the native model')
        if case == 'survey':
            if not knowledge['survey'] or len(knowledge['survey']['coverage']) != 8 or knowledge['initial_delivery']['status'] != 'pending':
                raise AssertionError('The actual eight-perspective survey is missing or falsely complete')
            if rows['spec_applications'] or rows['changes'] or len(self.candidates()) != 3:
                raise AssertionError('Candidate-only stage changed formal or business state')
            candidates = {p['path']: p for p in self.candidates()}
            codemap = candidates.get('evolve/codemap.md', {})
            if ('```mermaid' not in codemap.get('content', '')
                    or '`navigation_only.py`' not in codemap.get('content', '')
                    or not {'calc.py', 'navigation_only.py', 'test_calc.py'}.issubset(
                        {s['path'] for s in (codemap.get('document') or {}).get('sources', [])})):
                raise AssertionError('Required actual map, navigation source and diagram are missing')
            if any((self.project / p).exists() for p in ('evolve/project.md', 'evolve/codemap.md')):
                raise AssertionError('Formal text was written outside its approved application')
        elif case == 'initial_delivery':
            if knowledge['initial_delivery']['status'] != 'completed' or set(docs) != {'project', 'code-navigation', 'totals', 'reports'}:
                raise AssertionError('Complete initial delivery and partial legacy navigation are required')
            if any(d['applicability'] != 'matching_local_bytes' for d in docs.values()):
                raise AssertionError('Initial documents are not currently applicable')
        elif case in ('implement', 'finish'):
            check = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_calc', 'test_summary', '-v'],
                cwd=self.project, capture_output=True, text=True, timeout=20)
            save(self.evidence / (case + '-independent-literals.json'), {'exit_code': check.returncode, 'stdout': check.stdout, 'stderr': check.stderr})
            if check.returncode or len(rows['changes']) != 1:
                raise AssertionError('The independently specified integer results or actual Change are missing')
            change = next(iter(rows['changes'].values()))
            if case == 'implement':
                if change['state'] == 'archived' or len(self.candidates()) != 3 or len(rows['spec_applications']) != 3:
                    raise AssertionError('Required knowledge must remain pending after code-only delivery')
            elif (change['state'] != 'archived' or docs['totals']['path'] != 'evolve/specs/totals/spec.md'
                    or docs['reports']['path'] != 'legacy.md' or self.candidates()):
                raise AssertionError('Actual required knowledge, partial migration and closure are incomplete')
        elif case == 'facts':
            expected = self.before_map.decode().replace('`navigation_only.py`', '`src/navigation_only.py`')
            expected = expected.replace('](../navigation_only.py)', '](../src/navigation_only.py)').encode()
            if (self.project / 'evolve/codemap.md').read_bytes() != expected:
                raise AssertionError('Scoped facts changed more than the authorized exact code path')
            if not any(r['response'].get('ok') and r['response'].get('data', {}).get('authority') == 'scoped_facts'
                    and r['response']['data'].get('factual_verification', {}).get('status') == 'passed' for r in receipts):
                raise AssertionError('No actual successful automatic facts result')
        elif case == 'conflict':
            if (self.project / 'evolve/codemap.md').read_bytes() != self.before_map:
                raise AssertionError('External formal text was overwritten')
            if len(rows['spec_applications']) != len(self.before_rows['spec_applications']):
                raise AssertionError('A conflict acquired a fabricated new application')
            if not any(r['exit_code'] != 0 and r['response'].get('error', {}).get('code') == 'FILE_CONFLICT' for r in receipts):
                raise AssertionError('No authentic FILE_CONFLICT receipt from sync.facts')
        self.next_case += 1
        return {'case': case, 'passed_parent_checks': True, 'counts': {k: len(v) for k, v in rows.items()},
            'actual_cli_receipts': len(receipts), 'semantic_trace_review': 'pending',
            'knowledge_topics': {k: v['path'] for k, v in docs.items()}, 'initial_delivery': knowledge['initial_delivery']}


if __name__ == '__main__':
    main(scope_factory=scope_for, checker_type=Checks, prompts=PROMPTS, description=__doc__)
