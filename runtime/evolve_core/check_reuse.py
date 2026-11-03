"""Reuse only explicitly cacheable, sealed local checks at the exact same cutoff."""
import json

from .checks import pending_checks, run_check
from .continuation import retained_source, sealed_result
from .errors import EvolveError
from .package import canonical, digest
from .workspace import writer_lock


def fresh_checks(data, definition):
    selected = data.get('fresh_checks', [])
    if (not isinstance(selected, list) or any(not isinstance(key, str) for key in selected)
            or len(selected) != len(set(selected)) or not set(selected).issubset(definition['required_checks'])):
        raise EvolveError('INPUT', 'fresh_checks must list distinct declared checks to execute again')
    return selected


def basis(store, request, definition, snapshot, check):
    return {'project_id': store.meta['project_id'], 'workspace_epoch': store.meta['workspace_epoch'],
            'change_id': request['input']['change_id'], 'revision_id': request['input']['revision_id'],
            'definition_digest': request['input']['definition_digest'],
            'task_id': definition.get('_task_id'), 'fingerprint_digest': snapshot['digest'],
            'plan_digest': store.one('SELECT plan_digest FROM plan_revisions WHERE id=?', (request['input']['revision_id'],))[0],
            'check_digest': digest(canonical(check)),
            'environment_digest': next(item['digest'] for item in snapshot['environment'] if item['check_id'] == check['id'])}


def saved_check(store, row):
    blob = store.one('SELECT content FROM blobs WHERE digest=?', (row['content_digest'],))
    if blob is None or digest(blob['content']) != row['content_digest']:
        raise EvolveError('CHECK_SOURCE_INVALID', 'Saved check bytes do not match their immutable digest')
    return json.loads(blob['content'])


def sealed_check(store, row, expected):
    source = store.one('SELECT * FROM phase_runs WHERE id=?', (row['source_run_id'],))
    if source is None or source['status'] != 'completed' or source['workspace_epoch'] != expected['workspace_epoch']:
        return None
    ref = {'run_id': source['id'], 'result_digest': source['result_digest']}
    _, request, result = sealed_result(store.connection, ref)
    if not retained_source(store.connection, source, request) or pending_checks(store.connection, source['id']):
        return None
    check = saved_check(store, row)
    receipts = result.get('task_checks', result.get('checks', []))
    if (check.get('reuse_basis') != expected or check.get('status') != 'passed' or check.get('returncode') != 0
            or check.get('unfinished_processes') is not False or check.get('workspace_change')
            or result.get('fingerprint', {}).get('digest', result.get('fingerprint_digest')) != expected['fingerprint_digest']
            or result.get('outcome') not in ('implemented', 'verified')
            or result.get('status', 'passed') != 'passed'
            or not any(item.get('evidence_id') == row['id'] and item.get('status') == 'passed' for item in receipts)):
        return None
    return check, ref


def candidate(store, run_id, expected, check):
    # Any other unfinished run makes the current execution cutoff uncertain.
    if store.one("SELECT 1 FROM phase_runs WHERE status='started' AND id!=?", (run_id,)):
        return None
    for row in store.connection.execute("SELECT DISTINCT run_id FROM events WHERE kind='check_dispatch_prepared'"):
        if row['run_id'] != run_id and pending_checks(store.connection, row['run_id']):
            return None
    rows = store.connection.execute("SELECT e.* FROM evidence e JOIN phase_runs r ON r.id=e.source_run_id "
        "WHERE e.method IN ('argv-check','argv-check-reuse') AND r.action IN ('apply','verify') "
        "AND r.id!=? ORDER BY e.rowid DESC", (run_id,))
    for row in rows:
        item = saved_check(store, row)
        if item.get('check_id') != check['id']:
            continue
        source = store.one('SELECT input_json FROM phase_runs WHERE id=?', (row['source_run_id'],))
        target = json.loads(source['input_json'])['request']['input']
        if any(target.get(key) != expected[key] for key in ('change_id', 'revision_id', 'definition_digest')):
            continue
        # Stop at the latest matching receipt: a newer failure or input change
        # cannot be hidden by finding an older green result.
        valid = sealed_check(store, row, expected)
        if valid is None:
            return None
        item, ref = valid
        if row['method'] == 'argv-check-reuse':
            origin = item.get('reuse_source', {})
            row = store.one("SELECT * FROM evidence WHERE id=? AND source_run_id=? AND method='argv-check'",
                            (origin.get('evidence_id'), origin.get('run_id')))
            if row is None:
                return None
            valid = sealed_check(store, row, expected)
            if valid is None or valid[1]['result_digest'] != origin.get('result_digest'):
                return None
            item, ref = valid
        if not item.get('executed') or item.get('reused') or not item.get('execution_id'):
            return None
        finished = store.one("SELECT 1 FROM events WHERE run_id=? AND kind='check_process_finished' "
            "AND json_extract(payload_json,'$.execution_id')=? AND json_extract(payload_json,'$.status')='passed'",
            (ref['run_id'], item['execution_id']))
        if finished is None:
            return None
        return {'check_id': check['id'], 'status': 'passed', 'returncode': 0,
                'executed': False, 'reused': True, 'unfinished_processes': False,
                'reuse_basis': expected, 'reuse_source': {**ref, 'evidence_id': row['id'],
                    'blob_digest': row['content_digest'], 'execution_id': item['execution_id']},
                'environment': item['environment'], 'output': 'Referenced the original sealed check; no command was executed.'}
    return None


def execute(store, request, run_id, operation_id, versions, definition, snapshot, check, *, allow_reuse=True):
    from .work import check_event_sink, gate, require_workspace
    expected = basis(store, request, definition, snapshot, check)
    with writer_lock(store.root):
        gate(store, request, run_id, operation_id, versions)
        require_workspace(store.root, definition, snapshot, 'Workspace changed before selecting a check result', check_id=check['id'])
        reused = None
        if (allow_reuse and check.get('reuse', False) and not check.get('preflight')
                and check['id'] not in fresh_checks(request['input'], definition)):
            reused = candidate(store, run_id, expected, check)
        if reused is not None:
            with store.transaction():
                ref = reused['reuse_source']
                store.link_source(run_id, ref['run_id'], ref['result_digest'], 'check_reuse')
                store.event(run_id, 'check_reused', {'check_id': check['id'], 'source': ref, 'basis': expected})
            return reused
    result = run_check(store.root, check, event_sink=check_event_sink(store, request, run_id, operation_id, versions))
    return {**result, 'executed': True, 'reused': False, 'reuse_basis': expected}


def receipt(item, evidence_id):
    return {**{key: item[key] for key in ('check_id', 'status', 'returncode')}, 'evidence_id': evidence_id,
            **{key: item[key] for key in ('executed', 'reused', 'reuse_source') if key in item}}
