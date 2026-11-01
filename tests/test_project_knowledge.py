"""Project knowledge is observed through the public CLI and actual project files."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = '''# 示例项目

## 项目定位
读取整数并输出数值之和。
## 目标与边界
只处理本地整数，不读取外部服务。
## 主要能力
通过 main.py 的 total 计算总额。
## 知识导航
实现地图位于 evolve/codemap.md。
## 覆盖与缺口
已阅读本地入口；未执行检查。
'''
CODEMAP = '''# 示例代码地图

## 范围
仅核对本地 `main.py`。
## 运行入口
`main.py`。
## 模块职责
total 接受整数并返回数值之和。
## 关键链路
整数列表进入 total，再得到一个整数。
## 数据与依赖
无持久存储；使用 Python 内置 sum。
## 检查与修改入口
本次只读了入口，未执行检查。
## 未覆盖范围
错误类型输入尚未调查。
'''


class ProjectKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-project-knowledge-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.auth = {'source': 'controlled-knowledge-lifecycle-fixture',
                     'text': 'Inspect, present and apply the exact temporary knowledge candidates.',
                     'effect_kinds': ['project_records', 'knowledge'], 'paths': []}

    def cli(self, action, method=None, data=None, *, ok=True, target=None, request_id=None):
        argv = [sys.executable, '-B', str(ROOT / 'runtime/evolve.py'), '--project', str(self.root), action]
        if target:
            argv.append(target)
        if method:
            argv += ['--method', method]
        payload = None
        if data is not None:
            argv += ['--request', '-']
            body = {'authorization': self.auth, 'input': data}
            if request_id:
                body['request_id'] = request_id
                body['project_id'] = self.connection['project_id']
                body['expected_workspace_epoch'] = self.connection['workspace_epoch']
            payload = json.dumps(body)
        result = subprocess.run(argv, input=payload, text=True, capture_output=True)
        response = json.loads(result.stdout)
        self.assertEqual(response['ok'], ok, response)
        return response['data'] if ok else response['error']

    def connect(self):
        self.connection = self.cli('init', 'connect', {})
        return self.connection

    def sha(self, path):
        return hashlib.sha256((self.root / path).read_bytes()).hexdigest()

    def source(self, path):
        return {'path': path, 'expected_digest': self.sha(path)}

    def publish(self, path, kind, content, *, topic=None, mode='managed', sources=None, topics=None, replaces=None, sections=None, prepare_only=False):
        self.auth['paths'] = [path]
        document = {'kind': kind, 'topic': topic or kind, 'scope': 'Only the literal controlled local example.',
                    'mode': mode, 'sources': sources or []}
        if topics is not None:
            document['topics'] = topics
        if replaces is not None:
            document['replaces'] = replaces
        if sections is not None:
            document['sections'] = sections
        data = {'path': path, 'expected_digest': self.sha(path) if (self.root / path).is_file() else None,
                'content': content, 'topic': topic or kind, 'reason': 'Preserve the independently reviewed example.',
                'document': document, 'presentation': {'source': 'controlled-full-text', 'text': content},
                'acceptance': [{'key': key, 'text': statement} for key, statement in [
                    ('structure', 'The stated headings describe this example.'),
                    ('sources', 'No remote or execution evidence is claimed.'),
                    ('consistency', 'Only integer summation is described.'),
                    ('usefulness', 'The actual entry and limitations can be located.')]]}
        registered = any(d['path'] == path for d in self.cli('status')['project']['knowledge']['documents'])
        action, propose, apply = ('sync', 'propose', 'apply') if registered else ('init', 'baseline.propose', 'baseline.apply')
        item = self.cli(action, propose, data)
        ref = {k: item[k] for k in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}
        observations = [{'criterion_key': c['key'], 'status': 'passed', 'observer': 'controlled-content-review',
                         'basis': c['text']} for c in data['acceptance']]
        self.cli('sync', 'check', {'proposal': ref, 'observations': observations})
        decision = self.cli('sync', 'review', {'decisions': [{'proposal': ref, 'decision': 'approved',
            'source': 'controlled-specific-approval', 'text': content, 'reason': 'Literal example reviewed.'}]})
        application = {'proposal': ref, 'approved_event_id': decision['decisions'][0]['decision_event_id']}
        if prepare_only:
            return application
        app = self.cli(action, apply, application)
        self.cli('verify', 'knowledge', {'application_id': app['application_id'], 'observations': observations})
        return app

    def survey(self, **extra):
        perspectives = ['purpose', 'domain', 'behavior', 'code', 'contracts', 'verification', 'decisions', 'risks']
        return self.cli('init', 'survey', {'scope': ['.'], 'sources': [],
            'coverage': [{'perspective': p, 'status': 'unknown', 'basis': 'No independent evidence yet.',
                          'source_paths': [], 'questions': ['Inspect the actual project.']} for p in perspectives], **extra})

    def test_templates_are_available_before_connection_without_creating_records(self):
        result = self.cli('init', 'templates', target='codemap')
        self.assertIn('关键链路', result['template'])
        self.assertIn('sources', result['acceptance_dimensions'])
        self.assertFalse((self.root / 'evolve').exists())
        self.assertFalse((self.root / '.evolve-local').exists())

    def test_connection_and_survey_do_not_falsely_complete_initialization(self):
        self.connect()
        self.survey()
        state = self.cli('status')['project']['knowledge']
        self.assertEqual(state['initial_delivery']['status'], 'pending')
        result = self.cli('init', 'complete', {}, ok=False)
        self.assertEqual(result['code'], 'KNOWLEDGE_INCOMPLETE')
        self.assertEqual(len(self.cli('status')['project']['knowledge']['survey']['coverage']), 8)

    def test_explicit_epoch_transition_retains_actual_document_sources_and_rejects_old_writes(self):
        self.connect()
        self.publish('evolve/guides/rules.md', 'rule', '# Rules\n\n## 适用范围\nTemporary example.\n## 规则\nKeep original expectations.\n## 依据与例外\nControlled local evidence only.\n')
        before = self.cli('status')['project']['knowledge']['documents']
        saved = self.cli('maintain', 'backup', {})
        plan = self.cli('maintain', 'restore', {'stage': 'plan', 'bundle': saved['path'], 'manifest_digest': saved['manifest_digest']})
        self.cli('maintain', 'restore', {'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']})
        after = self.cli('status')['project']['knowledge']['documents']
        self.assertEqual(after, before)
        rejected = self.cli('maintain', 'backup', {}, request_id='old-epoch-refused', ok=False)
        self.assertEqual(rejected['code'], 'WORKSPACE_EPOCH')

    def test_survey_rejects_missing_perspective_and_keeps_real_unknowns(self):
        self.connect()
        result = self.cli('init', 'survey', {'scope': ['.'], 'sources': [], 'coverage': []}, ok=False)
        self.assertEqual(result['code'], 'KNOWLEDGE_COVERAGE')
        self.survey()
        state = self.cli('status')['project']['knowledge']
        self.assertEqual(state['survey']['coverage'][0]['status'], 'unknown')

    def test_typed_candidate_rejects_new_knowledge_outside_evolve(self):
        self.connect()
        result = self.cli('init', 'baseline.propose', {'path': 'notes.md', 'expected_digest': None,
            'topic': 'project', 'reason': 'Initial project knowledge.', 'content': '# 项目\n',
            'presentation': {'source': 'controlled-text', 'text': '# 项目\n'},
            'acceptance': [{'key': 'sources', 'text': 'Only actual observations are stated.'}],
            'document': {'kind': 'project', 'topic': 'project', 'scope': 'Temporary project', 'sources': []}}, ok=False)
        self.assertEqual(result['code'], 'KNOWLEDGE_LOCATION')
        self.assertFalse((self.root / 'notes.md').exists())

    def test_complete_delivery_keeps_unknowns_and_actual_source_applicability(self):
        self.connect()
        (self.root / 'main.py').write_text('def total(items):\n    return sum(items)\n')
        coverage = [{'perspective': p, 'status': 'covered' if p in ('purpose', 'domain', 'behavior', 'code', 'verification') else 'unknown',
                     'basis': 'Read the local integer summation entry; no execution or remote state is claimed.',
                     'source_paths': ['main.py'] if p in ('purpose', 'domain', 'behavior', 'code', 'verification') else [],
                     'questions': [] if p in ('purpose', 'domain', 'behavior', 'code', 'verification') else ['Historical choices remain unknown.']}
                    for p in ['purpose', 'domain', 'behavior', 'code', 'contracts', 'verification', 'decisions', 'risks']]
        self.survey(sources=[self.source('main.py')], coverage=coverage)
        self.publish('evolve/project.md', 'project', PROJECT, sources=[self.source('main.py')])
        self.publish('evolve/codemap.md', 'codemap', CODEMAP, sources=[self.source('main.py')])
        self.assertEqual(self.cli('init', 'complete', {})['outcome'], 'knowledge_initial_delivery_completed')
        state = self.cli('status')['project']['knowledge']
        self.assertEqual(state['initial_delivery']['status'], 'completed')
        self.assertEqual(state['survey']['coverage'][-1]['status'], 'unknown')
        (self.root / 'main.py').write_text('def total(items):\n    return len(items)\n')
        docs = self.cli('status')['project']['knowledge']['documents']
        self.assertTrue(all(d['applicability'] == 'needs_review' for d in docs))
        self.assertEqual((self.root / 'evolve/project.md').read_text(), PROJECT)

    def test_empty_project_records_intent_and_absent_implementation_without_fabricated_code(self):
        self.connect()
        (self.root / 'README.md').write_text('# 新项目\n\n计划提供本地整数求和，尚无代码和检查。\n')
        self.survey(sources=[self.source('README.md')], coverage=[
            {'perspective': p, 'status': 'covered' if p in ('purpose', 'code', 'verification') else 'partial',
             'basis': 'Read the only README; there is no implementation, test command or external system.',
             'source_paths': ['README.md'], 'questions': [] if p in ('purpose', 'code', 'verification') else ['Confirm the detailed behavior and historical decisions before implementation.']}
            for p in ['purpose', 'domain', 'behavior', 'code', 'contracts', 'verification', 'decisions', 'risks']])
        self.publish('evolve/project.md', 'project', '# 新项目\n\n目标为本地整数求和；当前没有实现。知识入口为 evolve/codemap.md，细节行为待确认。\n',
                     sources=[self.source('README.md')], sections=[])
        self.publish('evolve/codemap.md', 'codemap', '# 当前结构\n\n仅 README.md 记录目标；没有运行入口、模块、数据依赖或检查脚本，不能声称运行通过。实现和异常约束尚待建立。\n',
                     sources=[self.source('README.md')], sections=[])
        self.assertEqual(self.cli('init', 'complete', {})['outcome'], 'knowledge_initial_delivery_completed')
        state = self.cli('status')
        self.assertFalse(state['project']['changes'])
        self.assertFalse((self.root / 'main.py').exists())
        self.assertFalse((self.root / 'tests').exists())

    def test_batched_subproject_survey_preserves_scope_unknowns_and_invalidates_old_completion(self):
        self.connect()
        for name in ('a', 'b'):
            (self.root / name).mkdir()
            (self.root / name / 'main.py').write_text('def total(items):\n    return sum(items)\n')
        invalid = {'scope': ['a'], 'sources': [self.source('b/main.py')], 'coverage': []}
        self.assertEqual(self.cli('init', 'survey', invalid, ok=False)['code'], 'KNOWLEDGE_COVERAGE')
        coverage = [{'perspective': p, 'status': 'partial', 'basis': 'Only module a was read; module b remains outside this batch.',
                     'source_paths': ['a/main.py'], 'questions': ['Inspect b in a separate batch.']}
                    for p in ['purpose', 'domain', 'behavior', 'code', 'contracts', 'verification', 'decisions', 'risks']]
        self.survey(scope=['a'], sources=[self.source('a/main.py')], coverage=coverage)
        self.publish('evolve/project.md', 'project', PROJECT.replace('main.py', 'a/main.py'), sources=[self.source('a/main.py')])
        self.publish('evolve/codemap.md', 'codemap', CODEMAP.replace('main.py', 'a/main.py'), sources=[self.source('a/main.py')])
        complete = self.cli('init', 'complete', {})
        self.assertEqual(complete['scope'], ['a'])
        self.survey(scope=['b'], sources=[self.source('b/main.py')], coverage=[{**c, 'source_paths': ['b/main.py']} for c in coverage])
        view = self.cli('status')['project']['knowledge']
        self.assertEqual(view['initial_delivery']['status'], 'pending')
        self.assertEqual(view['survey']['scope'], ['b'])

    def test_source_change_after_concrete_approval_blocks_application(self):
        self.connect()
        (self.root / 'main.py').write_text('def total(items):\n    return sum(items)\n')
        application = self.publish('evolve/codemap.md', 'codemap', CODEMAP,
                                   sources=[self.source('main.py')], prepare_only=True)
        (self.root / 'main.py').write_text('def total(items):\n    return len(items)\n')
        self.assertEqual(self.cli('init', 'baseline.apply', application, ok=False)['code'], 'KNOWLEDGE_SOURCE')
        self.assertFalse((self.root / 'evolve/codemap.md').exists())

    def interrupted_document(self):
        self.connect()
        application = self.publish('evolve/project.md', 'project', PROJECT, prepare_only=True)
        code = '''import os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core import formal,cli
def stop(*args,**kwargs): os._exit(61)
formal.install_files=stop
raise SystemExit(cli.main(['--project',sys.argv[2],'init','--method','baseline.apply','--request','-']))
'''
        request = {'authorization': self.auth, 'input': application}
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'runtime'), str(self.root)],
                                input=json.dumps(request), capture_output=True, text=True)
        self.assertEqual(result.returncode, 61, result.stderr)
        state = self.cli('status')
        return state['project']['pending_runs'][0]['id']

    def test_typed_initial_knowledge_recovers_exact_approved_journal_without_fake_verification(self):
        run_id = self.interrupted_document()
        result = self.cli('maintain', 'recover', {'run_id': run_id})
        self.assertFalse(result['business_commands_run'])
        self.assertEqual((self.root / 'evolve/project.md').read_text(), PROJECT)
        state = self.cli('status')
        document = next(d for d in state['project']['knowledge']['documents'] if d['active'])
        self.assertIsNone(document['verification_id'])
        self.assertEqual(state['project']['pending_runs'], [])
        self.assertEqual(self.cli('init', 'complete', {}, ok=False)['code'], 'KNOWLEDGE_INCOMPLETE')

    def test_typed_initial_recovery_keeps_third_party_content(self):
        run_id = self.interrupted_document()
        actual = 'External bytes must survive an interrupted initial application.\n'
        (self.root / 'evolve/project.md').write_text(actual)
        result = self.cli('maintain', 'recover', {'run_id': run_id})
        self.assertEqual(result['outcome'], 'needs_recovery')
        self.assertEqual((self.root / 'evolve/project.md').read_text(), actual)
        self.assertEqual(self.cli('status')['project']['knowledge']['documents'], [])

    def test_changed_source_only_marks_its_related_document_for_review(self):
        self.connect()
        for name in ('a.py', 'b.py'):
            (self.root / name).write_text('def total(items):\n    return sum(items)\n')
        self.publish('evolve/codemap.md', 'codemap', CODEMAP.replace('main.py', 'a.py'), sources=[self.source('a.py')])
        self.publish('evolve/guides/development.md', 'development', '# 检查范围\n\n仅阅读 b.py，未运行检查。其他模块和远端环境未调查。\n',
                     sources=[self.source('b.py')], sections=[])
        (self.root / 'a.py').write_text('def total(items):\n    return len(items)\n')
        docs = {d['topic']: d for d in self.cli('status')['project']['knowledge']['documents'] if d['active']}
        self.assertEqual(docs['codemap']['applicability'], 'needs_review')
        self.assertEqual(docs['development']['applicability'], 'matching_local_bytes')
        self.assertEqual(docs['development']['external_data'], 'not_reobserved')

    def test_content_check_finds_missing_references_anchors_and_bad_diagram_declarations(self):
        self.connect()
        for index, content in enumerate(('# 说明\n\n[缺失资源](missing.md)\n', '# 说明\n\n[失效锚点](#missing)\n',
                                         '# 说明\n\n```mermaid\nunsupportedDiagram\n```\n')):
            with self.subTest(content=content):
                criteria = [{'key': key, 'text': 'Check this exact bounded content.'}
                            for key in ('structure', 'sources', 'consistency', 'usefulness', 'diagrams')]
                item = self.cli('init', 'baseline.propose', {'path': 'evolve/decisions/check-' + str(index) + '.md',
                    'expected_digest': None, 'content': content, 'topic': 'check-' + str(index),
                    'reason': 'An intentionally invalid candidate must not pass structure validation.',
                    'presentation': {'source': 'negative-controlled-fixture', 'text': content}, 'acceptance': criteria,
                    'document': {'kind': 'decision', 'topic': 'check-' + str(index), 'scope': 'Bounded negative example',
                                 'sources': [], 'sections': []}})
                ref = {key: item[key] for key in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}
                error = self.cli('sync', 'check', {'proposal': ref, 'observations': []}, ok=False)
                self.assertEqual(error['code'], 'KNOWLEDGE_STRUCTURE')

    def test_initial_mapping_preserves_original_and_topic_migration_is_partial(self):
        self.connect()
        old = '# 既有资料\n\n## 汇总\n整数求和。\n\n## 报告\n输出文本。\n'
        (self.root / 'architecture.md').write_text(old)
        self.publish('architecture.md', 'architecture', old, topic='legacy', mode='mapped',
                     topics=[{'topic': 'totals', 'section': '汇总'}, {'topic': 'reports', 'section': '报告'}])
        docs = self.cli('status')['project']['knowledge']['documents']
        original = next(d for d in docs if d['topic'] == 'totals')
        new = '# 汇总决定\n\n## 背景\n已有整数求和。\n## 决定\n保留整数求和语义。\n## 理由与影响\n保持现有结果。\n'
        self.publish('evolve/decisions/0001-totals.md', 'decision', new, topic='totals',
                     replaces=[{k: original[k] for k in ('path', 'topic', 'artifact_version_id')}])
        docs = self.cli('status')['project']['knowledge']['documents']
        active = {d['topic']: d['path'] for d in docs if d['active']}
        self.assertEqual(active, {'totals': 'evolve/decisions/0001-totals.md', 'reports': 'architecture.md'})
        self.assertEqual((self.root / 'architecture.md').read_text(), old)

    def test_initial_mapping_preserves_crlf_bytes_and_rejects_newline_conversion(self):
        self.connect()
        original = b'# Existing\r\n\r\n## Overview\r\nInteger summation.\r\n'
        (self.root / 'architecture.md').write_bytes(original)
        data = {'path': 'architecture.md', 'expected_digest': self.sha('architecture.md'),
            'topic': 'legacy', 'reason': 'Map the actual existing text.',
            'content': original.decode().replace('\r\n', '\n'),
            'presentation': {'source': 'controlled-text', 'text': original.decode().replace('\r\n', '\n')},
            'acceptance': [{'key': 'structure', 'text': 'Existing document retained.'}],
            'document': {'kind': 'architecture', 'topic': 'legacy', 'scope': 'Local example', 'mode': 'mapped', 'sources': []}}
        self.assertEqual(self.cli('init', 'baseline.propose', data, ok=False)['code'], 'KNOWLEDGE_LOCATION')
        self.assertEqual((self.root / 'architecture.md').read_bytes(), original)
        self.publish('architecture.md', 'architecture', original.decode(), mode='mapped')
        self.assertEqual((self.root / 'architecture.md').read_bytes(), original)

    def test_managed_replacement_rejects_its_own_live_source_before_any_write(self):
        self.connect()
        path = 'evolve/project.md'
        self.publish(path, 'project', PROJECT)
        (self.root / 'mirror').symlink_to(self.root / 'evolve', target_is_directory=True)
        content = PROJECT.replace('读取整数', '读取本地整数')
        for source in (path, 'mirror/project.md'):
            with self.subTest(source=source):
                error = self.cli('sync', 'propose', {'path': path, 'expected_digest': self.sha(path), 'content': content,
                    'topic': 'project', 'reason': 'Keep the prior document as a version, not a changing live input.',
                    'presentation': {'source': 'controlled-text', 'text': content},
                    'acceptance': [{'key': k, 'text': 'Retain the actual bounded project meaning.'} for k in ('structure', 'sources', 'consistency', 'usefulness')],
                    'document': {'kind': 'project', 'topic': 'project', 'scope': 'Local project', 'sources': [self.source(source)]}}, ok=False)
                self.assertEqual(error['code'], 'KNOWLEDGE_SOURCE')
                self.assertEqual((self.root / path).read_text(), PROJECT)
                self.assertEqual(self.cli('status')['project']['pending_runs'], [])

    def test_revision_cannot_silently_drop_an_unrelated_topic_mapping(self):
        self.connect()
        original = '# 决定\n\n## A\n保留整数求和。\n\n## B\n没有报告输出。\n'
        path = 'evolve/decisions/0001-topics.md'
        self.publish(path, 'decision', original, topics=[{'topic': 'a', 'section': 'A'}, {'topic': 'b', 'section': 'B'}], sections=[])
        changed = original.replace('保留整数求和。', '保留本地整数求和。')
        error = self.cli('sync', 'propose', {'path': path, 'expected_digest': self.sha(path), 'content': changed,
            'topic': 'decision', 'reason': 'A changes; B remains present and must retain navigation.',
            'presentation': {'source': 'controlled-text', 'text': changed},
            'acceptance': [{'key': key, 'text': 'Preserve both actual topics.'} for key in ('structure', 'sources', 'consistency', 'usefulness')],
            'document': {'kind': 'decision', 'topic': 'decision', 'scope': 'Both local decisions', 'sections': [], 'sources': [],
                         'topics': [{'topic': 'a', 'section': 'A'}]}}, ok=False)
        self.assertEqual(error['code'], 'KNOWLEDGE_AUTHORITY')
        active = {d['topic'] for d in self.cli('status')['project']['knowledge']['documents'] if d['active']}
        self.assertEqual(active, {'a', 'b'})
        self.assertEqual((self.root / path).read_text(), original)

    def test_short_decision_can_cover_responsibilities_in_paragraphs(self):
        self.connect()
        content = '# 求和方式\n\n背景：项目处理本地整数。决定：使用 Python 内置 sum。理由：满足现有求和约定并减少实现代码。\n'
        self.publish('evolve/decisions/0001-sum.md', 'decision', content, sections=[])
        self.assertEqual((self.root / 'evolve/decisions/0001-sum.md').read_text(), content)

    def prepare_move(self):
        self.connect()
        (self.root / 'main.py').write_text('def total(items):\n    return sum(items)\n')
        self.publish('evolve/codemap.md', 'codemap', CODEMAP, sources=[self.source('main.py')])
        baseline = self.sha('evolve/codemap.md')
        (self.root / 'src').mkdir()
        (self.root / 'main.py').rename(self.root / 'src/main.py')
        self.auth['effect_kinds'].append('facts_maintenance')
        self.auth['fact_moves'] = [{'from_path': 'main.py', 'to_path': 'src/main.py'}]
        return {'path': 'evolve/codemap.md', 'expected_digest': baseline,
                'fact_update': {'kind': 'path_move', 'from_path': 'main.py', 'to_path': 'src/main.py'}}

    def test_fact_movement_preserves_other_text_and_can_retry_original_receipt(self):
        request = self.prepare_move()
        result = self.cli('sync', 'facts', request, request_id='scoped-path-move')
        self.assertEqual(result['authority'], 'scoped_facts')
        self.assertEqual(result['factual_verification']['status'], 'passed')
        self.assertEqual((self.root / 'evolve/codemap.md').read_text(), CODEMAP.replace('`main.py`', '`src/main.py`'))
        again = self.cli('sync', 'facts', request, request_id='scoped-path-move')
        self.assertEqual(again['application_id'], result['application_id'])

    def test_fact_movement_rejects_changed_behavior_and_extra_text(self):
        request = self.prepare_move()
        request['content'] = CODEMAP.replace('整数', '字符串')
        self.assertEqual(self.cli('sync', 'facts', request, ok=False)['code'], 'KNOWLEDGE_FACTS')
        self.assertEqual((self.root / 'evolve/codemap.md').read_text(), CODEMAP)
        request.pop('content')
        (self.root / 'src/main.py').write_text('def total(items):\n    return len(items)\n')
        self.assertEqual(self.cli('sync', 'facts', request, ok=False)['code'], 'KNOWLEDGE_FACTS')
        self.assertEqual((self.root / 'evolve/codemap.md').read_text(), CODEMAP)

    def test_fact_movement_cannot_replace_a_latest_failed_semantic_review_with_passed(self):
        request = self.prepare_move()
        doc = next(d for d in self.cli('status')['project']['knowledge']['documents'] if d['active'])
        verification = self.actual_document_review(doc['application_id'], 'failed')
        self.assertEqual(self.cli('sync', 'facts', request, ok=False)['code'], 'KNOWLEDGE_FACTS')
        current = next(d for d in self.cli('status')['project']['knowledge']['documents'] if d['active'])
        self.assertEqual(current['verification_id'], verification['verification_id'])
        self.assertEqual((self.root / 'evolve/codemap.md').read_text(), CODEMAP)

    def test_fact_movement_requires_exact_scope_and_preserves_external_edit(self):
        request = self.prepare_move()
        self.auth['fact_moves'] = []
        self.assertEqual(self.cli('sync', 'facts', request, ok=False)['code'], 'AUTHORIZATION')
        self.assertEqual((self.root / 'evolve/codemap.md').read_text(), CODEMAP)
        self.auth['fact_moves'] = [{'from_path': 'main.py', 'to_path': 'src/main.py'}]
        (self.root / 'evolve/codemap.md').write_text(CODEMAP + '\n用户补充。\n')
        self.assertEqual(self.cli('sync', 'facts', request, ok=False)['code'], 'FILE_CONFLICT')
        self.assertIn('用户补充', (self.root / 'evolve/codemap.md').read_text())

    def code_plan_data(self, disposition='unchanged'):
        text = 'Materialize the local iterable and preserve integer summation; inspect the affected knowledge.'
        return {'title': 'Preserve integer total', 'plan': text, 'completion': 'The known sum behavior remains correct.',
                'scope': ['main.py'], 'required_checks': [], 'acceptance': ['total([2, 3]) equals 5.'],
                'presentation': {'source': 'controlled-plan-text', 'text': text},
                'knowledge_impact': [{'topic': 'codemap', 'disposition': disposition,
                    'reason': 'The entry stays at the same location and the documented behavior is preserved.',
                    **({'target_path': 'evolve/codemap.md'} if disposition == 'required' else {})}]}

    def prepare_knowledge_plan(self):
        self.connect()
        (self.root / 'main.py').write_text('def total(items):\n    return sum(items)\n')
        self.publish('evolve/codemap.md', 'codemap', CODEMAP, sources=[self.source('main.py')])
        self.auth['effect_kinds'].append('business_files')
        self.auth['paths'] = ['main.py']

    def test_managed_plan_must_account_for_related_knowledge(self):
        self.prepare_knowledge_plan()
        data = self.code_plan_data()
        data['knowledge_impact'] = []
        self.assertEqual(self.cli('propose', 'create', data, ok=False)['code'], 'KNOWLEDGE_IMPACT')
        data.pop('knowledge_impact')
        self.assertEqual(self.cli('propose', 'create', data, ok=False)['code'], 'KNOWLEDGE_IMPACT')

    def test_scope_alias_cannot_hide_related_knowledge(self):
        self.prepare_knowledge_plan()
        (self.root / 'mirror').symlink_to(self.root, target_is_directory=True)
        for name in ('./main.py', 'mirror/main.py'):
            with self.subTest(path=name):
                data = self.code_plan_data()
                data.update(scope=[name], knowledge_impact=[])
                self.assertEqual(self.cli('propose', 'create', data, ok=False)['code'], 'KNOWLEDGE_IMPACT')

    def test_required_knowledge_cannot_be_silently_deferred(self):
        self.prepare_knowledge_plan()
        plan = self.cli('propose', 'create', self.code_plan_data('required'))
        error = self.cli('sync', 'assess', {'change_id': plan['change_id'], 'revision_id': plan['revision_id'],
            'observations': [{'topic': 'codemap', 'result': 'deferred', 'observer': 'controlled-review',
                              'basis': 'Leave it for later.'}]}, ok=False)
        self.assertEqual(error['code'], 'KNOWLEDGE_IMPACT')
        error = self.cli('sync', 'assess', {'change_id': plan['change_id'], 'revision_id': plan['revision_id'],
            'observations': [{'topic': 'codemap', 'result': 'updated', 'observer': 'controlled-review',
                              'basis': 'The document has not changed.'}]}, ok=False)
        self.assertEqual(error['code'], 'KNOWLEDGE_INCOMPLETE')

    def verified_implementation(self, disposition='unchanged', *, followup=False):
        self.prepare_knowledge_plan()
        data = self.code_plan_data(disposition)
        if followup:
            data['knowledge_impact'].append({'topic': 'future-cleanup', 'disposition': 'followup',
                'reason': 'Independent future documentation cleanup does not affect this local implementation.'})
        plan = self.cli('propose', 'create', data)
        self.cli('apply', 'implement', {'change_id': plan['change_id'], 'accepted_plan_digest': plan['plan_digest'],
            'files': [{'path': 'main.py', 'expected_digest': self.sha('main.py'),
                       'content': 'def total(items):\n    values = list(items)\n    return sum(values)\n'}]})
        observed = subprocess.run([sys.executable, '-B', '-c', 'from main import total; assert total([2,3]) == 5'], cwd=self.root)
        self.assertEqual(observed.returncode, 0)
        snapshot = self.cli('resume', target=plan['change_id'])['context']['workspace_observation']['current']
        reviews = [{'axis': axis, 'observer': 'controlled-actual-review', 'summary': 'Read the local implementation and preserved summation.',
                    'fingerprint_digest': snapshot['digest'], 'findings': []} for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': plan['acceptance'][0]['id'], 'status': 'passed',
                                            'basis': 'Executed total([2,3]) and compared to the literal 5.'}]
        checked = self.cli('verify', 'run', {'change_id': plan['change_id'], 'reviews': reviews})
        archive = {'change_id': plan['change_id'], 'verification_id': checked['verification_id']}
        return plan, archive

    def test_archive_requires_current_knowledge_assessment_and_restores_applicability(self):
        plan, archive = self.verified_implementation()
        self.assertEqual(self.cli('archive', 'close', archive, ok=False)['code'], 'KNOWLEDGE_INCOMPLETE')
        self.cli('sync', 'assess', {'change_id': plan['change_id'], 'revision_id': plan['revision_id'],
            'observations': [{'topic': 'codemap', 'result': 'unchanged', 'observer': 'controlled-actual-review',
                'basis': 'Only local iterable materialization changed; the entry, integer behavior and all stated limitations still apply.'}]})
        docs = self.cli('status')['project']['knowledge']['documents']
        self.assertEqual(next(d for d in docs if d['active'])['applicability'], 'matching_local_bytes')
        self.assertEqual(self.cli('archive', 'close', archive)['outcome'], 'archived')

    def actual_document_review(self, application_id, status):
        return self.cli('verify', 'knowledge', {'application_id': application_id,
            'observations': [{'criterion_key': key, 'status': status if key == 'consistency' else 'passed',
                'observer': 'independent-later-review', 'basis': 'Reassessed the same actual content without changing bytes.'}
                for key in ('structure', 'sources', 'consistency', 'usefulness')]})

    def test_unchanged_assessment_rejects_latest_failed_document_review(self):
        plan, _ = self.verified_implementation()
        doc = next(d for d in self.cli('status')['project']['knowledge']['documents'] if d['active'])
        self.actual_document_review(doc['application_id'], 'failed')
        error = self.cli('sync', 'assess', {'change_id': plan['change_id'], 'revision_id': plan['revision_id'],
            'observations': [{'topic': 'codemap', 'result': 'unchanged', 'observer': 'controlled-review',
                              'basis': 'A prior review passed but the latest one failed.'}]}, ok=False)
        self.assertEqual(error['code'], 'KNOWLEDGE_IMPACT')

    def test_independent_followup_does_not_block_verified_work_and_keeps_its_entry(self):
        plan, archive = self.verified_implementation(followup=True)
        self.cli('sync', 'assess', {'change_id': plan['change_id'], 'revision_id': plan['revision_id'],
            'observations': [{'topic': 'codemap', 'result': 'unchanged', 'observer': 'controlled-review',
                              'basis': 'The actual entry and integer result remain correct.'},
                             {'topic': 'future-cleanup', 'result': 'deferred', 'observer': 'controlled-review',
                              'basis': 'This independent cleanup has no bearing on the accepted behavior.'}]})
        self.assertEqual(self.cli('archive', 'close', archive)['outcome'], 'archived')
        state = self.cli('status', target=plan['change_id'])['project']['changes'][0]
        self.assertTrue(any(i['topic'] == 'future-cleanup' and i['disposition'] == 'followup' for i in state['knowledge_impact']))

    def test_archive_rechecks_latest_review_and_current_authority_after_assessment(self):
        plan, archive = self.verified_implementation('required')
        content = CODEMAP.replace('本次只读了入口，未执行检查。', '已执行 total([2,3])，结果为 5。')
        app = self.publish('evolve/codemap.md', 'codemap', content, sources=[self.source('main.py')])
        self.cli('sync', 'assess', {'change_id': plan['change_id'], 'revision_id': plan['revision_id'],
            'observations': [{'topic': 'codemap', 'result': 'updated', 'observer': 'controlled-review',
                              'basis': 'The new formal map reflects the actual verified result.'}]})
        self.actual_document_review(app['application_id'], 'failed')
        self.assertEqual(self.cli('archive', 'close', archive, ok=False)['code'], 'KNOWLEDGE_INCOMPLETE')
        self.actual_document_review(app['application_id'], 'passed')
        current = next(d for d in self.cli('status')['project']['knowledge']['documents'] if d['active'])
        self.publish('evolve/guides/architecture.md', 'architecture',
            '# 当前入口\n\n本地 main.py 的 total 负责整数求和；没有外部依赖。\n', topic='codemap', sections=[],
            replaces=[{k: current[k] for k in ('topic', 'path', 'artifact_version_id')}])
        self.assertEqual(self.cli('archive', 'close', archive, ok=False)['code'], 'KNOWLEDGE_INCOMPLETE')


    def parallel_metadata_composition(self, *, register_topic):
        self.connect()
        path, base = 'evolve/codemap.md', '# Combined\n\n## A\nA old.\n'
        self.publish(path, 'codemap', base, topic='a', topics=[{'topic': 'a', 'section': 'A'}], sections=[])
        criteria = [{'key': key, 'text': 'Preserve independent text and topic navigation.'}
                    for key in ('structure', 'sources', 'consistency', 'usefulness')]
        observations = [{'criterion_key': c['key'], 'status': 'passed', 'observer': 'controlled-review', 'basis': c['text']} for c in criteria]
        def candidate(topic, content, edit, topics, sources=None):
            item = self.cli('sync', 'propose', {'path': path, 'expected_digest': self.sha(path), 'content': content,
                'topic': topic, 'reason': 'An independently approved exact patch.',
                'presentation': {'source': 'controlled-text', 'text': content}, 'acceptance': criteria, 'edits': [edit],
                'document': {'kind': 'codemap', 'topic': 'a', 'scope': 'Both literal local sections',
                             'sources': sources or [], 'sections': [], 'topics': topics}})
            return {k: item[k] for k in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}
        start = base.index('A old.')
        a = candidate('a', base.replace('A old.', 'A new.'),
            {'start': start, 'end': start + 6, 'before': 'A old.', 'after': 'A new.', 'semantic_target': 'a'},
            [{'topic': 'a', 'section': 'A'}])
        extra = '\n## B\nB exists.\n'
        (self.root / 'b.py').write_text('# Actual retained source for the independent B section.\n')
        b = candidate('b', base + extra,
            {'start': len(base), 'end': len(base), 'before': '', 'after': extra, 'semantic_target': 'b'},
            [{'topic': 'a', 'section': 'A'}, *([{'topic': 'b', 'section': 'B'}] if register_topic else [])],
            sources=[] if register_topic else [self.source('b.py')])
        for ref in (a, b):
            self.cli('sync', 'check', {'proposal': ref, 'batch': [a, b], 'observations': observations})
        decisions = self.cli('sync', 'review', {'batch': [a, b], 'decisions': [
            {'proposal': ref, 'decision': 'approved', 'source': 'controlled-exact-batch',
             'text': 'Apply each exact independent patch while retaining both topics.', 'reason': 'Reviewed both actual candidates.'}
            for ref in (a, b)]})['decisions']
        self.cli('sync', 'apply', {'proposal': b, 'approved_event_id': decisions[1]['decision_event_id']})
        merged = (base + extra).replace('A old.', 'A new.')
        error = self.cli('sync', 'apply', {'proposal': a, 'approved_event_id': decisions[0]['decision_event_id'],
            'composition_review': {'base_digest': self.sha(path), 'result_digest': hashlib.sha256(merged.encode()).hexdigest(),
                'semantic_targets': ['a', 'b'], 'status': 'passed', 'observer': 'controlled-composition',
                'basis': 'The exact merged text retains both sections; metadata must also retain both.'}}, ok=False)
        self.assertEqual(error['code'], 'KNOWLEDGE_AUTHORITY' if register_topic else 'KNOWLEDGE_METADATA')
        self.assertEqual((self.root / path).read_text(), base + extra)
        active = {d['topic'] for d in self.cli('status')['project']['knowledge']['documents'] if d['active']}
        self.assertEqual(active, {'a', 'b'} if register_topic else {'a'})
        if not register_topic:
            current = next(d for d in self.cli('status')['project']['knowledge']['documents'] if d['active'])
            self.assertEqual([s['path'] for s in current['sources']], ['b.py'])

    def test_parallel_composition_cannot_drop_a_topic_added_after_proposal(self):
        self.parallel_metadata_composition(register_topic=True)

    def test_parallel_composition_cannot_drop_a_source_added_after_proposal(self):
        self.parallel_metadata_composition(register_topic=False)


if __name__ == '__main__':
    unittest.main()
