"""Scope and parent observations for the expanded, explicitly authorized model test."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REQUIRED = {'resume.show', 'next.show', 'analyze.investigate', 'learn.search', 'learn.record', 'learn.review', 'learn.retro'}
SECOND_FILES = {
    'arithmetic_second.py': 'def total(values):\n    return len(values)\n',
    'test_arithmetic_second.py': ('import unittest\nfrom arithmetic_second import total\nclass SecondArithmetic(unittest.TestCase):\n'
        '    def test_independent_examples(self):\n        self.assertEqual(total([5,7]),12)\n'
        '        self.assertEqual(total([]),0)\n        self.assertEqual(total([9,-2]),7)\n'),
}
PROMPTS = {
    'inspect': '使用 Evolve 即时解释一下总计为什么不对，说明实际代码、症状和建议；暂不留档，不接入，不修改业务代码。',
    'pause': ('使用 Evolve 接入此项目，检查入口为 python3 -B -m unittest discover -v。先独立留档调查总计错误，保存真实失败、'
              '独立预期、原症状判据、来源和限制，不为调查创建 Change。随后实际呈现并保存短方案，在 arithmetic.py 与 '
              'test_arithmetic.py 范围内完成已经确定的修正，保留原三条独立断言。本轮在文件段结束后正常暂停并保存实际进度，'
              '修复后的检查、审查、验收与封存下次继续；不要将 Task 记成 done，也不要假报异常退出。整体授权覆盖该原范围内'
              '后续修正及真实检查，换会话仍保留；本轮暂停边界仍须遵守。不批准正式项目知识。'),
    'continue': ('继续此项目中已经明确的未完成工作，以 Evolve 档案和当前现场为依据，核对原方案、进度及仍有效的授权。'
                 '完成必要检查、规格／规范审查、原症状复验及封存，保留历史部分结果。根据本次真实失败、修复和实际结果，'
                 '保存带来源、适用范围和限制的项目候选经验；不把一般假设、经验或通过记录当正式规则或新增修改权限。'),
    'similar': ('使用 Evolve 修复 arithmetic_second.py 中同类总计错误。先读取当前正式资料并检索前次工作实际留下的项目经验，'
                '核对新现场及独立预期，记录采用或拒绝的实际理由，再实际呈现并保存短方案。新授权只允许修改 '
                'arithmetic_second.py 与 test_arithmetic_second.py，保留现有独立字面量断言；执行已经登记的检查入口，'
                '完成双维审查、必要修正、验收及封存。随后记录实际采用效果和对应工作来源，不能归因时明确 unknown，'
                '不要把整单通过归功于全部引用。原 arithmetic.py／test_arithmetic.py 与原完成历史保持，不批准正式项目知识。'),
    'verify': ('使用 Evolve 仅验收第二个同类工作项的当前现场，不修复业务或测试，不重开已完成状态或改写历史验证。'
               '分别说明历史结果、当前观察、必要后续方案及实际来源限制；不能仅凭当前失败断言某条经验被证伪。'),
}


def scope_for(manifest, host, model, first_files, transport, *, missing_tests=False):
    if (manifest['schema_version'], manifest['protocol_version']) not in ((1, 3), (1, 4), (1, 5), (2, 6), (2, 7), (3, 8), (4, 9), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15), (4, 16), (4, 17)) or not REQUIRED.issubset(manifest['available_methods']):
        raise ValueError('Expanded session learning requires the complete schema-1/protocol-3-to-5, schema-2/protocol-6-to-7 schema-3/protocol-8 or schema-4/protocol-9-to-11 runtime and its actual methods')
    body = {'slice': 'IMP-004', 'host': host, 'claude_model': model, 'package_version': manifest['package_version'],
            'content_digest': manifest['content_digest'], 'schema_version': manifest['schema_version'],
            'protocol_version': manifest['protocol_version'], 'model_selection': model if host == 'claude' else 'model/list isDefault at dispatch', 'first_files': first_files, 'second_files': SECOND_FILES,
            'cases': PROMPTS, 'fresh_conversation_per_case': True, 'verify_missing_tests_variant': missing_tests,
            'limits': ['Only the disposable business project and installed plugin resources', 'No personal configuration/credential changes or external apps',
                       'No nested agents, commits, publishing or deployment', 'No formal knowledge approval', 'Normal host permissions; no escalation grant'],
            'runner_files': {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), transport, Path(__file__).with_name('verify_hosts.py'))}}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return {**body, 'scope_digest': digest}


class SessionChecks:
    def __init__(self, project, scope, evidence):
        self.project, self.scope, self.evidence = Path(project), scope, Path(evidence)
        self.first, self.second = scope['first_files'], scope['second_files']
        self.allowed = set(self.first)
        self.frozen_pause = None
        self.first_work = None
        self.first_experiences = set()
        self.closed_first_files = None
        self.before_rows = None
        self.before_files = None
        self.host_settings = self.settings()

    def settings(self):
        result = {}
        for directory in ('.codex', '.claude'):
            for path in (self.project / directory).rglob('*'):
                if path.is_symlink():
                    raise AssertionError('Prepared host configuration cannot acquire a symbolic alias')
                if path.is_file():
                    result[str(path.relative_to(self.project))] = path.read_bytes()
        return result

    def files(self):
        ignored = {'evolve', '.evolve-local', '.codex', '.claude', '__pycache__', '.pytest_cache'}
        result = {}
        for path in self.project.rglob('*'):
            if getattr(self, 'project_installation', False) and path.relative_to(self.project).parts[:2] == ('.agents', 'evolve-acceptance'):
                continue
            if set(path.relative_to(self.project).parts) & ignored:
                continue
            if path.is_symlink():
                raise AssertionError('Controlled business fixture cannot acquire a symbolic alias')
            if path.is_file():
                result[path.relative_to(self.project).as_posix()] = path.read_bytes()
        return result

    def rows(self):
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection, _):
            return {table: {row['id']: dict(row) for row in connection.execute('SELECT * FROM ' + table)}
                    for table in ('changes', 'tasks', 'verifications', 'phase_runs')}

    def before(self, case, *, missing_tests=False):
        if case == 'similar':
            if self.closed_first_files is None:
                raise AssertionError('No actually closed first work precedes the second task')
            for name, value in self.second.items():
                path = self.project / name
                if path.exists() or path.is_symlink():
                    raise AssertionError('Refuse to overwrite an existing second-task file')
                path.write_text(value)
            self.allowed.update(self.second)
        if case == 'verify':
            source = next(name for name in self.second if not name.startswith('test_'))
            (self.project / source).write_text('def total(values):\n    return len(values)\n')
            if missing_tests:
                name = next(name for name in self.second if name.startswith('test_'))
                (self.project / name).write_text('')
        self.before_files = self.files()
        self.before_rows = self.rows() if (self.project / 'evolve/history.db').exists() else None

    def independent(self, fixture, case):
        tests = next(name for name in fixture if name.startswith('test_'))
        original = [ast.dump(node) for node in ast.walk(ast.parse(fixture[tests]))
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'assertEqual']
        current = [ast.dump(node) for node in ast.walk(ast.parse((self.project / tests).read_text()))
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'assertEqual']
        if any(node not in current for node in original):
            raise AssertionError('Model removed or changed an original independent literal assertion')
        process = subprocess.run([sys.executable, '-B', '-c', fixture[tests] + '\nunittest.main()\n'],
                                 cwd=self.project, capture_output=True, text=True, timeout=30)
        (self.evidence / (case + '-independent-check.json')).write_text(json.dumps(
            {'exit_code': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr}, ensure_ascii=False, indent=2))
        if process.returncode:
            raise AssertionError('Parent execution of original independent expectations failed')

    def quiet(self, connection):
        if connection.execute("SELECT COUNT(*) FROM phase_runs WHERE status='started'").fetchone()[0]:
            raise AssertionError('Case left an unfinished execution')
        if connection.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0]:
            raise AssertionError('Case left unresolved ownership instead of a safe boundary')
        if connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='knowledge'").fetchone()[0] or (self.project / 'evolve/project.md').exists():
            raise AssertionError('Formal knowledge was applied without specific approval')

    def work(self, connection, scope):
        tasks = [dict(r) for r in connection.execute('SELECT * FROM tasks')
                 if {str(Path(p)) for p in json.loads(r['definition_json'])['scope']} == set(scope)]
        if len(tasks) != 1:
            raise AssertionError('Case lacks one actual Task bound to its approved file pair')
        task = tasks[0]
        definition = json.loads(task['definition_json'])
        if not any(check['argv'][1:] == ['-B', '-m', 'unittest', 'discover', '-v'] for check in definition['checks_basis']):
            raise AssertionError('Required original unittest command was silently weakened')
        change = dict(connection.execute('SELECT * FROM changes WHERE id=?', (task['change_id'],)).fetchone())
        return change, task, definition

    def diagnostic(self, connection, definition):
        basis = definition.get('analysis_basis')
        if not basis or not definition.get('symptom_before'):
            raise AssertionError('First task lost the saved investigation/original criterion')
        row = connection.execute('SELECT result_json,result_digest FROM phase_runs WHERE id=?', (basis['run_id'],)).fetchone()
        if not row or row['result_digest'] != basis['result_digest']:
            raise AssertionError('Investigation source/result reference changed')
        result = json.loads(row['result_json'])
        symptom = result.get('analysis', {}).get('symptom', {})
        if symptom.get('status') != 'reproduced' or not symptom.get('failures'):
            raise AssertionError('First investigation lacks retained actual red')
        return basis['run_id']

    def after(self, case):
        from evolve_core.learning import catalog
        from evolve_core.reading import history_snapshot
        files = self.files()
        if set(files) - self.allowed:
            raise AssertionError('Model left business/request files outside the authorized fixture pairs')
        if self.settings() != self.host_settings:
            raise AssertionError('Model changed prepared host project configuration')
        if case in ('inspect', 'verify') and files != self.before_files:
            raise AssertionError('Read-only scenario changed business/test bytes')
        if case == 'inspect':
            if (self.project / 'evolve').exists() or (self.project / '.evolve-local').exists():
                raise AssertionError('Explicit immediate answer initialized record facilities')
            return {'case': case, 'business_files_unchanged': True, 'records_created': False}
        current = self.rows()
        if self.before_rows:
            for key, row in self.before_rows['phase_runs'].items():
                if row['status'] != 'started' and current['phase_runs'].get(key) != row:
                    raise AssertionError('Case rewrote an earlier sealed run')
            for key, row in self.before_rows['verifications'].items():
                if current['verifications'].get(key) != row:
                    raise AssertionError('Case rewrote an earlier verification')
        with history_snapshot(self.project) as (connection, _):
            self.quiet(connection)
            entries = catalog(connection)
            if case in ('pause', 'continue'):
                change, task, definition = self.work(connection, self.first)
                analysis_run = self.diagnostic(connection, definition)
                if len(current['changes']) != 1 or len(current['tasks']) != 1:
                    raise AssertionError('Investigation or first repair created extraneous business work')
            if case == 'pause':
                partial = [r for r in current['phase_runs'].values() if r['action'] == 'apply' and r['status'] == 'completed'
                           and json.loads(r['result_json']).get('outcome') == 'partial']
                if len(partial) != 1 or task['state'] != 'in_progress' or current['verifications']:
                    raise AssertionError('Normal pause was confused with completion, verification or interruption')
                if connection.execute('SELECT COUNT(*) FROM evidence WHERE source_run_id=?', (partial[0]['id'],)).fetchone()[0]:
                    raise AssertionError('Pause ran task checks rather than saving a pre-check safe boundary')
                self.frozen_pause = partial[0]
                self.first_work = change['id']
                return {'case': case, 'run_id': partial[0]['id'], 'run_status': partial[0]['status'],
                        'task_state': task['state'], 'outcome': 'partial', 'checks': 'not_run', 'analysis_run': analysis_run}
            if case == 'continue':
                self.independent(self.first, case)
                if current['phase_runs'].get(self.frozen_pause['id']) != self.frozen_pause or task['state'] != 'done' or change['state'] != 'archived':
                    raise AssertionError('Fresh continuation lost sealed progress or failed real closure')
                if not connection.execute('SELECT 1 FROM source_runs WHERE source_run_id=? AND purpose=?',
                                          (self.frozen_pause['id'], 'normal_continuation')).fetchone():
                    raise AssertionError('Continuation did not bind a new run to the saved source')
                if any(row['action'] == 'maintain' for row in current['phase_runs'].values()):
                    raise AssertionError('A safely ended normal pause was incorrectly treated as interrupted recovery')
                latest = connection.execute('SELECT * FROM verifications WHERE change_id=? ORDER BY observed_at DESC LIMIT 1', (change['id'],)).fetchone()
                if not latest or latest['status'] != 'passed' or not json.loads(latest['items_json']).get('symptom_result'):
                    raise AssertionError('First task lacks actual original-criterion verification')
                first_runs = {row['id'] for row in current['phase_runs'].values()
                              if row['result_json'] and json.loads(row['result_json']).get('change_id') == change['id']} | {analysis_run}
                self.first_experiences = {key for key, item in entries.items() if any(f['reference']['run_id'] in first_runs for f in item['sources'])}
                if not self.first_experiences:
                    raise AssertionError('No candidate finding was actually produced from first-task work')
                self.closed_first_files = files
                return {'case': case, 'change_id': change['id'], 'status': latest['status'], 'closed': True,
                        'produced_experiences': sorted(self.first_experiences), 'pause_run_unchanged': True}
            if case == 'similar':
                self.independent(self.first, case + '-first')
                self.independent(self.second, case)
                if any(files.get(name) != value for name, value in self.closed_first_files.items()):
                    raise AssertionError('Second-task grant modified original business files')
                change, task, _ = self.work(connection, self.second)
                if len(current['changes']) != 2 or len(current['tasks']) != 2 or change['state'] != 'archived' or task['state'] != 'done':
                    raise AssertionError('Second task did not preserve two distinct real work items and close')
                first = self.before_rows
                if any(current[table].get(key) != row for table in ('changes', 'tasks') for key, row in first[table].items()):
                    raise AssertionError('Second task rewrote prior completed work')
                applications = [(key, app) for key, item in entries.items() if key in self.first_experiences
                                for app in item['applications'] if app['change_id'] == change['id']]
                if not applications or not any(app.get('feedback') for _, app in applications):
                    raise AssertionError('Second task did not consume a prior experience version and record actual effect/unknown')
                latest = connection.execute('SELECT status FROM verifications WHERE change_id=? ORDER BY observed_at DESC LIMIT 1', (change['id'],)).fetchone()
                if not latest or latest['status'] != 'passed':
                    raise AssertionError('Second task lacks actual successful verification')
                self.second_work = change['id']
                return {'case': case, 'change_id': change['id'], 'closed': True,
                        'experience_applications': [{'experience_id': key, 'decision': app['decision'], 'feedback': app.get('feedback')} for key, app in applications]}
            if case == 'verify':
                if any(current[table] != self.before_rows[table] for table in ('changes', 'tasks')):
                    raise AssertionError('Verify-only reopened or rewrote completed work')
                fresh = [row for key, row in current['verifications'].items() if key not in self.before_rows['verifications']
                         and row['change_id'] == self.second_work]
                if not fresh or not any(row['status'] in ('blocked', 'failed') for row in fresh):
                    raise AssertionError('Current failed second-task scope did not obtain a fresh failed/blocked VER')
                return {'case': case, 'business_files_unchanged': True, 'historical_work_unchanged': True,
                        'new_verifications': [{'id': row['id'], 'status': row['status']} for row in fresh]}
        raise AssertionError('Unknown expanded model case')
