"""Public preparation hints from observed facts; hints never grant permission."""
import json
from pathlib import Path
import shlex

from .errors import EvolveError
from .package import AVAILABLE, METHODS, OWNERS, ROOT


INPUT_FIELDS = {
    ('init', 'connect'): [],
    ('propose', 'create'): ['title', 'plan', 'completion', 'scope', 'acceptance', 'required_checks', 'presentation'],
    ('update', 'revise'): ['reason', 'proposal'],
    ('apply', 'implement'): ['files'],
    ('apply', 'external.execute'): ['stage'],
    ('apply', 'external.reconcile'): ['operation_id'],
    ('verify', 'run'): ['reviews'],
    ('archive', 'close'): ['verification_id'],
    ('sync', 'assess'): ['change_id', 'revision_id', 'observations'],
    ('init', 'baseline.propose'): ['path', 'expected_digest', 'content', 'presentation', 'acceptance'],
    ('sync', 'propose'): ['path', 'expected_digest', 'content', 'presentation', 'acceptance'],
    ('learn', 'promote'): ['stage'],
    ('maintain', 'clean'): ['stage', 'paths'],
}


def request_help(action, method):
    from .knowledge_impact import REVIEW_VIEWS
    pure = action in ('status', 'next', 'resume', 'history') or (action, method) in (
        ('maintain', 'doctor'), ('maintain', 'materials'), ('init', 'templates'), ('learn', 'search'))
    return {'owner_skill': 'evolve-' + OWNERS.get(action, 'workflow'),
        'available': action + '.' + method in AVAILABLE, 'pure_query': pure,
        'available_methods': METHODS.get(action, []), 'request_required': not pure,
        'required_request_objects': [] if pure else ['authorization', 'input'],
        'required_input_fields': INPUT_FIELDS.get((action, method), []),
        'optional_input_fields': ['fresh_checks'] if action in ('apply', 'verify') and method in ('implement', 'run') else [],
        'knowledge_review_views': list(REVIEW_VIEWS) if action in ('propose', 'update', 'sync') else [],
        'automatic_fresh_bindings': [] if pure else ['request_id', 'project_id', 'expected_workspace_epoch',
            'current revision/task/definition and expected_versions when this action consumes work'],
        'retry': 'Preserve the original request_context, input_bindings and exact input; never prepare a retry from new state.',
        'protocol': str(ROOT / 'shared/protocol.md'),
        'branch_protocol': str(ROOT / 'shared/external-work.md') if method.startswith('external.') else
            str(ROOT / 'shared/knowledge-candidates.md') if (action, method) in (('init', 'baseline.propose'), ('sync', 'propose')) else None,
        'authorization_granted': False}


