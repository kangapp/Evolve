"""Behavior-preservation evidence uses existing runs, checks and immutable events."""
import json
import re

from .continuation import sealed_result
from .errors import EvolveError
from .package import canonical, digest
from .workspace import current_digest, inside


LIMITATION = 'Proof is limited to the declared checks and unchanged inputs; untested behavior is not proven.'


def definition_fields(root, data):
    """The same preservation contract applies to short and structured plans."""
    declared = data.get('pre_refactor', False)
    if type(declared) is not bool:
        raise EvolveError('INPUT', 'pre_refactor must be boolean')
    context = data.get('context_paths', data.get('preservation_inputs', []))
    if (not isinstance(context, list) or any(not isinstance(name, str) or not name for name in context)
            or len(context) != len(set(context))):
        raise EvolveError('PRESERVATION', 'Context must list distinct explicit project paths')
    frozen_context = {name: current_digest(inside(root, name)) for name in context}
    if not declared:
        if data.get('preservation_checks') or data.get('preservation_inputs'):
            raise EvolveError('PRESERVATION', 'Preservation inputs and checks require pre_refactor=true')
        return {'context': frozen_context} if 'context_paths' in data else {}
    if data.get('responsible_action', 'apply') != 'apply':
        raise EvolveError('PRESERVATION', 'Behavior preparation belongs to business implementation')
    for field in ('preservation_checks', 'preservation_inputs'):
        value = data.get(field)
        if (not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value)
                or len(value) != len(set(value))):
            raise EvolveError('PRESERVATION', field + ' requires distinct nonempty strings')
    if not set(data['preservation_checks']).issubset(data['required_checks']):
        raise EvolveError('PRESERVATION', 'Behavior checks must be declared required checks')
    if not set(data['preservation_inputs']).issubset(context):
        raise EvolveError('PRESERVATION', 'Behavior inputs must belong to the frozen context')
    inputs = {inside(root, name).resolve() for name in data['preservation_inputs']}
    if inputs & {inside(root, name).resolve() for name in data['scope']}:
        raise EvolveError('PRESERVATION', 'Behavior inputs must remain unchanged during implementation')
    return {'pre_refactor': True, 'preservation_checks': data['preservation_checks'],
            'preservation_inputs': data['preservation_inputs'],
            'context': frozen_context}


def matches_task(connection, data, task):
    if data.get('revision_id') != task['revision_id']:
        return False
    if data.get('task_id') is not None:
        return data['task_id'] == task['id']
    # Short requests bind the single task by revision/definition instead of a task ID.
    return (not json.loads(task['definition_json']).get('structured')
            and connection.execute('SELECT COUNT(*) FROM tasks WHERE revision_id=?', (task['revision_id'],)).fetchone()[0] == 1)


def checks_for(root, definition):
    from .work import check_basis
    return [check for check in check_basis(root, definition) if check['id'] in definition['preservation_checks']]


def protected_inputs(root, definition):
    outputs = {inside(root, name).resolve() for name in definition['scope']}
    if outputs & {inside(root, name).resolve() for name in definition['preservation_inputs']}:
        raise EvolveError('PRESERVATION', 'A behavior-preservation input currently aliases an implementation output')
    names = set(definition.get('context', {})) | set(definition.get('dependency_inputs', [])) | set(definition['preservation_inputs'])
    return {name: current_digest(inside(root, name)) for name in sorted(names) if inside(root, name).resolve() not in outputs}


def has_coverage(result):
    return not re.search(r'\bRan\s+0\s+tests?\b', result['output'], re.IGNORECASE)


