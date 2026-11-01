"""Bind data operations to the existing work model and its independent verification."""
import json

from .errors import EvolveError
from .package import canonical, digest
from .workspace import current_digest, inside


def definition_fields(root, source):
    kind = source.get('execution_kind')
    if kind is None:
        if source.get('external_target') is not None:
            raise EvolveError('EXTERNAL_TASK', 'An external target must be an explicit external_write task')
        return {}
    if kind != 'external_write' or source.get('responsible_action', 'apply') != 'apply' or source.get('pre_refactor'):
        raise EvolveError('EXTERNAL_TASK', 'External data work uses apply with its own exact target, not formal/refactor execution')
    target = source.get('external_target')
    if (not isinstance(target, dict) or target.get('kind') != 'sqlite'
            or target.get('environment') not in ('isolated', 'test', 'production')
            or not isinstance(target.get('objects'), list) or not target['objects']
            or any(not isinstance(x, str) or not x for x in target['objects'])
            or not isinstance(target.get('scope'), str) or not target['scope'].strip()
            or not isinstance(target.get('identity'), dict) or not target['identity'].get('expected')
            or not isinstance(target['identity'].get('sql'), str) or not target['identity']['sql'].strip()):
        raise EvolveError('EXTERNAL_TASK', 'The actual plan must state the target provider/environment/objects/scope/identity probe')
    from .plans import business_path
    business_path(root, target.get('path'))
    if not source.get('required_checks'):
        raise EvolveError('EXTERNAL_TASK', 'External data work requires an explicit independent business check')
    return {'execution_kind': kind, 'external_target': target}


def bind(store, request, *, validate_versions=True):
    from .work import change_context, check_basis, implementation_baseline
    change, revision, task, definition = change_context(store, request, require_task=True, versions=validate_versions)
    if definition.get('execution_kind') != 'external_write':
        raise EvolveError('EXTERNAL_TASK', 'Use a presented external_write Change/Task before writing business data')
    if request['input'].get('accepted_plan_digest') != revision['plan_digest']:
        raise EvolveError('PLAN_ACCEPTANCE', 'External work must bind its current concrete business plan')
    check_basis(store.root, definition)
    dependency_basis = {}
    if definition.get('structured'):
        from .structured import current_tasks, dependency_basis as dependencies, readiness
        peers = current_tasks(store.connection, change['id'], revision['id'])
        state = readiness(store.connection, store.root, task, peers)
        if state['unmet']:
            raise EvolveError('DEPENDENCY_NOT_READY', 'External task prerequisites are not satisfied: ' + json.dumps(state['unmet']), exit_code=3)
        dependency_basis = dependencies(store.connection, task, peers)
    previous = json.loads(task['result_json']) if task['result_json'] else None
    baseline = implementation_baseline(store, change, definition, previous)
    sources = {p: current_digest(inside(store.root, p)) for p in definition['scope']}
    observed = request['input'].get('observations', {})
    if not isinstance(observed, dict):
        raise EvolveError('OBSERVATION', 'Source observations must bind actual project paths and digests')
    if any(value != baseline[path] and observed.get(path) != value for path, value in sources.items()):
        raise EvolveError('FILE_CONFLICT', 'Changed task mechanisms/checks require actual observations or a revision', exit_code=3)
    value = {'change_id': change['id'], 'revision_id': revision['id'], 'task_id': task['id'],
             'definition_digest': task['definition_digest'], 'accepted_plan_digest': revision['plan_digest'],
             'external_target': definition['external_target'], 'sources': sources, 'dependency_basis': dependency_basis}
    return value, change, revision, task, definition


def assert_candidate(binding, candidate):
    if binding['external_target'] != candidate['target']:
        raise EvolveError('EXTERNAL_TASK', 'Execution candidate targets a different business plan environment/scope')
    if not {r['path'] for r in candidate['execution']['files']}.issubset(binding['sources']):
        raise EvolveError('EXTERNAL_TASK', 'Execution material exceeds this presented task mechanism scope')
    if candidate.get('work_binding') is not None and candidate['work_binding'] != binding:
        raise EvolveError('EXTERNAL_TASK_CHANGED', 'The approved candidate belongs to another current task/spec/source basis', exit_code=3)



