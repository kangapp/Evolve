"""Read-only execution conditions and evidence-bound workflow handoffs."""
from pathlib import Path
import shlex
import sqlite3

from .errors import EvolveError
from .package import OWNERS, ROOT


def readiness(root, project):
    connected = project.get('state') == 'connected'
    from .protection import control_issues
    issues = control_issues(root, project) if connected else []
    if project.get('state') == 'maintenance':
        issues.append({'code': 'MAINTENANCE_ACTIVE', 'path': '.evolve-local/control/maintenance.json',
                       'affects': ['project_records', 'knowledge', 'business_files', 'checks', 'external'],
                       'reason': 'Resume the original maintenance plan and its unique apply request.'})
    if project.get('state') == 'unavailable':
        issues.append({'code': project.get('diagnostic', {}).get('code', 'OBSERVATION_REQUIRED'),
                       'path': 'evolve/history.db', 'affects': ['project_records', 'knowledge', 'business_files', 'checks', 'external'],
                       'reason': project.get('diagnostic', {}).get('message', 'Archive diagnosis requires maintenance.')})
    actions = {}
    for action in ('query', 'project_records', 'knowledge', 'business_files', 'checks', 'external'):
        blockers = [i for i in issues if action in i['affects']]
        actions[action] = {'status': 'blocked' if blockers or project.get('state') == 'unavailable' else 'ready' if connected or action == 'query' else 'requires_connection',
                           'blockers': blockers}
    environments = []
    if connected:
        import tomllib
        from .check_environment import observe
        from .workspace import inside
        config = tomllib.loads(inside(root, 'evolve/config.toml').read_text())
        environments = [observe(root, check) for check in config.get('verification', {}).get('checks', [])]
    return {'actions': actions, 'issues': issues, 'checks_executed': False,
            'execution_environment': {'checks': environments, 'commands_executed': False,
                'status': 'blocked' if any(item['status'] != 'ready' for item in environments) else 'ready' if connected else 'requires_connection'},
            'scope': 'Observed package/project prerequisites; business acceptance and host loading are separate.'}


def handoff(root, action, method=None, *, target=None, reason, prompt=None):
    owner = 'evolve-' + OWNERS[action]
    argv = ['python3', str(ROOT / 'runtime/evolve.py'), '--project', str(Path(root).resolve()), action]
    if target:
        argv.append(target)
    if method:
        argv += ['--method', method]
    return {'owner_skill': owner, 'action': action, 'method': method, 'target': target, 'reason': reason,
            'prompt': prompt or f'使用 {owner}，{reason}',
            'query_command': shlex.join(argv) if action in ('status', 'next', 'resume', 'history') or (action, method) == ('maintain', 'doctor') else None,
            'authorization_granted': False}