def _current_verification(root, change, snapshot):
    if not snapshot:
        return None, None
    from .reading import history_snapshot
    from .revisions import eligible_verifications
    from .continuation import sealed_result
    from .knowledge_impact import closure_gate
    from .work import verification_source
    with history_snapshot(root) as (connection, _):
        revision = connection.execute('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],)).fetchone()
        latest = next((item for item in eligible_verifications(connection, change['id'], revision['id'])
                       if json.loads(item['items_json']).get('task_id') is None), None)
        if (not latest or latest['status'] != 'passed' or json.loads(latest['fingerprint_json'])['digest'] != snapshot['digest']):
            return None, None
        source = verification_source(connection, latest)
        if not source:
            return None, None
        _, _, result = sealed_result(connection, {'run_id': source['id'], 'result_digest': source['result_digest']})
        if result.get('verification_id') != latest['id']:
            return None, None
        try:
            closure_gate(connection, root, change, revision)
        except EvolveError as error:
            return latest['id'], {'code': error.code, 'reason': str(error)}
        return latest['id'], None


def execution_view(root, context, conditions):
    from .guidance import handoff, next_handoff
    from .work import context_changes
    root = Path(root).resolve()
    project = context['project']
    step = next_handoff(root, project, conditions, context)
    view = {'status': 'needs_input', 'blockers': [], 'request_input': {},
            'authorization_granted': False, 'source_checkpoint': project.get('checkpoint')}
    changes = project.get('changes', [])
    selected = context.get('selection') == 'selected' and context.get('target_kind') == 'change' and len(changes) == 1
    if project.get('state') != 'connected' and not conditions['issues']:
        step = handoff(root, 'init', 'connect', reason='按本次目标明确必要接入范围，配置实际检查，再形成方案。')
    if selected and not conditions['issues'] and not project.get('pending_runs'):
        change = changes[0]
        tasks = change['tasks']
        view['target_title'] = change['title']
        definitions = {task['id']: task.get('definition', {}) for task in tasks}
        observation = context.get('workspace_observation', {})
        snapshot = observation.get('current') if observation.get('status') == 'observed' else None
        task = next((task for task in tasks if task['id'] == context.get('suggested_task_id')), None)
        task = task or (tasks[0] if len(tasks) == 1 else None)
        action = context.get('suggested_action')
        if change['state'] in ('archived', 'cancelled'):
            step = handoff(root, 'status', target=change['id'], reason='查看此目标已保存的完成截点；新的修改另建具体方案。')
        elif action == 'accept_revision':
            step = handoff(root, 'update', 'revise', target=change['id'], reason='按实际决定接受已呈现的准确修订，再实施。')
            view['revision_candidate'] = change.get('plan', {}).get('candidate')
            view['revision_candidate_digest'] = change.get('plan', {}).get('candidate_digest')
        elif observation.get('scope_changes') or observation.get('status') != 'observed':
            view['status'] = 'requires_workspace_review'
            view['scope_changes'] = observation.get('scope_changes', [])
            step = handoff(root, 'resume', target=change['id'], reason='核对已列出的当前差异及原范围，按真实观察选择仅检查或范围内修正。')
        else:
            changed = [item for definition in definitions.values() for item in context_changes(root, definition)]
            unresolved = [item for definition in definitions.values() for item in definition.get('input_impacts', []) if item['requires_review']]
            if changed or unresolved:
                step = handoff(root, 'update', 'revise', target=change['id'], reason='核对原输入变化及任务影响，呈现准确依赖或独立处理依据并修订。')
                view['blockers'] = [{'code': 'CONTEXT_CHANGED', **item} for item in changed] + unresolved
            elif action == 'verify_task' and task:
                step = handoff(root, 'verify', 'run', target=change['id'], reason='核对已实现的上游任务，完成其实际验收后继续后继。')
                view['request_input']['task_key'] = task['local_key']
            elif all(task['state'] == 'done' for task in tasks):
                verification, knowledge = _current_verification(root, change, snapshot)
                if verification and not knowledge:
                    step = handoff(root, 'archive', 'close', target=change['id'], reason='最新整体验收与知识收尾适用于当前现场，核对并封存此目标。')
                    view['request_input']['verification_id'] = verification
                elif knowledge:
                    step = handoff(root, 'sync', 'assess', reason='完成所列知识候选及实际文档核验，再核对全部知识影响并封存。')
                    view['request_input'].update(change_id=change['id'], revision_id=change['current_revision'])
                    view['blockers'].append(knowledge)
                    view['planned_knowledge_review'] = next((definition['knowledge_review'] for definition in definitions.values()
                                                             if definition.get('knowledge_review') is not None), None)
                else:
                    step = handoff(root, 'verify', 'run', target=change['id'], reason='对当前实际成果准备规格与规范观察，执行最新整体验收。')
                    task = None
            elif task and step['action'] == 'apply':
                definition = definitions[task['id']]
                owner = definition.get('responsible_action', 'apply')
                method = {'apply': 'implement', 'init': 'baseline.propose', 'sync': 'propose', 'learn': 'promote'}[owner]
                if owner == 'apply' and definition.get('execution_kind') == 'external_write':
                    method = 'external.execute'
                step = handoff(root, owner, method, target=change['id'] if owner == 'apply' else None,
                    reason='恢复此就绪任务的已接受范围与实际授权，准备具体候选并继续。')
                if change['complexity'] == 'complex':
                    view['request_input']['task_key'] = task['local_key']
                if owner != 'apply':
                    view['request_input'].pop('task_key', None)
                    view['request_input']['delivery'] = {'role': 'required', 'change_id': change['id'],
                        'revision_id': change['current_revision'], 'task_id': task['id'],
                        'definition_digest': task['definition_digest'], 'acceptance_ids': []}
                    view['delivery_subject'] = {'scope': definition['scope'], 'acceptance': definition['acceptance'],
                        'selection_required': 'Choose only the acceptance conditions actually covered by this candidate.'}
                    if owner == 'learn':
                        view['request_input']['stage'] = 'propose'
                elif method == 'external.execute':
                    saved = context.get('task_result') or next((item.get('result') for item in context.get('task_contexts', [])
                                                               if item['task_id'] == task['id']), None) or {}
                    operation_id = saved.get('external_operation_id')
                    view['request_input']['stage'] = 'checks' if operation_id else 'prepare'
                    if operation_id:
                        view['request_input']['operation_id'] = operation_id
            required = definitions.get(task['id'], {}).get('required_checks', []) if task else []
            if step['action'] == 'verify' and not task:
                required = list(snapshot.get('checks', [])) if snapshot else []
                required = [item['id'] for item in required]
            missing = [item for item in conditions.get('execution_environment', {}).get('checks', [])
                       if item['check_id'] in required and item['status'] != 'ready']
            if missing and step['action'] in ('apply', 'verify', 'init', 'sync', 'learn'):
                view['status'] = 'blocked'
                view['blockers'].extend({'code': 'CHECK_ENVIRONMENT', 'observation': item} for item in missing)
                step = handoff(root, 'maintain', 'doctor', reason='此目标必需检查的环境缺失，先按列出的入口与依赖恢复环境，再继续原工作。')
            if step['action'] == 'verify':
                subject = snapshot
                if task and change['complexity'] == 'complex':
                    subject = next((item['workspace_observation'].get('current') for item in context.get('task_contexts', [])
                                    if item['task_id'] == task['id']), None)
                acceptance = definitions[task['id']].get('acceptance', []) if task else change.get('plan', {}).get('document', {}).get('acceptance', [])
                if task is None:
                    acceptance = list({item['id']: item for definition in definitions.values()
                                       for item in definition.get('acceptance', [])}.values())
                view['review_subject'] = {'fingerprint_digest': subject['digest'] if subject else None,
                    'scope': list(subject.get('scope', {})) if subject else [], 'acceptance': acceptance,
                    'review_policy': definitions[task['id']].get('review_policy', 'self_allowed') if task else
                        'independent' if any(definition.get('review_policy') == 'independent' for definition in definitions.values()) else 'self_allowed',
                    'required_axes': ['spec', 'standards'], 'observations_required': True}
        view['requires_actual_plan_acceptance'] = not change.get('plan', {}).get('accepted', False)
    if conditions['issues'] or project.get('pending_runs'):
        view['status'] = 'blocked'
        view['blockers'] = conditions['issues'] or [{'code': 'PENDING_RUN', 'runs': project['pending_runs']}]
    view.update(step)
    view['request_help'] = request_help(step['action'], step['method'] or 'show')
    argv = [str(ROOT / 'runtime/evolve.py'), '--project', str(root), step['action']]
    if step.get('target'):
        argv.append(step['target'])
    if step.get('method'):
        argv += ['--method', step['method']]
    if not view['request_help']['pure_query']:
        argv += ['--request', '-']
    view['command'] = shlex.join(['python3', *argv])
    return view