def assert_check_candidate(store, binding, candidate):
    """Readonly continuation may use proven same-definition task ancestry."""
    original = candidate.get('work_binding')
    if original is None or original == binding:
        return assert_candidate(binding, candidate)
    from .revisions import origin_tasks
    task = store.one('SELECT * FROM tasks WHERE id=?', (binding['task_id'],))
    origins = {(t['id'], t['revision_id']) for t in origin_tasks(store.connection, task)}
    if ((original['task_id'], original['revision_id']) not in origins
            or any(original[k] != binding[k] for k in ('change_id', 'definition_digest', 'external_target', 'sources', 'dependency_basis'))):
        raise EvolveError('EXTERNAL_TASK_CHANGED', 'Readonly check continuation lacks proven identical task/source/dependency ancestry', exit_code=3)
    assert_candidate(binding, {**candidate, 'work_binding': binding})

def begin(store, request, run_id, operation_id, candidate):
    from .work import fingerprint
    binding, change, revision, task, definition = bind(store, request)
    assert_candidate(binding, candidate)
    if task['state'] == 'done':
        from .revisions import eligible_verifications
        failed = next((v for v in eligible_verifications(store.connection, change['id'], revision['id'], task)
                       if v['status'] in ('failed', 'blocked')), None)
        if not failed or request['input'].get('reopen_verification_id') != failed['id']:
            raise EvolveError('TASK_DONE', 'A completed data task needs an actual failed verification or a new revision', exit_code=3)
    snapshot = fingerprint(store.root, definition)
    if revision['accepted_event_id'] is None:
        event = store.event(run_id, 'plan_accepted', {'revision_id': revision['id'], 'plan_digest': revision['plan_digest'],
                                                   'authorization': request['authorization']})
        store.connection.execute('UPDATE plan_revisions SET accepted_event_id=? WHERE id=?', (event, revision['id']))
    if task['result_json']:
        previous = store.blob(task['result_json'].encode())
        store.event(run_id, 'external_prior_task_result_preserved', {'task_id': task['id'], 'result_digest': previous})
    result = {'definition_digest': task['definition_digest'], 'fingerprint': snapshot,
              'external_operation_id': operation_id, 'external_effect_outcome': 'unknown',
              'dependency_basis': binding['dependency_basis'], 'artifacts': [], 'check_evidence': []}
    store.connection.execute("UPDATE changes SET state='active',row_version=row_version+1 WHERE id=?", (change['id'],))
    store.connection.execute("UPDATE tasks SET state='in_progress',result_json=?,row_version=row_version+1 WHERE id=?",
                             (canonical(result).decode(), task['id']))
    store.event(run_id, 'external_task_started', {'work_binding': binding, 'operation_id': operation_id,
                                               'business_acceptance': 'not_inferred'})
    return binding


def observe_result(store, observer_run_id, capsule, value):
    binding = capsule['candidate'].get('work_binding')
    if binding is None:
        return
    task = store.one('SELECT t.*,c.state AS change_state,c.current_revision FROM tasks t JOIN changes c ON c.id=t.change_id WHERE t.id=?', (binding['task_id'],))
    if (not task or task['current_revision'] != binding['revision_id'] or task['definition_digest'] != binding['definition_digest']
            or task['change_state'] in ('cancelled', 'archived')):
        store.event(observer_run_id, 'external_work_observation_unattached', {'operation_id': capsule['operation_id'],
            'original_work_binding': binding, 'reason': 'Original definition is no longer an active current task; do not recreate or reopen it.'})
        return
    from .work import fingerprint
    definition = json.loads(task['definition_json'])
    saved = json.loads(task['result_json']) if task['result_json'] else {
        'definition_digest': task['definition_digest'], 'fingerprint': fingerprint(store.root, definition),
        'dependency_basis': binding['dependency_basis'], 'artifacts': [], 'check_evidence': []}
    if saved.get('external_operation_id') not in (None, capsule['operation_id']):
        store.event(observer_run_id, 'external_work_observation_unattached', {'operation_id': capsule['operation_id'],
            'original_work_binding': binding, 'reason': 'The current task records a different operation; retain this source without replacing it.'})
        return
    saved.update(external_operation_id=capsule['operation_id'], external_effect_outcome=value['effect_outcome'],
                 external_capsule=value['capsule'], external_observation_digest=value.get('confirmed_observation_digest'),
                 external_observer_run_id=observer_run_id)
    store.connection.execute('UPDATE tasks SET result_json=?,row_version=row_version+1 WHERE id=?',
                              (canonical(saved).decode(), task['id']))
    store.event(observer_run_id, 'external_work_effect_attached', {'task_id': task['id'], 'operation_id': capsule['operation_id'],
                'effect_outcome': value['effect_outcome'], 'task_complete': 'not_inferred', 'business_acceptance': 'not_inferred'})