def error_handoff(root, code, details=None):
    if code == 'CONTEXT_CHANGED':
        execution = (details or {}).get('execution', {})
        return handoff(root, 'update', 'revise', target=execution.get('change_id'),
            reason='核对具体只读输入变化和原判据，呈现准确受影响方案并按实际决定修订；保留已有原行为证据。')
    if code == 'CHECK_ENVIRONMENT':
        return handoff(root, 'maintain', 'doctor', reason='核对回执中的解释器、声明依赖和环境前置检查；配置变更由 evolve-init 展示准确候选，环境恢复后继续原任务。')
    if code == 'WORKSPACE_CHANGED':
        execution = (details or {}).get('execution', {})
        return handoff(root, 'resume', target=execution.get('change_id'),
            reason='核对回执中的变化文件及已发生效果；业务文件已提交且没有未决操作时，确认现场后以新请求、files=[]及准确 observations 继续检查。')
    if code == 'SESSION_PACKAGE_MISMATCH':
        return handoff(root, 'status', reason='在新会话加载当前完整插件，重新核对实际包摘要后继续原工作。')
    if code in ('PACKAGE_INCOMPLETE', 'PACKAGE_VERSION', 'DUPLICATE_INSTALLATION'):
        return handoff(root, 'maintain', 'doctor', reason='核对完整安装包及宿主加载位置，按更新指南修复安装后继续。')
    if code in ('SCHEMA_VERSION', 'UPGRADE_REQUIRED'):
        return handoff(root, 'maintain', 'doctor', reason='核对旧包与档案协议，保留原资料并准备支持的显式升级方案。')
    if code in ('PROJECT_INVALID', 'PROJECT_IDENTITY', 'HISTORY_DIVERGED') or code.startswith('CONFIG_'):
        return handoff(root, 'maintain', 'doctor', reason='保留档案和配置的真实诊断，先核对身份、历史与保护资料，再准备支持的恢复方案。')
    if code in ('PROTECTION_UNKNOWN', 'INITIALIZATION_UNVERIFIED', 'REPAIR_UNSAFE', 'PROJECT_COLLISION', 'PROJECT_INCOMPLETE', 'NEEDS_RECOVERY', 'MAINTENANCE_ACTIVE'):
        return handoff(root, 'maintain', 'doctor', reason='诊断原操作与控制资料；中断沿原请求恢复，已结束的缺失资料先评估 repair 方案，证据不足保留受阻。')
    if code == 'NOT_CONNECTED':
        return handoff(root, 'status', reason='说明本次目标并选择必要接入范围，再由 evolve-init 接入。')
    if code.startswith('KNOWLEDGE'):
        return handoff(root, 'status', reason='恢复具体知识候选、实际来源与必需交付，核对后由相应 owner 继续。')
    return handoff(root, 'status', reason='核对当前目标、实际失败与未决操作，再选择有证据支持的下一步。')


def next_handoff(root, project, conditions, context=None):
    if project.get('state') == 'unavailable':
        return handoff(root, 'maintain', 'doctor', reason='档案当前不可读取；保留原始诊断与保护资料，准备支持的恢复方案，恢复前不推进业务工作。')
    if conditions['issues']:
        return error_handoff(root, conditions['issues'][0]['code'])
    if project.get('state') != 'connected':
        return handoff(root, 'status', reason='说明希望完成的修改；未接入的已有项目按目标调查，空项目先明确目标与最小验收行为。')
    if project.get('pending_runs'):
        return handoff(root, 'maintain', 'doctor', reason='先核实仍在执行或未收尾的原操作，按原 owner 恢复。')
    if context and context.get('selection') == 'required':
        return handoff(root, 'status', reason='存在多个工作目标，请按标题选择需要继续的一项。')
    selected = project.get('changes', [])
    active = [c for c in selected if c['state'] not in ('archived', 'cancelled')]
    if len(active) == 1:
        change = active[0]
        target = change['id']
        if context and context.get('suggested_action') in ('inspect_workspace_change', 'accept_revision', 'review_task_conditions'):
            return handoff(root, 'resume', target=target, reason='核对原方案、现场变化及尚未满足的任务条件后继续。')
        if all(t['state'] == 'done' for t in change['tasks']):
            return handoff(root, 'verify', 'run', target=target, reason='实施已登记，核对必需知识与当前实际成果，完成最新整体验收后由 evolve-archive 封存。')
        return handoff(root, 'apply', 'implement', target=target, reason='恢复已接受方案、准确任务和有效授权，继续实施、检查及后续验收。')
    if len(active) > 1:
        return handoff(root, 'status', reason='按标题选择需要推进的工作项。')
    return handoff(root, 'propose', 'create', reason='描述下一项需求；先形成具体方案和验收条件。')


