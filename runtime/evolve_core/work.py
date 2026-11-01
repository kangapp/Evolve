"""Shared gates and observations for apply, verify, and archive."""
import json
import os
from pathlib import Path
import tomllib

from .errors import EvolveError
from .package import canonical, check_package, digest
from .plans import business_path
from .workspace import current_digest, inside


def change_context(store, request, *, versions=True, allow_archived=False, require_task=False):
    data = request['input']
    target = data.get('change_id')
    if not isinstance(target, str) or not target:
        raise EvolveError('TARGET', 'A prepared request must identify its change')
    change = store.one('SELECT * FROM changes WHERE id=?', (target,))
    if not change:
        raise EvolveError('TARGET', 'Change does not exist in this project')
    if change['state'] == 'cancelled' or (change['state'] == 'archived' and not allow_archived):
        raise EvolveError('TERMINAL_CHANGE', 'Archived or cancelled implementation scope cannot be reopened', exit_code=3)
    revision = store.one('SELECT * FROM plan_revisions WHERE id=? AND change_id=?',
                         (change['current_revision'], target))
    if revision['ordinal'] > 1:
        from .revisions import require_ready
        require_ready(store.connection, revision)
    tasks = store.connection.execute('SELECT * FROM tasks WHERE change_id=? AND revision_id=? ORDER BY rowid',
                                     (target, revision['id'])).fetchall()
    if not tasks:
        raise EvolveError('TARGET', 'The current revision has no tasks')
    if change['complexity'] == 'complex':
        from .structured import whole_definition
        if require_task and data.get('task_id') is None:
            raise EvolveError('TASK_TARGET', 'Implementation must bind an actual current task')
        selected = [t for t in tasks if t['id'] == data.get('task_id')]
        if data.get('task_id') is not None and len(selected) != 1:
            raise EvolveError('TASK_TARGET', 'Task is not in the current revision')
        task = selected[0] if selected else tasks[0]
        definition = json.loads(task['definition_json']) if selected else whole_definition(revision, tasks)
        definition['_task_id'] = task['id'] if selected else None
        bound_digest = task['definition_digest'] if selected else revision['definition_digest']
        expected = {'change': change['row_version'], 'tasks': {t['id']: t['row_version'] for t in tasks}}
    else:
        if len(tasks) != 1:
            raise EvolveError('TARGET', 'Simple work requires exactly one task')
        task = tasks[0]
        definition = json.loads(task['definition_json'])
        bound_digest = task['definition_digest']
        expected = {'change': change['row_version'], 'task': task['row_version']}
    if data.get('revision_id') != revision['id'] or data.get('definition_digest') != bound_digest:
        raise EvolveError('REVISION', 'The prepared request is not bound to the current presented definition', exit_code=3)
    if versions:
        if request.get('expected_versions') != expected:
            raise EvolveError('VERSION', 'Change or task version changed; prepare again', exit_code=3)
    return dict(change), dict(revision), dict(task), definition


def check_basis(root, definition):
    config = tomllib.loads(inside(root, 'evolve/config.toml').read_text())
    configured = {c['id']: c for c in config.get('verification', {}).get('checks', [])}
    checks = []
    for original in definition['checks_basis']:
        if configured.get(original['id']) != original:
            raise EvolveError('CHECK_CONFIG', 'A required check changed after planning', exit_code=3)
        checks.append(original)
    if sorted(c['id'] for c in checks) != sorted(definition['required_checks']):
        raise EvolveError('CHECK_CONFIG', 'Required checks are missing from the plan')
    return checks


