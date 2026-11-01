"""Pure project context restoration; no commands, indexing or writer takeover."""
import json
from pathlib import Path

from .continuation import sealed_result
from .errors import EvolveError
from .reading import current_state, history_snapshot
from .store import now
from .work import fingerprint



def restored_run(connection, row, change_id=None):
    body, result = json.loads(row['input_json'])['request'], None
    if row['status'] != 'started':
        _, body, result = sealed_result(connection, {'run_id': row['id'], 'result_digest': row['result_digest']})
    revoked = False
    for event in connection.execute("SELECT payload_json FROM events WHERE kind='authorization_revoked'"):
        value = json.loads(event[0])
        revoked |= value.get('request_id') == row['request_id'] or (change_id is not None and value.get('change_id') == change_id)
    from .learning import learning_status
    return {'learning': learning_status(connection, row['id']), 'run_id': row['id'], 'action': row['action'], 'status': row['status'],
            'result_digest': row['result_digest'], 'result': result,
            'authorization': body['authorization'], 'authorization_revoked': revoked,
            'input_scope': body['input'].get('scope'), 'ended_at': row['ended_at'],
            'evidence': [dict(e) for e in connection.execute(
                'SELECT id,subject_kind,observer,method,observed_at,limitations FROM evidence WHERE source_run_id=?', (row['id'],))]}


def history_view(root, target=None):
    """Return recorded runs; observing old results never revalidates or authorizes them."""
    project = current_state(root)
    view = {'project': project, 'runs': [], 'authorization_granted': False}
    if project['state'] != 'connected':
        if target:
            raise EvolveError('TARGET', 'No recorded run is available in this project state')
        return view
    with history_snapshot(root) as (connection, meta):
        if meta.get('checkpoint') != project.get('checkpoint'):
            raise EvolveError('PROJECT_CHANGED', 'History changed before reading recorded runs', exit_code=3)
        rows = connection.execute('SELECT * FROM phase_runs WHERE id=? ORDER BY rowid', (target,)).fetchall() if target else connection.execute('SELECT * FROM phase_runs ORDER BY rowid').fetchall()
        if target and not rows:
            raise EvolveError('TARGET', 'Recorded run is missing; select an observed run identity')
        for row in rows:
            from .package import canonical, digest
            if digest(canonical(json.loads(row['input_json']))) != row['input_digest']:
                raise EvolveError('RUN_RESULT_INVALID', 'Saved source input is invalid')
            view['runs'].append({**restored_run(connection, row), 'method': row['method'],
                'started_at': row['started_at'], 'input_digest': row['input_digest'],
                'applicability': 'historical_not_revalidated',
                'sources': [dict(r) for r in connection.execute('SELECT * FROM source_runs WHERE run_id=?', (row['id'],))],
                'input_checks': [dict(r) for r in connection.execute('SELECT * FROM input_checks WHERE run_id=?', (row['id'],))]})
    return view