def source_run(connection, task, run_id, active_run=None):
    row = connection.execute('SELECT * FROM phase_runs WHERE id=?', (run_id,)).fetchone()
    if not row:
        raise EvolveError('PRESERVATION_SOURCE', 'Behavior evidence source is missing')
    body = json.loads(row['input_json'])
    if digest(canonical(body)) != row['input_digest']:
        raise EvolveError('PRESERVATION_SOURCE', 'Behavior evidence input is not the recorded source')
    request = body['request']
    from .continuation import retained_source
    from .revisions import origin_tasks
    origins = origin_tasks(connection, task)
    same_task = any(matches_task(connection, request['input'], old) for old in origins)
    if (row['action'] != 'apply' or row['method'] != 'implement'
            or not retained_source(connection, row, request)
            or not same_task
            or request['input'].get('change_id') != task['change_id']
            or request['input'].get('definition_digest') != task['definition_digest']
            or 'checks' not in request['authorization']['effect_kinds']):
        raise EvolveError('PRESERVATION_SOURCE', 'Behavior evidence belongs to another task, definition, epoch or grant')
    if row['status'] == 'started':
        if row['id'] != active_run:
            raise EvolveError('PRESERVATION_SOURCE', 'Original behavior evidence still needs safe finalization or recovery')
    else:
        _, _, result = sealed_result(connection, {'run_id': row['id'], 'result_digest': row['result_digest']})
        if row['status'] == 'interrupted':
            recovery = connection.execute("SELECT * FROM phase_runs WHERE id=? AND action='maintain' AND method='recover' AND status='completed'",
                (result.get('finalized_by'),)).fetchone()
            facts = json.loads(recovery['result_json']) if recovery else {}
            if (not recovery or facts.get('original_run_id') != row['id'] or facts.get('business_commands_run') is not False
                    or facts.get('outcome') not in ('recovered_local', 'recovered_registration')):
                raise EvolveError('PRESERVATION_SOURCE', 'Interrupted behavior evidence has no matching completed recovery')
            sealed_result(connection, {'run_id': recovery['id'], 'result_digest': recovery['result_digest']})
    return row


def check_evidence(connection, task, evidence_ids, checks, *, active_run=None, source_id=None, after_files=False, before_files=False):
    if not isinstance(evidence_ids, list) or len(evidence_ids) != len(checks) or len(set(evidence_ids)) != len(evidence_ids):
        raise EvolveError('PRESERVATION_EVIDENCE', 'Behavior proof needs exactly one actual result for each declared check')
    expected = {check['id']: check for check in checks}
    observed, sources = set(), set()
    for evidence_id in evidence_ids:
        row = connection.execute("SELECT * FROM evidence WHERE id=? AND method='argv-check'", (evidence_id,)).fetchone()
        blob = connection.execute('SELECT content FROM blobs WHERE digest=?', (row['content_digest'],)).fetchone() if row else None
        if not row or not blob or digest(blob['content']) != row['content_digest']:
            raise EvolveError('PRESERVATION_EVIDENCE', 'Original check evidence is missing or changed')
        source_run(connection, task, row['source_run_id'], active_run)
        sources.add(row['source_run_id'])
        result = json.loads(blob['content'])
        check = expected.get(result.get('check_id'))
        if (not check or result['check_id'] in observed or result.get('status') != 'passed'
                or result.get('returncode') != 0 or result.get('unfinished_processes') is not False
                or result.get('argv') != check['argv'] or result.get('cwd') != check.get('cwd', '.') or not has_coverage(result)):
            raise EvolveError('PRESERVATION_EVIDENCE', 'Behavior proof cannot use failed, empty, changed or repeated checks')
        prepared, finished, applied = None, None, None
        for event in connection.execute('SELECT rowid,kind,payload_json FROM events WHERE run_id=? ORDER BY rowid', (row['source_run_id'],)):
            value = json.loads(event['payload_json'])
            if event['kind'] == 'files_applied':
                applied = event['rowid']
            if value.get('execution_id') == result.get('execution_id'):
                if event['kind'] == 'check_dispatch_prepared' and value.get('command_digest') == digest(canonical(check)):
                    prepared = event['rowid']
                elif event['kind'] == 'check_process_finished' and value.get('status') == 'passed' and value.get('returncode') == 0:
                    finished = event['rowid']
        if (prepared is None or finished is None or finished <= prepared
                or (after_files and (applied is None or prepared <= applied))
                or (before_files and applied is not None and finished >= applied)):
            raise EvolveError('PRESERVATION_ORDER', 'Behavior checks do not prove the required before/after execution order')
        observed.add(check['id'])
    if len(sources) != 1 or (source_id is not None and sources != {source_id}):
        raise EvolveError('PRESERVATION_SOURCE', 'Behavior check results must share their actual bound execution')