def implementation_baseline(store, change, definition, saved):
    """Use the latest actual same-Change write, including partial and prior-REV files."""
    baseline = dict(saved['fingerprint']['scope'] if saved else definition['baseline'])
    if not definition.get('structured'):
        return baseline
    for name in baseline:
        versions = store.connection.execute('SELECT v.blob_digest,v.source_run_id,v.source FROM artifact_versions v '
            'JOIN artifacts a ON a.id=v.artifact_id WHERE a.path=? ORDER BY v.rowid DESC', (name,))
        for version in versions:
            if version['source'] not in ('evolve-apply', 'evolve-maintain:recovered-apply'):
                continue
            run = store.one('SELECT * FROM phase_runs WHERE id=?', (version['source_run_id'],))
            if run and run['action'] == 'maintain':
                result = json.loads(run['result_json']) if run['result_json'] else {}
                run = store.one('SELECT * FROM phase_runs WHERE id=?', (result.get('original_run_id'),))
            data = json.loads(run['input_json'])['request']['input'] if run else {}
            if data.get('change_id') == change['id']:
                target = inside(store.root, name).resolve().relative_to(store.root).as_posix()
                for event in store.connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind='file_targets_bound'", (run['id'],)):
                    if json.loads(event[0])['targets'].get(name) == target:
                        baseline[name] = version['blob_digest']
                        break
            break
    return baseline


def fingerprint(root, definition):
    # Hash relevant source and untracked inputs without retaining their plaintext.
    # Generated state and environments do not invalidate business verification.
    excluded = {'.git', 'evolve', '.evolve-local', '.codex', '.claude', '.agents',
                '__pycache__', '.pytest_cache', '.venv', 'venv', 'node_modules', 'dist', 'build'}
    files = {}
    for directory, subdirs, names in os.walk(root, followlinks=False):
        subdirs[:] = sorted(d for d in subdirs if d not in excluded)
        for name in list(subdirs):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                files[relative] = {'symlink': digest(os.readlink(path).encode())}
                subdirs.remove(name)
            elif path.resolve() != path:
                # Directory junctions and other resolved aliases are inputs,
                # not permission to traverse a second source tree.
                files[relative] = {'directory_alias': digest(str(path.resolve()).encode())}
                subdirs.remove(name)
        for name in sorted(names):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if name.endswith(('.pyc', '.pyo')):
                continue
            if path.is_symlink():
                files[relative] = {'symlink': digest(os.readlink(path).encode())}
            elif path.is_file():
                files[relative] = current_digest(path)
    scope = {name: current_digest(inside(root, name)) for name in definition['scope']}
    basis = {'files': files, 'scope': scope, 'checks': check_basis(root, definition)}
    if definition.get('structured'):
        basis['context'] = {name: current_digest(inside(root, name)) for name in definition.get('context', {})}
        if not definition.get('whole_change'):
            inputs = {name: current_digest(inside(root, name)) for name in definition.get('dependency_inputs', [])}
            basis['task_basis_digest'] = digest(canonical({'scope': scope, 'context': basis['context'],
                                                         'dependency_inputs': inputs, 'checks': basis['checks']}))
    return {**basis, 'digest': digest(canonical(basis))}


def workspace_work(connection, snapshot, change_id):
    """Describe saved work visible in this whole-directory verification cutoff."""
    result = []
    for task in connection.execute('SELECT t.*,c.state AS change_state FROM tasks t JOIN changes c ON c.id=t.change_id '
                                   'WHERE t.revision_id=c.current_revision AND t.change_id!=?', (change_id,)):
        saved = json.loads(task['result_json']) if task['result_json'] else None
        if (not saved or not saved.get('fingerprint')) and task['state'] != 'in_progress':
            continue
        definition = json.loads(task['definition_json'])
        scope = saved['fingerprint']['scope'] if saved and saved.get('fingerprint') else {name: None for name in definition['scope']}
        observed = {name: snapshot['files'].get(name) for name in scope if name in snapshot['files']}
        if not observed:
            continue
        result.append({'change_id': task['change_id'], 'task_id': task['id'], 'task_key': definition['local_key'],
            'change_state': task['change_state'], 'recorded_task_state': task['state'],
            'definition_digest': task['definition_digest'], 'saved_result_digest': digest(canonical(saved)) if saved else None,
            'observed_files': observed,
            'scope_matches_saved_result': set(observed) == set(scope) and observed == scope if saved else None,
            'physical_effect_attribution': 'saved_result_comparison' if saved else 'unconfirmed_in_progress_scope',
            'independent_isolation': 'not_asserted'})
    return result


