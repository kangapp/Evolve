"""Read sealed work facts and validate an explicitly requested continuation."""
import json

from .errors import EvolveError
from .package import canonical, digest


def retained_source(connection, row, request):
    """An archived fact keeps its original epoch; a new write still binds the live epoch."""
    meta = dict(connection.execute('SELECT key,value FROM project_meta'))
    return (request.get('project_id') == meta['project_id']
            and request.get('expected_workspace_epoch') == row['workspace_epoch'])


def sealed_result(connection, reference):
    if not isinstance(reference, dict) or not reference.get('run_id') or not reference.get('result_digest'):
        raise EvolveError('CONTINUATION', 'Continuation requires the observed run and result digest')
    row = connection.execute('SELECT * FROM phase_runs WHERE id=?', (reference['run_id'],)).fetchone()
    if not row or row['status'] == 'started' or row['result_digest'] != reference['result_digest']:
        raise EvolveError('CONTINUATION', 'Source is missing, unfinished or not the observed result')
    try:
        result, body = json.loads(row['result_json']), json.loads(row['input_json'])
        if digest(canonical(result)) != row['result_digest'] or digest(canonical(body)) != row['input_digest']:
            raise ValueError('Source digest mismatch')
    except (ValueError, TypeError):
        raise EvolveError('RUN_RESULT_INVALID', 'Saved source input or result is invalid')
    return row, body['request'], result


def current_pause_reference(connection, task):
    saved = json.loads(task['result_json']) if task['result_json'] else {}
    if task['state'] != 'in_progress' or saved.get('checks') != 'not_run' or not saved.get('progress'):
        return None
    from .revisions import origin_tasks
    identities = {item['id'] for item in origin_tasks(connection, task)}
    for event in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='implementation_paused' ORDER BY rowid DESC"):
        if json.loads(event['payload_json'])['task_id'] not in identities:
            continue
        row = connection.execute('SELECT * FROM phase_runs WHERE id=?', (event['run_id'],)).fetchone()
        if row is None or row['status'] == 'started':
            raise EvolveError('CONTINUATION', 'Safely finalize or recover the current paused source before continuing')
        if row['status'] != 'completed':
            return None
        reference = {'run_id': row['id'], 'result_digest': row['result_digest']}
        _, _, result = sealed_result(connection, reference)
        if (result.get('checks') != 'not_run' or result.get('fingerprint') != saved.get('fingerprint')
                or result.get('progress') != saved.get('progress')):
            raise EvolveError('CONTINUATION', 'Current partial result does not match its actual paused source')
        return reference
    raise EvolveError('CONTINUATION', 'Current partial result has no verifiable paused source')


def _bind_continuation(store, request, run_id, *, task):
    reference = request['input'].get('continuation')
    paused = current_pause_reference(store.connection, task)
    automatic = reference is None and paused is not None
    if paused is not None:
        if reference is not None and reference != paused:
            raise EvolveError('CONTINUATION', 'Continue from the current actual file pause, not an earlier result')
        reference = paused
    if reference is None:
        return None
    source, previous, result = sealed_result(store.connection, reference)
    if (source['status'] != 'completed' or source['action'] != 'apply'
            or result.get('outcome') not in ('partial', 'checks_not_passed')
            or previous['project_id'] != request['project_id']
            or not retained_source(store.connection, source, previous)):
        raise EvolveError('CONTINUATION', 'Select a safely ended partial implementation in this project/epoch')
    for key in ('change_id', 'definition_digest'):
        if result.get(key) != request['input'].get(key):
            raise EvolveError('CONTINUATION', 'Continuation is bound to another work definition')
    if result.get('revision_id') != request['input'].get('revision_id'):
        from .work import change_context
        from .revisions import origin_tasks
        _, _, task, _ = change_context(store, request, versions=False, require_task=True)
        if not any(old['id'] == previous['input'].get('task_id') and old['revision_id'] == result['revision_id']
                   for old in origin_tasks(store.connection, task)):
            raise EvolveError('CONTINUATION', 'Revision does not preserve the original task definition')
    elif previous['input'].get('task_id') is not None and previous['input']['task_id'] != request['input'].get('task_id'):
        raise EvolveError('CONTINUATION', 'Continuation is bound to another task')
    old, new = previous['authorization'], request['authorization']
    if (not set(new['effect_kinds']).issubset(old['effect_kinds'])
            or not set(new.get('paths', [])).issubset(old.get('paths', []))):
        raise EvolveError('AUTHORIZATION', 'Reusing an earlier grant cannot expand effects or paths')
    for event in store.connection.execute("SELECT payload_json FROM events WHERE kind='authorization_revoked'"):
        revoked = json.loads(event[0])
        if revoked.get('request_id') == source['request_id'] or revoked.get('change_id') == result['change_id']:
            raise EvolveError('AUTHORIZATION', 'The source authorization was revoked')
    if store.one('SELECT 1 FROM resource_claims c JOIN operations o ON o.id=c.operation_id WHERE o.run_id=?', (source['id'],)):
        raise EvolveError('CONTINUATION', 'The original run still owns unresolved effects')
    store.link_source(run_id, source['id'], source['result_digest'], 'normal_continuation')
    return {'run_id': source['id'], 'result_digest': source['result_digest'],
            **({'resolved_from_task_result': True} if automatic else {})}


def bind_continuation(store, request, run_id, *, task):
    try:
        return _bind_continuation(store, request, run_id, task=task)
    except EvolveError as error:
        error.input_check_reference = request['input'].get('continuation')
        raise