def before_fact(connection, root, task, definition, reference, dependencies, *, active_run=None):
    if not isinstance(reference, dict):
        raise EvolveError('PRESERVATION_REQUIRED', 'Original behavior proof is required')
    event = connection.execute("SELECT * FROM events WHERE id=? AND run_id=? AND kind='preservation_before_checked'",
        (reference.get('event_id'), reference.get('run_id'))).fetchone()
    if not event:
        raise EvolveError('PRESERVATION_REQUIRED', 'Original behavior proof event is missing')
    source_run(connection, task, event['run_id'], active_run)
    fact = json.loads(event['payload_json'])
    checks = checks_for(root, definition)
    from .revisions import origin_tasks
    if (fact.get('task_id') not in {old['id'] for old in origin_tasks(connection, task)} or fact.get('definition_digest') != task['definition_digest']
            or fact.get('status') != 'passed' or fact.get('checks_basis') != checks):
        raise EvolveError('PRESERVATION_EVIDENCE', 'Original behavior proof does not match the declared task checks')
    originals = {**fact['before_snapshot']['scope'], **fact['protected_inputs']}
    originals = {name: value for name, value in originals.items() if value is not None}
    references = fact.get('input_refs', {})
    if set(references) != set(originals):
        raise EvolveError('PRESERVATION_EVIDENCE', 'Original source and behavior inputs are not fully retained')
    for name, expected in originals.items():
        reference = references[name]
        version = connection.execute('SELECT v.blob_digest,v.source_run_id,a.path,a.kind,b.content FROM artifact_versions v '
            'JOIN artifacts a ON a.id=v.artifact_id JOIN blobs b ON b.digest=v.blob_digest WHERE v.id=?', (reference.get('entity_id'),)).fetchone()
        if (not version or reference.get('entity_type') != 'artifact_version' or reference.get('digest') != expected
                or version['blob_digest'] != expected or version['source_run_id'] != event['run_id']
                or version['path'] is not None or version['kind'] != 'behavior_input_snapshot' or digest(version['content']) != expected):
            raise EvolveError('PRESERVATION_EVIDENCE', 'Retained original bytes do not match the actual behavior basis: ' + name)
    check_evidence(connection, task, fact.get('evidence_ids'), checks, active_run=active_run, source_id=event['run_id'], before_files=True)
    if fact.get('protected_inputs') != protected_inputs(root, definition) or fact.get('dependency_basis') != dependencies:
        raise EvolveError('PRESERVATION_CHANGED', 'Behavior inputs or upstream basis changed; preserve the old proof and revise the affected work')
    return fact


def wrote_files(connection, task):
    from .revisions import origin_tasks
    origins = origin_tasks(connection, task)
    for row in connection.execute("SELECT r.input_json FROM operations o JOIN phase_runs r ON r.id=o.run_id WHERE r.action='apply' AND o.journal_path IS NOT NULL"):
        data = json.loads(row['input_json'])['request']['input']
        if any(matches_task(connection, data, old) for old in origins) and data.get('files'):
            return True
    return False


def select_before(connection, root, task, definition, dependencies, *, active_run=None):
    wrote = wrote_files(connection, task)
    from .revisions import origin_tasks
    origins = {old['id'] for old in origin_tasks(connection, task)}
    for event in connection.execute("SELECT id,run_id,payload_json FROM events WHERE kind='preservation_before_checked' ORDER BY rowid DESC"):
        fact = json.loads(event['payload_json'])
        if fact.get('task_id') not in origins or fact.get('definition_digest') != task['definition_digest'] or fact.get('status') != 'passed':
            continue
        reference = {'run_id': event['run_id'], 'event_id': event['id']}
        try:
            before_fact(connection, root, task, definition, reference, dependencies, active_run=active_run)
            return reference
        except EvolveError as error:
            if error.code != 'PRESERVATION_CHANGED' or wrote:
                raise
    if wrote:
        raise EvolveError('PRESERVATION_REQUIRED', 'Files were already dispatched; checks on modified code cannot invent an original baseline')
    return None