def stable_goal_basis(observation):
    return digest(canonical({k: observation.get(k) for k in ('effect_outcome', 'terminal_confirmed',
        'provider_receipt', 'scope_observations')}))


def run_task_checks(store, request, run_id, owner_operation_id, capsule):
    """Only task checks; no dispatch, retries or implicit whole-change verification."""
    from .checks import run_check
    from .external import effect_probe, observation_gate
    from .protection import record_check as protect_check
    from .store import now
    from .work import check_basis, fingerprint, gate_identity, record_check, versions
    from .workspace import writer_lock
    candidate = capsule['candidate']
    binding = candidate.get('work_binding')
    if binding is None:
        return {}
    def guard(*, admission=False):
        (gate_identity if admission else observation_gate)(store, request, run_id)
        current, change, revision, task, definition = bind(store, request, validate_versions=False)
        assert_check_candidate(store, current, candidate)
        claim = store.one('SELECT operation_id FROM resource_claims WHERE resource=?', ('change:' + change['id'],))
        if not claim or claim[0] != owner_operation_id:
            raise EvolveError('CLAIM', 'Data task checks no longer own this current work item', exit_code=4)
        return change, revision, task, definition
    def sink(kind, details):
        with writer_lock(store.root):
            guard(admission=kind == 'check_dispatch_prepared')
            protect_check(store.root, store.meta, kind, {**details, 'run_id': run_id}, now())
            with store.transaction():
                store.event(run_id, kind, details)
    with writer_lock(store.root):
        change, revision, task, definition = guard(admission=True)
        snapshot = fingerprint(store.root, definition)
        checks = check_basis(store.root, definition)
    results, evidence = [], []
    for check in checks:
        result = run_check(store.root, check, event_sink=sink)
        with writer_lock(store.root):
            guard()
            with store.transaction():
                evidence.append(record_check(store, run_id, result))
                store.event(run_id, 'task_check', {'check_id': check['id'], 'status': result['status'], 'evidence_id': evidence[-1]})
        results.append(result)
        if result['unfinished_processes']:
            raise EvolveError('CHECK_RUNNING', 'A task check remains active; preserve work ownership until it is observed to stop', exit_code=4, committed=True)
    goal = effect_probe(store.root, capsule, True)
    with writer_lock(store.root):
        change, revision, task, definition = guard()
        current = fingerprint(store.root, definition)
        missing = [p for p, value in current['scope'].items() if value is None]
        passed = (current['digest'] == snapshot['digest'] and not missing
                  and all(r['status'] == 'passed' for r in results)
                  and goal['terminal_confirmed'] and goal['effect_outcome'] == 'succeeded')
        target = candidate['target']['path']
        saved = {'definition_digest': task['definition_digest'], 'fingerprint': current,
            'dependency_basis': binding['dependency_basis'], 'artifacts': [], 'check_evidence': evidence,
            'external_operation_id': capsule['operation_id'], 'external_capsule': {'capsule_path': '.evolve-local/control/external-records/' + capsule['operation_id'] + '.json',
                'capsule_digest': digest(canonical(capsule))}, 'external_effect_outcome': goal['effect_outcome'],
            'external_goal_basis_digest': stable_goal_basis(goal), 'external_scope_file_digest': current['files'].get(target),
            'external_checks_source_run_id': run_id, 'external_checks_passed': passed,
            'implementation_source': 'approved_external_operation_and_actual_task_checks'}
        with store.transaction() as db:
            blob = store.blob(canonical(goal))
            saved['external_goal_observation_digest'] = blob
            db.execute('UPDATE tasks SET state=?,row_version=row_version+1,result_json=? WHERE id=?',
                ('done' if passed else 'in_progress', canonical(saved).decode(), task['id']))
            if definition.get('structured'):
                from .structured import invalidate_dependents
                invalidate_dependents(store, run_id, change['id'], revision['id'])
            db.execute('DELETE FROM resource_claims WHERE operation_id=?', (owner_operation_id,))
            fact = {'task_id': task['id'], 'external_operation_id': capsule['operation_id'],
                    'task_result_digest': digest(canonical(saved)), 'completed': passed, 'business_acceptance': 'not_inferred'}
            store.event(run_id, 'external_task_checks_committed', fact)
            if owner_operation_id != capsule['operation_id']:
                db.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?", (canonical(fact).decode(), owner_operation_id))
        return {'task_checks': [{**{k: r[k] for k in ('check_id', 'status', 'returncode')}, 'evidence_id': evidence[i]}
                    for i, r in enumerate(results)], 'task_completed': passed, 'task_id': task['id'],
                'change_id': change['id'], 'revision_id': revision['id'], 'versions': versions(store, change['id'], task['id']),
                'overall_verification': 'not_run', 'external_goal_observation': goal}


