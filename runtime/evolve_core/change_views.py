"""Rebuildable change documents from sealed facts, with explicit ownership checks."""
import html
import json
from pathlib import Path

from .continuation import retained_source, sealed_result
from .errors import EvolveError
from .package import canonical, digest
from .privacy import redact
from .workspace import current_digest, durable_write, inside


def view_path(root, name):
    path = inside(root, name)
    if path.resolve() != path:
        raise EvolveError('VIEW_CONFLICT', 'A derived view path uses a link: ' + name)
    return path


def manifests(connection, project_id, change_id):
    for row in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='change_view_prepared' ORDER BY rowid DESC"):
        value = json.loads(row['payload_json'])
        if value['change_id'] != change_id or value['project_id'] != project_id:
            continue
        source, request, _ = sealed_result(connection, value['source'])
        if retained_source(connection, source, request):
            yield value


def render(store, change, revision, run_id, result, status):
    source = {'run_id': run_id, 'result_digest': digest(canonical(result))}
    tasks = store.connection.execute('SELECT * FROM tasks WHERE revision_id=? ORDER BY rowid', (revision['id'],)).fetchall()
    verifications = store.connection.execute('SELECT * FROM verifications WHERE change_id=? ORDER BY observed_at,rowid', (change['id'],)).fetchall()
    from .knowledge_impact import declared_impacts, declared_review
    impacts = declared_impacts(store.connection, revision['id'])
    review = result.get('knowledge_review') or declared_review(store.connection, revision['id'])
    header = ['> 由 Evolve 历史事实生成。修改本文件不改变方案或任务状态；手工编辑冲突会保留。',
        '> 以下为保存时记录；当前适用性由 next／verify 核对。', '',
        '工作编号：' + change['code'], '工作状态：' + change['state'], '方案版本：' + str(revision['ordinal']),
        '来源运行：' + run_id, '来源结果摘要：' + source['result_digest'], '']
    lines = ['# ' + change['title'], '', *header, '## 目标与范围', '']
    definitions = [json.loads(task['definition_json']) for task in tasks]
    lines += [definitions[0]['completion'] if definitions else '', '']
    lines += ['- ' + name for name in json.loads(revision['scope_json'])]
    plan = store.one('SELECT content FROM blobs WHERE digest=?', (revision['plan_digest'],))[0].decode()
    document = json.loads(plan) if change['complexity'] == 'complex' else None
    lines += ['', '## 方案', '', document['plan'] if document else plan, '', '## 验收条件', '']
    lines += ['- ' + item['id'] + '：' + item['text'] for item in json.loads(revision['acceptance_json'])]
    lines += ['', '## 任务与检查', '']
    for task, definition in zip(tasks, definitions):
        lines += ['- ' + definition.get('task_code', definition['local_key']) + '：' + definition['title']
                  + '；记录状态 ' + task['state'] + '；必需检查 ' + ', '.join(definition['required_checks'])]
        if definition.get('pre_refactor'):
            saved = json.loads(task['result_json']) if task['result_json'] else {}
            lines += ['  - 保行为证明：' + saved.get('preservation', {}).get('status', '尚未执行')]
    if verifications:
        latest = verifications[-1]
        lines += ['', '最新验收记录：' + latest['status'] + '；版本 ' + latest['revision_id'] + '；编号 ' + latest['id']]
        for check in json.loads(latest['items_json']).get('checks', []):
            lines += ['- 检查 ' + check['check_id'] + '：' + check['status']
                      + ('；引用原运行 ' + check['reuse_source']['run_id'] if check.get('reused') else
                         '；本次实际执行' if check.get('executed') else '；原记录未区分执行方式')]
    from .learning import work_learning
    learning = work_learning(store.connection, change['id'])
    if learning.get('applications'):
        lines += ['', '## 经验采用与反馈', '']
        for application in learning['applications']:
            decision = application['decision']
            lines += ['- ' + application['experience']['topic'] + '：' + decision['decision'],
                      '  - 实际影响：' + decision.get('influence', {}).get('description', '原记录未说明具体影响'),
                      '  - 效果：' + decision.get('feedback', {}).get('outcome', '尚无后续反馈')]
    lines += ['', '## 知识变化', '']
    lines += ['- ' + item['topic'] + '：' + item['disposition'] + '；依据：' + item['reason'] for item in impacts]
    if review:
        lines += ['- ' + ', '.join(item['views']) + '：' + item['result'] + '；依据：' + item['basis'] for item in review]
    elif not impacts:
        lines += ['本方案未登记知识影响；这不代表已调查所有业务含义。']
    lines += ['', '## 本次结果与接手', '', '本次记录：' + status + '／' + str(result.get('outcome', 'observed')), '']
    next_step = ('本项已历史封存；使用 evolve-workflow 查看当前适用性或下一目标。' if change['state'] == 'archived' else
                 '使用 evolve-workflow 的 next 核对当前条件、原授权及准确接手动作；实施、验收和封存分别处理。')
    lines += [next_step, '', '## 来源与限制', '', '方案摘要：' + revision['plan_digest'],
              '任务定义摘要：' + revision['definition_digest'], '历史数据库：evolve/history.db',
              '此视图不授予修改授权，也不替代正式知识批准。', '']
    prefix = 'evolve/changes/' + change['id'] + '/'
    files = {prefix + 'summary.md': '\n'.join(lines).encode()}
    if document:
        spec_lines = ['# 规格：' + change['title'], '', *header]
        for key, title in (('problem', '问题'), ('goals', '目标'), ('non_goals', '边界'), ('behavior', '行为'),
                           ('constraints', '约束'), ('tradeoffs', '取舍'), ('test_decisions', '检查决定'), ('open_questions', '未决问题')):
            value = document['spec'].get(key)
            if not value:
                continue
            spec_lines += ['## ' + title, '']
            spec_lines += ['- ' + (item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)) for item in value] if isinstance(value, list) else [value]
            spec_lines.append('')
        files[prefix + 'spec.md'] = '\n'.join(spec_lines).encode()
        task_lines = ['# 任务：' + change['title'], '', *header]
        keys = {definition['local_key']: 'T' + str(index) for index, definition in enumerate(definitions)}
        if any(definition.get('dependencies') for definition in definitions):
            task_lines += ['## 任务依赖', '', '箭头表示方案中明确声明的前置条件；具体依据见下方任务。', '', '```mermaid', 'flowchart TD']
            for definition in definitions:
                label = (html.escape(definition.get('task_code', definition['local_key']), quote=True) + '<br/>'
                         + html.escape(definition['title'], quote=True).replace('\n', ' ').replace('\r', ' '))
                task_lines.append('  ' + keys[definition['local_key']] + '["' + label + '"]')
            for definition in definitions:
                for dependency in definition.get('dependencies', []):
                    label = {'task_completed': '任务完成', 'verification_passed': '验收通过', 'artifact_available': '产物可用'}[dependency['condition_kind']]
                    task_lines.append('  ' + keys[dependency['upstream_task']] + ' -->|' + label + '| ' + keys[definition['local_key']])
            task_lines += ['```', '']
        for task, definition in zip(tasks, definitions):
            task_lines += ['## ' + definition.get('task_code', definition['local_key']) + ' ' + definition['title'], '',
                '记录状态：' + task['state'], '完成条件：' + definition['completion'],
                '验证方法：' + definition.get('validation', '按已声明验收条件观察。'),
                '范围：' + ', '.join(definition['scope']),
                '只读输入：' + ', '.join(definition.get('context', {})),
                '依赖输入：' + ', '.join(definition.get('dependency_inputs', [])),
                '依赖：' + json.dumps(definition.get('dependencies', []), ensure_ascii=False), '']
        files[prefix + 'tasks.md'] = '\n'.join(task_lines).encode()
        if verifications:
            report = ['# 验收记录：' + change['title'], '', *header]
            for item in verifications:
                details = json.loads(item['items_json'])
                report += ['## ' + item['id'], '', '记录状态：' + item['status'], '方案版本：' + item['revision_id'],
                    '观察时间：' + item['observed_at'], '来源运行：' + item['source_run_id'], '', '### 验收条件与证据', '']
                for coverage in details.get('coverage', []):
                    report += ['- ' + coverage['ac_id'] + '：' + coverage['observed_status'] + '；依据：' + coverage['basis'],
                        '  - 检查映射：' + coverage['check_mapping'] + '；' + ', '.join(
                            check['check_id'] + '=' + check['status'] + ' [' + str(check['evidence_id']) + ']' for check in coverage['checks'])]
                if not details.get('coverage'):
                    report += ['原记录未提供逐条件检查映射，保留其原有审查观察。']
                report += ['', '### 检查与审查', '']
                report += ['- 检查 ' + check['check_id'] + '：' + check['status'] + '；证据 ' + str(check['evidence_id'])
                           + ('；引用原运行 ' + check['reuse_source']['run_id'] if check.get('reused') else
                              '；本次实际执行' if check.get('executed') else '；原记录未区分执行方式') for check in details.get('checks', [])]
                modes = {value['axis']: value['mode'] for value in details.get('review_provenance', [])}
                for review_item in details.get('reviews', []):
                    report += ['- ' + review_item['axis'] + '：' + review_item['observer'] + '；类型 ' + modes.get(review_item['axis'], 'not_recorded'),
                               '  - ' + review_item['summary']]
                    report += ['  - 发现 ' + finding['id'] + '：' + finding['impact'] for finding in review_item['findings']]
                report += ['', '当前文件、未决执行与知识收尾仍须按实际现场核对；历史通过不代表当前仍通过。', '']
            files[prefix + 'verification.md'] = '\n'.join(report).encode()
    return source, files