def completion_proven(connection, root, task, definition, saved, dependencies):
    proof = saved.get('preservation') or {}
    if proof.get('status') != 'passed':
        return False
    before_fact(connection, root, task, definition, proof.get('before'), dependencies)
    after = proof.get('after_evidence_ids')
    if not isinstance(after, list) or not set(after).issubset(saved.get('check_evidence', [])):
        return False
    check_evidence(connection, task, after, checks_for(root, definition), after_files=True)
    return True


def run_before(store, request, run_id, operation_id, expected, task, definition, dependencies, snapshot):
    from .checks import run_check
    from .work import check_event_sink, gate, record_check, require_workspace
    from .workspace import writer_lock
    checks = checks_for(store.root, definition)
    results, evidence_ids = [], []
    for check in checks:
        with writer_lock(store.root):
            gate(store, request, run_id, operation_id, expected)
            require_workspace(store.root, definition, snapshot, 'Workspace changed before original behavior check', check_id=check['id'])
        result = run_check(store.root, check, event_sink=check_event_sink(store, request, run_id, operation_id, expected))
        with writer_lock(store.root):
            gate(store, request, run_id, operation_id, expected)
            with store.transaction():
                evidence_ids.append(record_check(store, run_id, result))
                store.event(run_id, 'preservation_check_observed', {'stage': 'before', 'evidence_id': evidence_ids[-1], 'status': result['status']})
            if result['unfinished_processes']:
                raise EvolveError('CHECK_RUNNING', 'Original behavior check still has an executing process group', exit_code=4, committed=True)
            require_workspace(store.root, definition, snapshot, 'Original behavior check changed its input workspace; no refactor was dispatched', check_id=check['id'])
        results.append(result)
    status = ('blocked' if any(item['status'] == 'blocked' or not has_coverage(item) for item in results)
              else 'failed' if any(item['status'] != 'passed' for item in results) else 'passed')
    with writer_lock(store.root):
        gate(store, request, run_id, operation_id, expected)
        require_workspace(store.root, definition, snapshot, 'Workspace changed before original behavior facts were recorded')
        fact = {'task_id': task['id'], 'definition_digest': task['definition_digest'], 'status': status,
                'checks_basis': checks, 'evidence_ids': evidence_ids, 'before_snapshot': snapshot,
                'protected_inputs': protected_inputs(store.root, definition), 'dependency_basis': dependencies,
                'limitations': [LIMITATION]}
        with store.transaction():
            references = {}
            for name, expected_digest in {**snapshot['scope'], **fact['protected_inputs']}.items():
                if expected_digest is None:
                    continue
                content = inside(store.root, name).read_bytes()
                if digest(content) != expected_digest:
                    raise EvolveError('WORKSPACE_CHANGED', 'Original behavior input changed before its bytes could be retained', exit_code=3)
                references[name] = store.artifact(None, 'behavior_input_snapshot', content, run_id, 'evolve-apply:preservation-before:' + name)
            fact['input_refs'] = references
            event_id = store.event(run_id, 'preservation_before_checked', fact)
    return {'run_id': run_id, 'event_id': event_id}, status, results


def after_summary(connection, root, task, definition, reference, dependencies, results, evidence_ids, run_id):
    before_fact(connection, root, task, definition, reference, dependencies, active_run=run_id)
    pairs = {result['check_id']: (result, evidence_id) for result, evidence_id in zip(results, evidence_ids)}
    selected = [pairs[key] for key in definition['preservation_checks']]
    status = ('blocked' if any(item['status'] == 'blocked' or not has_coverage(item) for item, _ in selected)
              else 'failed' if any(item['status'] != 'passed' for item, _ in selected) else 'passed')
    ids = [evidence_id for _, evidence_id in selected]
    if status == 'passed':
        check_evidence(connection, task, ids, checks_for(root, definition), active_run=run_id, source_id=run_id, after_files=True)
    return {'status': status, 'before': reference, 'after_evidence_ids': ids, 'limitations': [LIMITATION]}