def gate_identity(store, request, run_id):
    """Recheck identity, epoch, latest revocations, package, and operation ownership."""
    store.assert_current_database()
    meta = dict(store.connection.execute('SELECT key,value FROM project_meta'))
    if meta['project_id'] != request['project_id'] or meta['workspace_epoch'] != request['expected_workspace_epoch']:
        raise EvolveError('WORKSPACE_EPOCH', 'Project or epoch changed before a side effect', exit_code=3)
    config = tomllib.loads(inside(store.root, 'evolve/config.toml').read_text())
    if config.get('project', {}).get('id') != meta['project_id']:
        raise EvolveError('PROJECT_IDENTITY', 'Configuration identity changed before a side effect')
    if config.get('history') != {'backend': 'sqlite', 'database': 'evolve/history.db'}:
        raise EvolveError('CONFIG_PATH', 'History location/backend changed')
    run = store.one('SELECT * FROM phase_runs WHERE id=?', (run_id,))
    if not run or run['status'] != 'started' or run['package_digest'] != check_package()['content_digest']:
        raise EvolveError('EXECUTION_CHANGED', 'Run or package changed before a side effect', exit_code=3)
    for event in store.connection.execute("SELECT payload_json FROM events WHERE kind='authorization_revoked'"):
        revoked = json.loads(event[0])
        if revoked.get('request_id') in {request['request_id'], request.get('authorization_parent_request_id', request['request_id'])} or (
                request['input'].get('change_id') is not None and revoked.get('change_id') == request['input']['change_id']):
            raise EvolveError('AUTHORIZATION', 'The effective authorization was revoked', exit_code=3)
    return run


def gate(store, request, run_id, operation_id, expected_versions=None):
    run = gate_identity(store, request, run_id)
    claim = store.one('SELECT operation_id FROM resource_claims WHERE resource=?',
                      ('change:' + request['input']['change_id'],))
    if not claim or claim[0] != operation_id:
        raise EvolveError('CLAIM', 'Operation no longer owns the change', exit_code=3)
    change, revision, task, definition = change_context(store, request, versions=False, allow_archived=run['action'] == 'verify')
    if expected_versions is not None and expected_versions != versions(store, change['id'], task['id']):
        raise EvolveError('VERSION', 'Change or task changed while execution was in progress', exit_code=3)
    from .cross_dependencies import guard
    guard(store.connection, store.root, run_id, change['id'], request['input'])
    require_bound_targets(store, operation_id, definition['scope'])


def claim_resources(store, run_id, operation_id, generation, change, paths, effect):
    resources = (['change:' + change['id']] if change is not None else []) + ['file:' + str(inside(store.root, p).resolve()) for p in paths]
    targets = {p: inside(store.root, p).resolve().relative_to(store.root).as_posix() for p in paths}
    for resource in resources:
        existing = store.one('SELECT operation_id FROM resource_claims WHERE resource=?', (resource,))
        if existing:
            raise EvolveError('CLAIM', 'Relevant resource is occupied by operation ' + existing[0], exit_code=3)
    for row in store.connection.execute("SELECT DISTINCT operation_id FROM resource_claims WHERE resource LIKE 'file:%'"):
        bound = recorded_targets(store, row[0])
        if bound is not None and set(bound.values()) & set(targets.values()):
            raise EvolveError('CLAIM', 'Canonical file target is occupied by operation ' + row[0], exit_code=3)
        if bound is None:
            legacy = store.connection.execute("SELECT resource FROM resource_claims WHERE operation_id=? AND resource LIKE 'file:%'", (row[0],))
            if any(not Path(r[0][5:]).is_relative_to(store.root) for r in legacy):
                raise EvolveError('CLAIM', 'A legacy claim from another project location requires recovery before new writes', exit_code=3)
    with store.transaction() as connection:
        connection.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?)',
                           (operation_id, run_id, effect, 'prepared', digest(canonical(resources)), None, None))
        for resource in sorted(resources):
            connection.execute('INSERT INTO resource_claims VALUES (?,?,?,?,1)',
                               (resource, operation_id, 'active', canonical(generation).decode()))
        store.event(run_id, 'file_targets_bound', {'operation_id': operation_id,
                    'targets': targets})
        if change is not None:
            from .cross_dependencies import snapshot, proofs
            request_data = json.loads(store.one('SELECT input_json FROM phase_runs WHERE id=?', (run_id,))[0])['request']['input']
            dependencies = snapshot(connection, change['id'], request_data)
            if dependencies:
                from .store import now
                store.event(run_id, 'cross_dependencies_bound', {'task_bases': dependencies,
                    'proofs': proofs(connection, change['id'], request_data), 'observed_at': now()})