def recorded_complete(connection, root, task, definition, saved):
    """Pure metadata/file observation for navigation and archive; no business SQL."""
    if definition.get('execution_kind') != 'external_write':
        return True
    if (not saved or not saved.get('external_checks_passed') or not saved.get('external_operation_id')
            or not saved.get('external_goal_basis_digest')):
        return False
    try:
        from . import external_registry as registry
        from .external import resources_for
        from .external_material import regular_path
        meta = dict(connection.execute('SELECT key,value FROM project_meta'))
        op = connection.execute('SELECT result_json FROM operations WHERE id=?', (saved['external_operation_id'],)).fetchone()
        value = json.loads(op[0]) if op and op[0] else {}
        if not value.get('terminal_confirmed') or value.get('effect_outcome') != 'succeeded':
            return False
        capsule = registry.read_capsule(root, {'operation_id': saved['external_operation_id'], **saved['external_capsule']}, meta['project_id'])
        candidate = capsule['candidate']
        if candidate['target'] != definition['external_target']:
            return False
        path = regular_path(root, candidate['target']['path'])
        actual = path.stat()
        expected = candidate['target_snapshot']
        if (actual.st_dev, actual.st_ino) != (expected['device'], expected['inode']):
            return False
        if current_digest(path) != saved['external_scope_file_digest']:
            return False
        index, _ = registry.load_index(root, meta)
        if index.get('coverage') == 'unverified' or any(set(r['resources']) & set(resources_for(candidate)) for r in index['pending']):
            return False
        source = connection.execute('SELECT status,result_json,result_digest FROM phase_runs WHERE id=?', (saved['external_checks_source_run_id'],)).fetchone()
        if not source or source['status'] not in ('completed', 'interrupted') or not source['result_json']:
            return False
        return digest(canonical(json.loads(source['result_json']))) == source['result_digest']
    except (EvolveError, ValueError, TypeError, KeyError, OSError):
        return False


def selected_tasks(connection, change, revision, task, definition):
    if definition.get('whole_change'):
        return connection.execute('SELECT * FROM tasks WHERE change_id=? AND revision_id=?', (change['id'], revision['id'])).fetchall()
    return [task]


def verification_basis(connection, root, change, revision, task, definition, request):
    """Independent verify explicitly observes real data, not just source fingerprints."""
    from .external import effect_probe, require_target_grant
    from . import external_registry as registry
    from .requests import require_effect
    meta = dict(connection.execute('SELECT key,value FROM project_meta'))
    result = {}
    for item in selected_tasks(connection, change, revision, task, definition):
        declared = json.loads(item['definition_json'])
        if declared.get('execution_kind') != 'external_write':
            continue
        require_effect(request, 'external_read')
        require_target_grant(request, declared['external_target'])
        saved = json.loads(item['result_json']) if item['result_json'] else {}
        try:
            capsule = registry.read_capsule(root, {'operation_id': saved.get('external_operation_id'),
                **saved.get('external_capsule', {})}, meta['project_id'])
            observed = effect_probe(root, capsule, True)
            passed = bool(recorded_complete(connection, root, item, declared, saved) and observed['terminal_confirmed']
                          and observed['effect_outcome'] == 'succeeded')
            result[item['id']] = {'status': 'passed' if passed else 'blocked',
                'operation_id': saved.get('external_operation_id'), 'basis_digest': stable_goal_basis(observed), 'observation': observed}
        except (EvolveError, ValueError, TypeError, KeyError, OSError) as error:
            result[item['id']] = {'status': 'blocked', 'error': str(error), 'business_success': 'not_inferred'}
    return result


def archive_basis(connection, root, change, revision, task, definition, verification):
    items = json.loads(verification['items_json'])
    inspected = items.get('external_goal_observations', {})
    for item in selected_tasks(connection, change, revision, task, definition):
        declared = json.loads(item['definition_json'])
        if declared.get('execution_kind') != 'external_write':
            continue
        saved = json.loads(item['result_json']) if item['result_json'] else {}
        if (not recorded_complete(connection, root, item, declared, saved)
                or inspected.get(item['id'], {}).get('status') != 'passed'
                or inspected[item['id']].get('basis_digest') != saved.get('external_goal_basis_digest')):
            raise EvolveError('EXTERNAL_SCOPE_UNCONFIRMED', 'Archive needs the current exact data goal verification and no related pending external effect', exit_code=3)