def verified_handoff(root, data):
    if data.get('input_bindings', {}).get('task_id'):
        return handoff(root, 'next', target=data.get('change_id'), reason='本任务验收已完成，读取当前就绪任务及整项剩余条件。')
    from .reading import history_snapshot
    from .knowledge_impact import closure_gate
    try:
        with history_snapshot(root) as (connection, _):
            change = connection.execute('SELECT * FROM changes WHERE id=?', (data.get('change_id'),)).fetchone()
            if change:
                revision = connection.execute('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],)).fetchone()
                closure_gate(connection, root, change, revision)
    except (EvolveError, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        return handoff(root, 'sync', 'assess', reason='当前验收已保存，必需知识尚需交付或核对；恢复具体文档候选，完成实际文档验收后再做知识收尾和最新整体验收。')
    return handoff(root, 'archive', 'close', target=data.get('change_id'), reason='核对最新整体验收和全部必需交付，在当前现场封存完成结果。')


def workflow_view(root, action, method, data, *, error=None):
    owner = 'evolve-' + OWNERS.get(action, 'workflow')
    outcome = data.get('outcome')
    status = 'blocked' if error else 'observed' if not data.get('run_id') and (data.get('committed') is False or outcome in ('observed', 'no_match', None)) else 'completed'
    remaining, following = [], []
    goal_complete = outcome == 'archived'
    if error:
        following = [error_handoff(root, error['code'], error.get('details'))]
        remaining = [error['message']]
    elif action == 'apply' and method.startswith('external.'):
        if outcome == 'external_candidate_prepared':
            status = 'waiting_confirmation'
            remaining = ['候选已固定，尚未派发；核对具体目标和差异，按实际批准继续。']
            following = [handoff(root, 'apply', method, reason=remaining[0])]
        elif data.get('effect_outcome') in ('unknown', 'running') or data.get('effect_record', {}).get('terminal_confirmed') is False:
            status = 'blocked'
            remaining = ['实际外部结果尚未确认，使用原操作身份只读核实。']
            following = [{**handoff(root, 'apply', 'external.reconcile', reason=remaining[0]), 'operation_id': data.get('operation_id')}]
        elif data.get('effect_outcome') == 'failed':
            status = 'blocked'
            remaining = ['已知失败及实际效果保留，修正或补偿需新的具体方案。']
            following = [handoff(root, 'propose', 'create', reason=remaining[0])]
        elif data.get('task_completed') is False:
            status = 'blocked'
            remaining = ['外部派发已结束，任务检查或当前目标条件尚未通过；核对真实失败，必要修正按具体方案执行，再沿原操作仅复验，保留已发生效果。']
            following = [{**handoff(root, 'apply', 'external.execute', reason=remaining[0],
                prompt='使用 evolve-apply 核对原外部操作的失败检查和当前目标，按有效方案修正后，以原 operation_id 和 stage=checks 继续检查，不重派发已执行写入。'),
                'stage': 'checks', 'operation_id': data.get('operation_id')}]
        elif data.get('task_completed'):
            following = [handoff(root, 'verify', 'run', target=data.get('change_id') or data.get('input_bindings', {}).get('change_id'),
                                 reason='外部任务检查已完成，按实际业务目标验收及封存。')]
        else:
            following = [handoff(root, 'status', reason='外部观察或阶段已保存，核对原操作的任务检查、业务验收和实际效果后继续。')]
    elif outcome in ('review_cleanup_planned', 'review_cleanup_partial', 'review_materials_interrupted'):
        status = 'waiting_confirmation' if outcome == 'review_cleanup_planned' else 'blocked'
        remaining = ['核对准确资料集合、保留原因和已发生删除；只按有效授权处理可重建辅助副本。']
        following = [handoff(root, 'maintain', 'materials', reason=remaining[0])]
    elif outcome == 'partial':
        status = 'paused'
        remaining = data.get('progress', {}).get('remaining', ['检查、验收及封存尚未完成。'])
        following = [handoff(root, 'resume', target=data.get('change_id'), reason='恢复已保存进度和现场，继续原目标。')]
    elif outcome in ('blocked', 'checks_not_passed') or data.get('status') in ('failed', 'blocked'):
        status = 'blocked'
        remaining = ['核对实际失败，修正后重新检查和验收。']
        following = [handoff(root, 'resume', target=data.get('change_id'), reason=remaining[0])]
    elif outcome in ('knowledge_proposed', 'baseline_proposed', 'config_candidate', 'scope_confirmation_required'):
        status = 'waiting_confirmation'
        remaining = ['具体候选仍需内容检查、实际决定及应用后验收。']
        following = [handoff(root, 'status', target=data.get('proposal_id'), reason='审阅已展示的准确候选，按实际决定继续。')]
    elif outcome in ('restore_planned', 'upgrade_planned', 'repair_planned') or data.get('plan_digest') and action == 'maintain':
        status = 'waiting_confirmation'
        following = [handoff(root, 'maintain', method, reason='核对已展示的准确维护集合，沿原 plan_id、plan_digest 和唯一 apply 请求继续。')]
    elif outcome == 'cancelled':
        status = 'cancelled'
        following = [handoff(root, 'status', reason='查看已保留的结果和其他工作；取消不撤销已发生效果。')]
    elif outcome == 'external_future_dispatch_revoked':
        status = 'cancelled'
        remaining = ['未来派发已取消，已发生或未知效果仍需核实。']
        following = [{**handoff(root, 'apply', 'external.reconcile', reason=remaining[0]), 'operation_id': data.get('operation_id')}]
    elif outcome == 'archived':
        following = [handoff(root, 'status', reason='本目标已封存；按需查看其他工作或描述下一项目标。')]
    elif action == 'propose':
        status = 'waiting_confirmation'
        remaining = ['方案保存完成；实施需要实际接受的具体范围。']
        following = [handoff(root, 'apply', 'implement', target=data.get('change_id'), reason='在有效方案与授权范围内实施，并继续检查、验收和封存。')]
    elif action == 'apply':
        remaining = ['任务实施结果仍需实际验收、知识收尾及整项封存。']
        following = [handoff(root, 'verify', 'run', target=data.get('change_id'), reason=remaining[0])]
    elif action == 'verify' and method == 'run':
        remaining = ['核对必需知识和整体验收范围；任务验收与整项封存分别处理。']
        following = [verified_handoff(root, data)]
    elif action == 'init':
        completed = outcome == 'knowledge_initial_delivery_completed'
        remaining = [] if completed else ['记录接入或候选处理已完成，完整知识交付需调查、实际文档验收及 init.complete。']
        following = [handoff(root, 'propose' if completed else 'status', 'create' if completed else None,
                            reason='描述需要修改的目标，形成方案与验收条件。' if completed else remaining[0])]
    elif data.get('update_check'):
        following = [handoff(root, 'maintain', 'doctor', reason=data['update_check']['next_prompt'])]
    elif outcome in ('restored', 'upgraded', 'repaired'):
        following = [handoff(root, 'status', reason='维护已完成，核对新 epoch 的执行条件及原工作，再沿有效授权继续。')]
    else:
        context = data.get('context', {})
        project = data.get('project') or context.get('project')
        if data.get('execution'):
            following = [{key: data['execution'][key] for key in ('owner_skill', 'action', 'method', 'target', 'reason', 'prompt', 'query_command', 'authorization_granted')}]
        elif project:
            following = [next_handoff(root, project, data.get('readiness') or readiness(root, project), context)]
        else:
            following = [handoff(root, 'next', reason='核对本阶段结果与原工作目标，选择下一步。')]
    labels = {'observed': '只读观察完成', 'completed': '本阶段完成', 'waiting_confirmation': '等待具体决定',
              'paused': '已暂停', 'blocked': '受阻', 'cancelled': '已取消'}
    if data.get('index_status') in ('manual_conflict', 'changed_since_prepared', 'pending'):
        remaining.append('主记录已保存；review 索引尚未更新，保留手工内容，使用 evolve-maintain 核对并显式重建。')
    view = data.get('change_view')
    if view and view['status'] != 'ready':
        remaining.append('主执行记录按实际结果保存；派生工作文档尚未更新，保留冲突并由 evolve-maintain 显式重建。')
        if action == 'maintain' and method == 'export':
            status = 'blocked'
    return {'owner_skill': owner, 'action': action, 'method': method, 'phase_status': status,
            'marker': f'[Evolve · {owner} · {labels[status]}]', 'call_finished': True,
            'stage_complete': status in ('observed', 'completed', 'cancelled'), 'goal_complete': goal_complete,
            'result': outcome or ('error' if error else 'observed'), 'remaining': remaining, 'next_steps': following,
            'evidence': {k: data[k] for k in ('run_id', 'operation_id', 'verification_id', 'application_id', 'change_id') if data.get(k)},
            'authorization_granted': False}