def recorded_targets(store, operation_id):
    operation = store.one('SELECT run_id FROM operations WHERE id=?', (operation_id,))
    for row in store.connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind='file_targets_bound'", (operation['run_id'],)):
        payload = json.loads(row[0])
        if payload['operation_id'] == operation_id:
            return payload['targets']
    return None


def require_bound_targets(store, operation_id, paths):
    expected = recorded_targets(store, operation_id)
    actual = {p: inside(store.root, p).resolve().relative_to(store.root).as_posix() for p in paths}
    if expected is None:
        # Earlier alpha builds froze absolute resource addresses in the operation
        # digest. Reuse that proof without inventing a missing binding event.
        operation = store.one('SELECT * FROM operations WHERE id=?', (operation_id,))
        original = store.one('SELECT action,input_json FROM phase_runs WHERE id=?', (operation['run_id'],))
        source = json.loads(original['input_json'])['request']['input']
        resources = (['change:' + source['change_id']] if original['action'] in ('apply', 'verify', 'archive') else [])
        resources += ['file:' + str(inside(store.root, p).resolve()) for p in paths]
        matches = digest(canonical(resources)) == operation['input_digest']
    else:
        matches = actual == expected
    if not matches:
        raise EvolveError('FILE_TARGET_CHANGED', 'Canonical file targets differ from the recorded operation; preserve the journal and inspect the aliases', exit_code=4, committed=True)


def versions(store, change_id, task_id):
    change = store.one('SELECT row_version,complexity,current_revision FROM changes WHERE id=?', (change_id,))
    if change['complexity'] == 'complex':
        tasks = store.connection.execute('SELECT id,row_version FROM tasks WHERE change_id=? AND revision_id=?',
                                         (change_id, change['current_revision']))
        return {'change': change['row_version'], 'tasks': {t['id']: t['row_version'] for t in tasks}}
    return {'change': store.one('SELECT row_version FROM changes WHERE id=?', (change_id,))[0],
            'task': store.one('SELECT row_version FROM tasks WHERE id=?', (task_id,))[0]}


def verification_source(connection, verification):
    source = connection.execute('SELECT * FROM phase_runs WHERE id=?', (verification['source_run_id'],)).fetchone()
    if source and source['status'] == 'completed':
        return source
    if source and source['status'] == 'interrupted':
        facts = json.loads(source['result_json'])
        recovery = connection.execute("SELECT result_json FROM phase_runs WHERE id=? AND action='maintain' AND method='recover' AND status='completed'",
                                       (facts.get('finalized_by'),)).fetchone()
        result = json.loads(recovery['result_json']) if recovery else {}
        if (facts.get('outcome') == 'reconciled_committed_metadata'
                and facts.get('saved_operation_result') == {'verification_id': verification['id'], 'status': 'passed'}
                and result.get('original_run_id') == verification['source_run_id'] and result.get('original_facts_committed') is True):
            return source
    return None


def record_check(store, run_id, item, *, verification_id=None):
    from .store import identifier, now
    evidence_id = identifier()
    content_digest = store.blob(canonical(item))
    store.connection.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)',
                             (evidence_id, run_id, verification_id, 'applied', 'local-process', 'argv-check',
                              content_digest, now(), 'Command success alone does not prove every acceptance condition'))
    return evidence_id


def check_event_sink(store, request, run_id, operation_id, expected_versions):
    from .workspace import writer_lock
    def record(kind, details):
        with writer_lock(store.root):
            gate(store, request, run_id, operation_id, expected_versions)
            from .protection import record_check as protect_check
            from .store import now
            protect_check(store.root, store.meta, kind, details, now())
            with store.transaction():
                store.event(run_id, kind, details)
    return record