def complex_resume(root, selected):
    from .structured import current_tasks, recorded_outputs, whole_definition
    change = selected['changes'][0]
    with history_snapshot(root) as (connection, meta):
        if meta.get('checkpoint') != selected.get('checkpoint'):
            raise EvolveError('PROJECT_CHANGED', 'History changed before complex context read', exit_code=3)
        revision = connection.execute('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],)).fetchone()
        peers = current_tasks(connection, change['id'], revision['id'])
        runs = []
        for row in connection.execute("SELECT * FROM phase_runs WHERE action!='learn' ORDER BY started_at,id"):
            body = json.loads(row['input_json'])['request']
            if body['input'].get('change_id') == change['id'] or (row['action'] == 'propose' and row['result_json']
                    and json.loads(row['result_json']).get('change_id') == change['id']):
                runs.append(restored_run(connection, row, change['id']))
        task_contexts = []
        expected = recorded_outputs(peers)
        for row in peers:
            definition = json.loads(row['definition_json'])
            result = json.loads(row['result_json']) if row['result_json'] else None
            basis = result['fingerprint']['scope'] if result else definition['baseline']
            if row['state'] == 'in_progress' and result:
                expected.update(basis)
            for path, value in basis.items():
                expected.setdefault(path, value)
            try:
                observed = {'status': 'observed', 'current': fingerprint(root, definition)}
            except EvolveError as error:
                observed = {'status': 'unavailable', 'error': {'code': error.code, 'message': str(error)}}
            task_contexts.append({'task_id': row['id'], 'local_key': definition['local_key'],
                'state': row['state'], 'result': result, 'workspace_observation': observed})
        try:
            snapshot = fingerprint(root, whole_definition(revision, peers))
            observation = {'status': 'observed', 'current': snapshot, 'scope_changes': [
                {'path': name, 'previous_digest': value, 'current_digest': snapshot['scope'][name], 'source': 'external_or_unknown'}
                for name, value in expected.items() if snapshot['scope'][name] != value], 'external_data': 'not_observed'}
        except EvolveError as error:
            observation = {'status': 'unavailable', 'error': {'code': error.code, 'message': str(error)}, 'external_data': 'not_observed'}
        latest, seen = [], set()
        from .revisions import eligible_verifications, origin_tasks
        applicable_tasks = {old['id']: task['id'] for task in peers for old in origin_tasks(connection, task)}
        for row in eligible_verifications(connection, change['id'], revision['id']):
            items = json.loads(row['items_json'])
            key = applicable_tasks.get(items.get('task_id'))
            if key not in seen:
                latest.append({'id': row['id'], 'revision_id': row['revision_id'], 'applies_to_task_id': key, 'recorded_status': row['status'], 'items': items,
                    'observed_at': row['observed_at'], 'source_run_id': row['source_run_id'], 'applicability': 'unconfirmed'})
                seen.add(key)
        from .learning import work_learning
        learning = work_learning(connection, change['id'])
    tasks = change['tasks']
    ready = [t for t in tasks if t['readiness']['ready']]
    waiting_review = {item['reference'] for t in tasks for item in t['readiness']['unmet'] if item['kind'] == 'verification_passed'}
    review_task = next((t for t in tasks if t['local_key'] in waiting_review), None)
    suggested = ('inspect_original_owner' if selected['pending_runs'] or selected['initialization'] != 'committed'
                 else 'inspect_archived' if change['state'] == 'archived'
                 else 'accept_revision' if change.get('plan', {}).get('requires_acceptance') and not change['plan']['accepted']
                 else 'inspect_workspace_change' if observation['status'] != 'observed' or observation.get('scope_changes')
                 else 'apply' if ready else 'verify_task' if review_task
                 else 'verify' if all(t['state'] == 'done' for t in tasks) else 'review_task_conditions')
    return {'selection': 'selected', 'target_kind': 'change', 'project': selected, 'task_contexts': task_contexts,
            'runs': runs, 'workspace_observation': observation, 'learning_context': learning, 'verifications': latest,
            'suggested_action': suggested, 'suggested_task_id': ready[0]['id'] if ready else review_task['id'] if review_task else None,
            'authorization_granted': False, 'observed_at': now(),
            'continuation_requires': 'Explicit continue intent, original task grant and fresh revision/task versions; saved context grants nothing'}


def resume_view(root, target=None):
    root = Path(root).resolve()
    navigation = current_state(root)
    candidates = [{'kind': 'change', 'id': c['id'], 'title': c['title'], 'state': c['state']}
                  for c in navigation['changes'] if c['state'] != 'archived']
    candidates += [{'kind': 'analysis', 'id': a['run_id'], 'title': a['question'], 'state': a['run_status']}
                   for a in navigation.get('analyses', []) if a['answer_status'] != 'answered' or a['current_head_status'] != 'completed']
    if target is None:
        if len(candidates) != 1:
            return {'selection': 'required' if candidates else 'none', 'candidates': candidates,
                    'project': navigation, 'suggested_action': 'choose_target' if candidates else 'inspect_or_propose',
                    'authorization_granted': False, 'observed_at': now()}
        target = candidates[0]['id']
    if navigation['state'] != 'connected':
        raise EvolveError('NOT_CONNECTED', 'No connected project contains this target')
    selected = current_state(root, target)
    if selected.get('checkpoint') != navigation.get('checkpoint'):
        raise EvolveError('PROJECT_CHANGED', 'History changed during target selection; read again', exit_code=3)
    if selected.get('analyses'):
        analysis = selected['analyses'][0]
        with history_snapshot(root) as (connection, meta):
            if meta.get('checkpoint') != selected.get('checkpoint'):
                raise EvolveError('PROJECT_CHANGED', 'History changed before analysis context read', exit_code=3)
            ids = dict.fromkeys((analysis['run_id'], analysis['current_head']))
            runs = [restored_run(connection, connection.execute('SELECT * FROM phase_runs WHERE id=?', (key,)).fetchone()) for key in ids]
        return {'selection': 'selected', 'target_kind': 'analysis', 'project': selected, 'runs': runs,
                'suggested_action': 'inspect_original_owner' if selected['pending_runs'] else 'analyze',
                'authorization_granted': False, 'observed_at': now()}
    change = selected['changes'][0]
    if change['complexity'] == 'complex':
        return complex_resume(root, selected)
    if len(change['tasks']) != 1:
        raise EvolveError('UNAVAILABLE', 'This package restores the simple single-task path; complex tasks are not selected implicitly')
    task = change['tasks'][0]
    runs = []
    with history_snapshot(root) as (connection, meta):
        if meta.get('checkpoint') != selected.get('checkpoint'):
            raise EvolveError('PROJECT_CHANGED', 'History changed before context read; read again', exit_code=3)
        for row in connection.execute("SELECT * FROM phase_runs WHERE action!='learn' ORDER BY started_at,id"):
            body = json.loads(row['input_json'])['request']
            if body['input'].get('change_id') != change['id'] and not (
                    row['action'] == 'propose' and row['result_json'] and json.loads(row['result_json']).get('change_id') == change['id']):
                continue
            runs.append(restored_run(connection, row, change['id']))
        saved = connection.execute('SELECT result_json FROM tasks WHERE id=?', (task['id'],)).fetchone()[0]
        task_result = json.loads(saved) if saved else None
        from .learning import work_learning
        learning_context = work_learning(connection, change['id'])
        basis = task_result['fingerprint'] if task_result else {'scope': task['definition']['baseline']}
        try:
            current = fingerprint(root, task['definition'])
            observation = {'status': 'observed', 'current': current,
                           'scope_changes': [{'path': path, 'previous_digest': old, 'current_digest': current['scope'][path],
                                              'source': 'external_or_unknown'} for path, old in basis['scope'].items()
                                             if current['scope'][path] != old],
                           'other_inputs_changed': bool(basis.get('files') is not None and basis['files'] != current['files']),
                           'external_data': 'not_observed'}
        except EvolveError as error:
            observation = {'status': 'unavailable', 'error': {'code': error.code, 'message': str(error)}, 'external_data': 'not_observed'}
    blocked_owner = selected['pending_runs'] or selected['initialization'] != 'committed'
    suggested = ('inspect_original_owner' if blocked_owner else 'inspect_archived' if change['state'] == 'archived'
                 else 'accept_revision' if change.get('plan', {}).get('requires_acceptance') and not change['plan']['accepted']
                 else 'verify' if task['state'] == 'done' else 'apply')
    if not blocked_owner and (observation['status'] != 'observed' or observation.get('scope_changes')):
        suggested = 'inspect_workspace_change'
    return {'selection': 'selected', 'target_kind': 'change', 'project': selected,
            'task_result': task_result, 'runs': runs, 'workspace_observation': observation, 'learning_context': learning_context,
            'suggested_action': suggested, 'authorization_granted': False, 'observed_at': now(),
            'continuation_requires': 'Explicit continue intent, still-applicable original grant and fresh versions; saved context alone authorizes nothing'}