def prepare(store, run_id, result, status):
    run = store.one('SELECT * FROM phase_runs WHERE id=?', (run_id,))
    data = json.loads(run['input_json'])['request']['input']
    change_id = result.get('change_id') or data.get('change_id')
    if not change_id and result.get('original_run_id'):
        old = store.one('SELECT input_json FROM phase_runs WHERE id=?', (result['original_run_id'],))
        change_id = json.loads(old[0])['request']['input'].get('change_id') if old else None
    if not change_id:
        return None
    change = store.one('SELECT * FROM changes WHERE id=?', (change_id,))
    if not change:
        return None
    revision = store.one('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],))
    source, files = render(store, change, revision, run_id, result, status)
    owned = {}
    for previous in manifests(store.connection, store.meta['project_id'], change_id):
        for item in previous['files']:
            owned.setdefault(item['path'], set()).add(item['digest'])
    records = []
    for name, content in files.items():
        path = view_path(store.root, name)
        authority = store.one("SELECT kind FROM artifacts WHERE path=? AND kind IN ('knowledge','config')", (name,))
        actual = current_digest(path)
        records.append({'path': name, 'digest': store.blob(content), 'expected_digest': actual,
                        'conflict': bool(authority or actual is not None and actual not in owned.get(name, set()))})
    manifest = {'project_id': store.meta['project_id'], 'workspace_epoch': store.meta['workspace_epoch'],
        'change_id': change_id, 'revision_id': revision['id'], 'source': source, 'files': records}
    store.event(run_id, 'change_view_prepared', manifest)
    return manifest


def install(store, manifest):
    if not manifest:
        return
    # Primary facts are already sealed. A view failure never turns them into a failed write.
    try:
        store.assert_current_database()
        current = dict(store.connection.execute('SELECT key,value FROM project_meta'))
        if any(current[key] != manifest[key] for key in ('project_id', 'workspace_epoch')):
            return
        latest = next(manifests(store.connection, current['project_id'], manifest['change_id']), None)
        if latest != manifest:
            return
        for item in manifest['files']:
            path = view_path(store.root, item['path'])
            if item['conflict'] or current_digest(path) != item['expected_digest']:
                continue
            if store.one("SELECT 1 FROM artifacts WHERE path=? AND kind IN ('knowledge','config')", (item['path'],)):
                continue
            content = store.one('SELECT content FROM blobs WHERE digest=?', (item['digest'],))
            if not content or digest(content[0]) != item['digest']:
                continue
            durable_write(path, content[0])
    except (EvolveError, OSError, ValueError, TypeError, KeyError):
        return


def observe(root, change_id):
    from .reading import history_snapshot
    try:
        with history_snapshot(root) as (connection, meta):
            manifest = next(manifests(connection, meta['project_id'], change_id), None)
            if not manifest:
                return {'status': 'not_prepared', 'change_id': change_id}
            latest_run = None
            for run in connection.execute('SELECT * FROM phase_runs ORDER BY rowid DESC'):
                data = json.loads(run['input_json'])['request']['input']
                result = json.loads(run['result_json']) if run['result_json'] else {}
                if (result.get('change_id') or data.get('change_id')) == change_id:
                    latest_run = run
                    break
            files = []
            for item in manifest['files']:
                actual = current_digest(view_path(root, item['path']))
                state = 'ready' if actual == item['digest'] else 'missing' if actual is None else 'conflict' if item['conflict'] or actual != item['expected_digest'] else 'stale'
                files.append({'path': item['path'], 'status': state, 'content_digest': item['digest'], 'actual_digest': actual})
            current_source = bool(latest_run and latest_run['id'] == manifest['source']['run_id']
                                  and latest_run['result_digest'] == manifest['source']['result_digest'])
            return {'status': 'ready' if current_source and all(item['status'] == 'ready' for item in files) else 'pending',
                'change_id': change_id, 'source': manifest['source'], 'files': files,
                'source_is_latest_record': current_source,
                'authority': 'derived_from_history', 'rebuild': {'action': 'maintain', 'method': 'export',
                    'input': {'kind': 'change', 'change_id': change_id}}, 'authorization_granted': False}
    except (EvolveError, OSError, ValueError, TypeError, KeyError) as error:
        return {'status': 'unavailable', 'change_id': change_id,
                'diagnostic': {'code': getattr(error, 'code', 'VIEW_UNAVAILABLE'), 'reason': redact(str(error))}}


def rebuild(root, payload):
    from .requests import normalize, require_effect
    from .store import Store
    from .workspace import writer_lock
    request = normalize(payload)
    require_effect(request, 'project_records')
    if set(request['input']) - {'kind', 'change_id'}:
        raise EvolveError('VIEW_INPUT', 'Change view rebuild accepts kind and change_id; it does not overwrite human edits or export arbitrary paths')
    root = Path(root).resolve()
    with writer_lock(root):
        store = Store(root)
        try:
            run_id, previous = store.start(request, action='maintain', method='export', owner='evolve-maintain')
            if previous is not None:
                return previous
            target = request['input'].get('change_id')
            rows = store.connection.execute('SELECT * FROM changes WHERE id=? OR code=? OR title=?', (target, target, target)).fetchall()
            if len(rows) != 1:
                error = EvolveError('TARGET', 'Choose one recorded change for its derived view')
                store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                error.committed = True
                raise error
            return store.finish(run_id, {'committed': True, 'outcome': 'view_refresh_recorded', 'change_id': rows[0]['id'],
                'business_commands_run': False, 'authority_changed': False})
        finally:
            store.close()
