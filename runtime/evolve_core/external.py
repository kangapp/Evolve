"""Explicit external candidate records; dispatch/reconciliation gates are built here."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile

from .errors import EvolveError
from .external_material import (collect_material, freeze_material, read_query, regular_path, require_current,
                                target_snapshot, validate_frozen)
from . import external_registry as registry
from .external_process import finish_process, receipt as transport_receipt
from .privacy import ensure_recordable
from .package import canonical, check_package, digest
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .workspace import inside, process_alive, writer_lock
from .work import gate_identity


def require_target_grant(request, target):
    grants = request['authorization'].get('external_targets')
    selected = {k: target.get(k) for k in ('kind', 'path', 'environment', 'objects', 'scope')}
    selected['provider_identity'] = target.get('identity', {}).get('expected')
    if not isinstance(grants, list) or selected not in grants:
        raise EvolveError('EXTERNAL_AUTHORIZATION', 'Actual authorization must identify this environment, provider, object and exact data scope', exit_code=3)


def parameters(values, operation_id):
    if not isinstance(values, list) or any(type(v) not in (str, int, float, bool, type(None)) for v in values):
        raise EvolveError('EXTERNAL_QUERY', 'Observation parameters must be explicit non-secret scalar values')
    return [operation_id if v == '{operation_id}' else v for v in values]


def probe(root, target, query, operation_id):
    if not isinstance(query, dict):
        raise EvolveError('EXTERNAL_QUERY', 'Provide an exact read-only observation query')
    return read_query(regular_path(root, target['path']), query.get('sql'),
                      parameters(query.get('parameters', []), operation_id))


def query_items(value, name):
    if not isinstance(value, list) or not value or len(value) > 16:
        raise EvolveError('EXTERNAL_QUERY', name + ' needs 1–16 explicit read-only queries')
    for item in value:
        if (not isinstance(item, dict) or not isinstance(item.get('description'), str) or not item['description'].strip()
                or not isinstance(item.get('sql'), str) or not item['sql'].strip()
                or not isinstance(item.get('expected_rows'), list)
                or any(not isinstance(row, list) for row in item['expected_rows'])):
            raise EvolveError('EXTERNAL_QUERY', 'Each scope query needs SQL, expected_rows and an actual description')
        parameters(item.get('parameters', []), 'not-dispatched')
    return value


def build_candidate(root, data):
    """Read real target facts and all finite material; never dispatch a command."""
    target = data.get('target')
    actual = target_snapshot(root, target)
    execution = collect_material(root, data.get('execution'), regular_path(root, target['path']))
    idempotency = data.get('idempotency')
    if (not isinstance(idempotency, dict) or type(idempotency.get('supported')) is not bool
            or not isinstance(idempotency.get('basis'), str) or not idempotency['basis'].strip()):
        raise EvolveError('EXTERNAL_CAPABILITY', 'State actual provider idempotency support and its inspected basis; do not infer it from exit status')
    limitations = data.get('limitations')
    if not isinstance(limitations, list) or not limitations or any(not isinstance(s, str) or not s.strip() for s in limitations):
        raise EvolveError('EXTERNAL_CAPABILITY', 'Preserve actual provider/idempotency/observation limits explicitly')
    preconditions = query_items(data.get('preconditions'), 'Preconditions')
    reconciliation = data.get('reconciliation')
    if (not isinstance(reconciliation, dict) or not isinstance(reconciliation.get('receipt'), dict)
            or reconciliation.get('complete_scope') is not True
            or not isinstance(reconciliation.get('coverage_basis'), str) or not reconciliation['coverage_basis'].strip()
            or reconciliation['receipt'].get('parameters', []).count('{operation_id}') != 1):
        raise EvolveError('EXTERNAL_CAPABILITY', 'Reliable receipt query, complete scoped observation and actual coverage basis are required')
    effects = query_items(reconciliation.get('effects'), 'Scope effects')
    candidate_id = identifier()
    preview_id = 'not-dispatched-' + candidate_id
    receipt = probe(root, target, reconciliation['receipt'], preview_id)
    if receipt['columns'] != ['operation_id', 'outcome', 'known_effects_json', 'finished']:
        raise EvolveError('EXTERNAL_CAPABILITY', 'Receipt query must return operation_id/outcome/known_effects_json/finished in that order')
    observed_preconditions = [probe(root, target, q, preview_id) for q in preconditions]
    effects_before = [probe(root, target, q, preview_id) for q in effects]
    if target_snapshot(root, target) != actual:
        raise EvolveError('EXTERNAL_TARGET_CHANGED', 'Target changed during actual candidate observation', exit_code=3)
    return {'format': 'evolve-external-candidate-v1', 'candidate_id': candidate_id, 'observed_at': now(),
            'target': target, 'target_snapshot': actual, 'execution': execution,
            'preconditions': preconditions, 'preconditions_observed': observed_preconditions,
            'reconciliation': reconciliation, 'effects_before': effects_before, 'idempotency': idempotency, 'limitations': limitations,
            'ready': all(q['expected_rows'] == observed['rows'] for q, observed in zip(preconditions, observed_preconditions)),
            'dispatch_performed': False, 'business_acceptance': 'not_inferred'}


def prepare(root, payload, *, method='external.execute'):
    root, request = Path(root).resolve(), normalize(payload)
    require_effect(request, 'project_records')
    require_effect(request, 'external_read')
    if request['input'].get('stage') != 'prepare' or method not in ('external.execute', 'external.compensate'):
        raise EvolveError('EXTERNAL_UNAVAILABLE', 'Only candidate preparation is implemented at this development point')
    target = request['input'].get('target')
    if not isinstance(target, dict):
        raise EvolveError('EXTERNAL_TARGET', 'Select an explicit external target')
    require_target_grant(request, target)
    store, run_id, work_binding, compensation = None, None, None, None
    try:
        with writer_lock(root):
            store = Store(root)
            previous = store.lookup(request, action='apply', method=method, owner='evolve-apply')
            if previous is not None:
                return previous[1]
            if request['input'].get('change_id'):
                from .external_work import bind
                work_binding = bind(store, request)[0]
            if method == 'external.compensate':
                from .external_actions import compensation_source
                compensation = compensation_source(store, request)
            run_id, _ = store.start(request, action='apply', method=method, owner='evolve-apply')
        # Target/material IO does not hold the shared writer control section.
        candidate = build_candidate(root, request['input'])
        if compensation is not None:
            from .external_actions import observe_compensation
            candidate['compensation_of'] = {**compensation[0], 'current_scope_basis_digest': observe_compensation(root, compensation[1], candidate)}
        if work_binding is not None:
            from .external_work import assert_candidate
            assert_candidate(work_binding, candidate)
            candidate['work_binding'] = work_binding
        with writer_lock(root):
            if work_binding is not None:
                from .external_work import bind, assert_candidate
                assert_candidate(bind(store, request, validate_versions=False)[0], candidate)
            gate_identity(store, request, run_id)
            with store.transaction():
                artifact = store.artifact(None, 'external_candidate', canonical(candidate), run_id, 'evolve-apply:external-candidate')
                store.event(run_id, 'external_candidate_prepared', {'candidate_id': candidate['candidate_id'],
                    'candidate_digest': digest(canonical(candidate)), 'artifact': artifact, 'dispatch_performed': False})
            return store.finish(run_id, {'committed': True, 'outcome': 'external_candidate_prepared',
                'candidate': candidate, 'candidate_digest': digest(canonical(candidate)), 'artifact': artifact,
                'ready': candidate['ready'], 'dispatch_performed': False, 'approval': 'not_implied',
                'business_acceptance': 'not_inferred'})
    except EvolveError as error:
        if store is not None and run_id is not None and store.run_started(run_id):
            with writer_lock(root):
                store.finish(run_id, {'committed': True, 'outcome': 'external_candidate_blocked',
                    'error': {'code': error.code, 'message': str(error)}, 'dispatch_performed': False}, status='blocked')
        raise
    finally:
        if store is not None:
            store.close()


def selected_candidate(store, reference, method='external.execute'):
    if not isinstance(reference, dict):
        raise EvolveError('EXTERNAL_CANDIDATE', 'Select the exact saved candidate run/result digest')
    row = store.one('SELECT * FROM phase_runs WHERE id=?', (reference.get('run_id'),))
    if (not row or row['status'] != 'completed' or (row['action'], row['method']) != ('apply', method)
            or row['result_digest'] != reference.get('result_digest') or not row['result_json']):
        raise EvolveError('EXTERNAL_CANDIDATE', 'Candidate source is missing, incomplete or has another result digest')
    value = json.loads(row['result_json'])
    if digest(canonical(value)) != row['result_digest'] or value.get('outcome') != 'external_candidate_prepared':
        raise EvolveError('EXTERNAL_CANDIDATE', 'Candidate source result is not its actual immutable preparation')
    candidate = value['candidate']
    if (row['workspace_epoch'] != store.meta['workspace_epoch']
            or value['candidate_digest'] != digest(canonical(candidate))):
        raise EvolveError('WORKSPACE_EPOCH', 'A candidate cannot inherit write approval across archive restoration', exit_code=3)
    return candidate


def resources_for(candidate):
    target = candidate['target_snapshot']
    identity = digest(canonical({k: target[k] for k in ('kind', 'provider_identity', 'environment')}))
    return ['external:' + identity + ':object:' + name for name in target['objects']]


def require_preconditions(root, candidate):
    observed = [probe(root, candidate['target'], q, 'not-dispatched') for q in candidate['preconditions']]
    if not candidate['ready'] or any(q['expected_rows'] != actual['rows'] for q, actual in zip(candidate['preconditions'], observed)):
        raise EvolveError('EXTERNAL_PRECONDITION', 'Actual data preconditions differ from the exact approved candidate', exit_code=3)
    return observed


def approval_for(request, candidate):
    value = request['input'].get('approval')
    if (not isinstance(value, dict) or value.get('candidate_digest') != digest(canonical(candidate))
            or value.get('target_digest') != candidate['target_snapshot']['digest']
            or any(not isinstance(value.get(k), str) or not value[k].strip() for k in ('source', 'text'))):
        raise EvolveError('EXTERNAL_APPROVAL', 'Actual approval must bind this exact candidate, resolved target and specific scope', exit_code=3)
    return value


def observation_gate(store, request, run_id):
    """Permit recording past effects after revocation, while still fencing old stores."""
    store.assert_current_database()
    meta = dict(store.connection.execute('SELECT key,value FROM project_meta'))
    row = store.one('SELECT * FROM phase_runs WHERE id=?', (run_id,))
    if (meta['project_id'] != request['project_id'] or meta['workspace_epoch'] != request['expected_workspace_epoch']
            or not row or row['status'] != 'started' or row['package_digest'] != check_package()['content_digest']):
        raise EvolveError('EXECUTION_CHANGED', 'Past effects must be recorded in the actual current epoch/run', exit_code=4)


def effect_probe(root, capsule, sender_stopped):
    """Observe the real provider receipt and all declared data scope, never resend."""
    candidate, operation_id = capsule['candidate'], capsule['operation_id']
    base = {'observed_at': now(), 'source': 'actual-read-only-sqlite-observation',
            'effect_outcome': 'unknown', 'terminal_confirmed': False, 'verification_status': 'unconfirmed',
            'sender_stopped': sender_stopped, 'business_acceptance': 'not_inferred'}
    try:
        if target_snapshot(root, candidate['target']) != candidate['target_snapshot']:
            raise EvolveError('EXTERNAL_TARGET_CHANGED', 'The actual target differs from the operation source')
        policy = candidate['reconciliation']
        actual_receipt = probe(root, candidate['target'], policy['receipt'], operation_id)
        actual_scope = [probe(root, candidate['target'], q, operation_id) for q in policy['effects']]
        value = {**base, 'provider_receipt': actual_receipt, 'scope_observations': actual_scope}
        if len(actual_receipt['rows']) != 1 or actual_receipt['rows'][0][0] != operation_id:
            return {**value, 'limitations': ['No unique matching provider receipt; current data alone cannot attribute an operation or prove it never ran.']}
        row = actual_receipt['rows'][0]
        if len(row) != 4 or row[1] not in ('not_started', 'running', 'succeeded', 'failed', 'unknown'):
            return {**value, 'limitations': ['Provider outcome is not an interpretable operation observation.']}
        known = json.loads(row[2])
        ensure_recordable(known)
        value.update(provider_claim=row[1], provider_known_effects=known)
        if not sender_stopped or row[3] != 1 or row[1] not in ('not_started', 'succeeded', 'failed'):
            return {**value, 'effect_outcome': 'running' if row[1] == 'running' else 'unknown',
                    'limitations': ['Sender or provider termination/full effects are not established; retain protection.']}
        matched = all(actual['rows'] == [parameters(r, operation_id) for r in query['expected_rows']]
                      for query, actual in zip(policy['effects'], actual_scope))
        unchanged = all(actual == before for actual, before in zip(actual_scope, candidate['effects_before']))
        if row[1] == 'not_started' and not unchanged:
            return {**value, 'limitations': ['Provider says not_started but actual complete scope differs from the observed baseline.']}
        outcome = ('not_started' if row[1] == 'not_started' else 'succeeded' if row[1] == 'succeeded' and matched else 'failed')
        return {**value, 'effect_outcome': outcome, 'terminal_confirmed': True,
                'verification_status': 'passed' if outcome == 'succeeded' else 'failed' if outcome == 'failed' else 'not_run',
                'complete_scope_basis': policy['coverage_basis'], 'limitations': candidate['limitations']}
    except (EvolveError, ValueError, TypeError, IndexError) as error:
        return {**base, 'error': {'code': error.code if isinstance(error, EvolveError) else 'EXTERNAL_RECEIPT_INVALID',
                                'message': str(error)},
                'limitations': ['Observation failed; do not erase previous confirmed facts or release unknown effects.']}


def fault_point(name):
    """Controlled tests replace this function in their own child; no product switch."""


def operation_value(capsule, reference):
    return {'format': 'evolve-external-operation-v1', 'candidate_id': capsule['candidate']['candidate_id'],
            'candidate_digest': capsule['candidate_digest'], 'target_snapshot': capsule['candidate']['target_snapshot'],
            'resources': capsule['resources'], 'capsule': reference, 'effect_outcome': 'not_started',
            'terminal_confirmed': False, 'business_acceptance': 'not_inferred'}


def record_effect(store, run_id, operation_id, capsule, reference, observation, transport=None, *, release_resources=True):
    """DB observations are authority; leftover protection can only remain conservative."""
    index, expected = registry.load_index(store.root, store.meta)
    row = next((r for r in index['pending'] if r['operation_id'] == operation_id), None)
    current = store.one('SELECT result_json FROM operations WHERE id=?', (operation_id,))
    old = json.loads(current['result_json']) if current and current['result_json'] else operation_value(capsule, reference)
    value = {**old, 'last_observation': observation}
    if not old.get('terminal_confirmed'):
        value.update(effect_outcome=observation['effect_outcome'], terminal_confirmed=observation['terminal_confirmed'])
        if observation['terminal_confirmed']:
            value.update(confirmed_observation_digest=digest(canonical(observation)), confirmed_observation_run_id=run_id, confirmed_at=observation['observed_at'])
    if transport is not None:
        value['transport'] = transport
    if row and observation.get('sender_stopped'):
        row['sender'] = {**row['sender'], 'state': 'stopped'}
    if row:
        row['state'] = 'unknown' if value['effect_outcome'] != 'running' else 'running'
    with store.transaction() as db:
        evidence = store.blob(canonical(observation))
        from .external_work import observe_result
        observe_result(store, run_id, capsule, value)
        store.event(run_id, 'external_effect_observed', {'operation_id': operation_id, 'observation_digest': evidence,
            'effect_outcome': observation['effect_outcome'], 'terminal_confirmed': observation['terminal_confirmed'],
            'command_replayed': False})
        db.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?", (canonical(value).decode(), operation_id))
        if value['terminal_confirmed'] and release_resources:
            db.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
    if value['terminal_confirmed']:
        index['pending'] = [r for r in index['pending'] if r['operation_id'] != operation_id]
    registry.save_index(store.root, index, expected)
    return value


def execute(root, payload, *, method='external.execute'):
    request = normalize(payload)
    if request['input'].get('stage') == 'prepare':
        return prepare(root, request, method=method)
    if request['input'].get('stage') == 'checks':
        return check_existing(root, request, method=method)
    if request['input'].get('stage') != 'apply':
        raise EvolveError('INPUT', 'External execution stage must be prepare or apply')
    if set(request['input']) - {'stage', 'candidate_ref', 'approval', 'change_id', 'revision_id', 'task_id', 'task_key',
                                 'definition_digest', 'accepted_plan_digest', 'observations', 'reopen_verification_id'}:
        raise EvolveError('INPUT', 'Execution must use the exact prepared candidate; parameters/timeout belong in preparation')
    for effect in ('project_records', 'external_read', 'external_write'):
        require_effect(request, effect)
    if os.name != 'posix' or not hasattr(os, 'pread'):
        raise EvolveError('EXTERNAL_UNSUPPORTED', 'This execution mechanism requires observable local POSIX sender groups')
    root = Path(root).resolve()
    store, run_id, process = None, None, None
    output = tempfile.TemporaryFile()
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            previous = store.lookup(request, action='apply', method=method, owner='evolve-apply')
            if previous is not None:
                return previous[1]
            candidate = selected_candidate(store, request['input'].get('candidate_ref'), method)
            require_target_grant(request, candidate['target'])
            approval = approval_for(request, candidate)
            require_current(root, candidate)
            require_preconditions(root, candidate)
            if method == 'external.compensate':
                from .external_actions import compensation_source, observe_compensation
                source = candidate.get('compensation_of')
                if not source:
                    raise EvolveError('EXTERNAL_COMPENSATION_UNKNOWN', 'Compensation needs its own exact prepared source')
                _, original = compensation_source(store, request, source)
                if observe_compensation(root, original, candidate) != source['current_scope_basis_digest']:
                    raise EvolveError('EXTERNAL_COMPENSATION_CHANGED', 'Original scoped data changed after compensation preparation')
                if candidate.get('work_binding') and candidate['work_binding']['change_id'] == original['candidate'].get('work_binding', {}).get('change_id'):
                    raise EvolveError('EXTERNAL_COMPENSATION_TASK', 'Compensation requires its own separately approved Change and Task')
            index, expected = registry.load_index(root, store.meta)
            if index.get('coverage') == 'unverified':
                raise EvolveError('EXTERNAL_PROTECTION_UNKNOWN', 'Lost external protection needs a specific actual target audit; absence is not permission', exit_code=4)
            work_binding = None
            if request['input'].get('change_id'):
                from .external_work import bind, assert_candidate
                work_binding = bind(store, request)[0]
                if candidate.get('work_binding') is None:
                    raise EvolveError('EXTERNAL_TASK_CHANGED', 'A public work execution requires a candidate prepared for that exact task')
                assert_candidate(work_binding, candidate)
                require_effect(request, 'checks')
            resources = resources_for(candidate) + (['change:' + work_binding['change_id']] if work_binding else [])
            if any(set(row['resources']) & set(resources) for row in index['pending']):
                raise EvolveError('EXTERNAL_PENDING', 'This actual target/scope has a protected running or unknown operation', exit_code=3)
            for row in store.connection.execute("SELECT result_json FROM operations WHERE effect_kind='external_write'"):
                if row[0] and json.loads(row[0]).get('candidate_id') == candidate['candidate_id']:
                    raise EvolveError('EXTERNAL_CANDIDATE_USED', 'A specific approved candidate cannot be dispatched again under a new request', exit_code=3)
            if any(store.one('SELECT operation_id FROM resource_claims WHERE resource=?', (r,)) for r in resources):
                raise EvolveError('CLAIM', 'A related resource is already owned', exit_code=3)
            run_id, _ = store.start(request, action='apply', method=method, owner='evolve-apply')
            operation_id = identifier()
            material_folder = inside(root, '.evolve-local/control/external-material/' + operation_id)
            freeze_material(material_folder, candidate)
            argv = [candidate['execution']['interpreter']['path'], *candidate['execution']['python_flags'], str(inside(material_folder, candidate['execution']['argv'][0])),
                    *[candidate['target_snapshot']['resolved_path'] if arg == '{target}' else operation_id if arg == '{operation_id}' else arg
                      for arg in candidate['execution']['argv'][1:]]]
            cwd = inside(material_folder, candidate['execution']['cwd'])
            sender = {'execution_id': identifier(), 'command_digest': digest(canonical({'argv': argv, 'cwd': str(cwd)})),
                      'host': socket.gethostname(), 'prepared_at': now(), 'state': 'intent'}
            capsule = {'format': 'evolve-external-capsule-v1', 'project_id': store.meta['project_id'],
                'original_epoch': store.meta['workspace_epoch'], 'operation_id': operation_id, 'run_id': run_id,
                'request': request, 'candidate': candidate, 'candidate_digest': digest(canonical(candidate)),
                'approval': approval, 'authorization': request['authorization'], 'resources': resources,
                'generation': generation, 'sender_identity': dict(sender), 'material_folder': material_folder.relative_to(root).as_posix(),
                'argv': argv, 'cwd': str(cwd), 'created_at': now()}
            reference = registry.save_capsule(root, capsule)
            value = operation_value(capsule, reference)
            with store.transaction() as db:
                if work_binding is not None:
                    from .external_work import begin
                    begin(store, request, run_id, operation_id, candidate)
                store.artifact(None, 'external_capsule', canonical(capsule), run_id, 'evolve-apply:external-protection-source')
                db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,NULL)',
                    (operation_id, run_id, 'external_write', 'prepared', digest(canonical(request)), canonical(value).decode()))
                for resource in resources:
                    db.execute('INSERT INTO resource_claims VALUES (?,?,?,?,1)',
                        (resource, operation_id, 'held', canonical(generation).decode()))
                store.link_source(run_id, request['input']['candidate_ref']['run_id'], request['input']['candidate_ref']['result_digest'], 'external_execution_candidate')
                store.event(run_id, 'external_operation_registered', {'operation_id': operation_id, 'capsule': reference,
                    'idempotency_key': operation_id, 'provider_idempotency': candidate['idempotency'], 'dispatch_performed': False})
            fault_point('registered')
            index['pending'].append({**reference, 'operation_id': operation_id, 'state': 'unknown', 'resources': resources,
                'target': {k: candidate['target_snapshot'][k] for k in ('provider_identity', 'resolved_path', 'environment', 'objects', 'scope')},
                'sender': sender, 'original_epoch': store.meta['workspace_epoch']})
            expected = registry.save_index(root, index, expected)
            with store.transaction() as db:
                db.execute("UPDATE operations SET state='applying' WHERE id=?", (operation_id,))
                store.event(run_id, 'external_dispatch_admitted', {'operation_id': operation_id, 'sender': sender, 'generation': generation})
            gate_identity(store, request, run_id)
            validate_frozen(material_folder, candidate)
            require_current(root, candidate)
            require_preconditions(root, candidate)
            fault_point('before_launch')
            environment = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR')}
            environment.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
            process = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            fault_point('launched_before_pid_receipt')
            sender.update(pid=process.pid, state='started')
            index['pending'][-1]['sender'] = sender
            expected = registry.save_index(root, index, expected)
            with store.transaction():
                store.event(run_id, 'external_sender_started', {'operation_id': operation_id, 'sender': sender})
            fault_point('sender_recorded')
        transport = finish_process(process, output, candidate['execution']['timeout'])
        fault_point('sender_finished_before_receipt')
        stopped = not transport['process_group_present']
        acknowledged = transport_receipt(transport, operation_id, candidate['target_snapshot']['provider_identity'])
        observation = (effect_probe(root, capsule, stopped) if acknowledged else {
            'observed_at': now(), 'source': 'actual-command-transport', 'effect_outcome': 'unknown',
            'terminal_confirmed': False, 'verification_status': 'unconfirmed', 'sender_stopped': stopped,
            'limitations': ['Sender timeout/exit or missing valid transport receipt does not prove no effects; reconcile this exact operation.'],
            'business_acceptance': 'not_inferred'})
        with writer_lock(root):
            observation_gate(store, request, run_id)
            result = record_effect(store, run_id, operation_id, capsule, reference, observation, transport,
                                   release_resources=not bool(candidate.get('work_binding')))
        work_result = {}
        if candidate.get('work_binding') and result['effect_outcome'] == 'succeeded':
            from .external_work import run_task_checks
            work_result = run_task_checks(store, request, run_id, operation_id, capsule)
            fault_point('task_checks_committed')
        elif candidate.get('work_binding') and result['terminal_confirmed']:
            with writer_lock(root):
                with store.transaction() as db:
                    db.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
        with writer_lock(root):
            observation_gate(store, request, run_id)
            return store.finish(run_id, {'committed': True, **work_result,
                'outcome': 'external_' + result['effect_outcome'], 'operation_id': operation_id,
                'effect_outcome': result['effect_outcome'], 'effect_record': result,
                'next_step': 'verify actual business goal' if result['terminal_confirmed'] else 'external.reconcile only; do not resend',
                'business_acceptance': 'not_inferred'})
    finally:
        output.close()
        if store is not None:
            store.close()


def resolve_operation(store, operation_id, check_observations=()):
    registry.record_path(store.root, operation_id)
    index, expected = registry.load_index(store.root, store.meta)
    pending = next((r for r in index['pending'] if r['operation_id'] == operation_id), None)
    operation = store.one('SELECT * FROM operations WHERE id=?', (operation_id,))
    if operation and operation['effect_kind'] != 'external_write':
        raise EvolveError('EXTERNAL_OPERATION', 'This identity is not an external data operation')
    value = json.loads(operation['result_json']) if operation and operation['result_json'] else None
    registry.require_recorded_reference(pending, (value or {}) if operation else None)
    reference = pending or (value or {}).get('capsule')
    if not isinstance(reference, dict) or not reference.get('capsule_path'):
        raise EvolveError('EXTERNAL_SOURCE_UNKNOWN', 'No exact protected source is available for this operation', exit_code=4)
    capsule = registry.read_capsule(store.root, {**reference, 'operation_id': operation_id}, store.meta['project_id'])
    original = store.one('SELECT * FROM phase_runs WHERE id=?', (capsule['run_id'],))
    if original and original['status'] == 'started':
        from .checks import pending_checks, validate_stop_observations
        validate_stop_observations(pending_checks(store.connection, original['id']), list(check_observations))
        instance = json.loads(original['execution_instance'])
        if instance['host'] != socket.gethostname() or process_alive(instance['pid']):
            raise EvolveError('EXTERNAL_EXECUTION_ACTIVE', 'The original local execution is not known to have ended; do not take over or resend', exit_code=4)
    if not pending and operation and not (value or {}).get('terminal_confirmed'):
        admitted = [json.loads(r[0]) for r in store.connection.execute(
            "SELECT payload_json FROM events WHERE run_id=? AND kind='external_dispatch_admitted'", (operation['run_id'],))]
        started = [json.loads(r[0]) for r in store.connection.execute(
            "SELECT payload_json FROM events WHERE run_id=? AND kind='external_sender_started'", (operation['run_id'],))]
        if admitted:
            sender = started[-1]['sender'] if started else admitted[-1]['sender']
        elif operation['state'] == 'prepared':
            sender = {'execution_id': operation_id + '-not-admitted', 'command_digest': digest(canonical({'argv': capsule['argv'], 'cwd': capsule['cwd']})),
                      'host': capsule['generation']['host'], 'prepared_at': capsule['created_at'], 'state': 'not_started'}
        else:
            raise EvolveError('EXTERNAL_SENDER_UNKNOWN', 'Protection is absent and the saved dispatch stage is ambiguous', exit_code=4)
        pending = {'operation_id': operation_id, **value['capsule'], 'state': 'unknown', 'resources': capsule['resources'],
                   'sender': sender, 'original_epoch': capsule['original_epoch'], 'target': capsule['candidate']['target_snapshot']}
        index['pending'].append(pending)
    return index, expected, pending, operation, capsule, {k: reference[k] for k in ('capsule_path', 'capsule_digest')}


def reconcile(root, payload, *, method='external.reconcile'):
    root, request = Path(root).resolve(), normalize(payload)
    for effect in ('project_records', 'external_read'):
        require_effect(request, effect)
    store, run_id = None, None
    try:
        with writer_lock(root, recover_dead=True) as generation:
            store = Store(root)
            previous = store.lookup(request, action='apply', method=method, owner='evolve-apply')
            if previous is not None:
                return previous[1]
            operation_id = request['input'].get('operation_id')
            index, expected, pending, operation, capsule, reference = resolve_operation(store, operation_id, request['input'].get('check_observations', []))
            require_target_grant(request, capsule['candidate']['target'])
            reported = None
            if method == 'external.record':
                from .external_actions import reported_observation
                reported = reported_observation(request, capsule)
            observations = registry.require_senders_stopped({'pending': [pending] if pending else []}, request['input'].get('sender_observations', []))
            if pending:
                pending['sender'] = {**pending['sender'], 'state': 'stopped'}
                registry.save_index(root, index, expected)
            run_id, _ = store.start(request, action='apply', method=method, owner='evolve-apply')
            with store.transaction() as db:
                if reported is not None:
                    store.event(run_id, 'external_observation_reported', {'operation_id': operation_id,
                        'reported_observation_digest': store.blob(canonical(reported)), 'claims_are_separate_from_actual_probe': True})
                if operation is None:
                    store.artifact(None, 'external_capsule', canonical(capsule), run_id, 'evolve-apply:restored-external-source')
                    value = {**operation_value(capsule, reference), 'effect_outcome': 'unknown',
                             'restored_protection_source': {'original_run_id': capsule['run_id'], 'original_epoch': capsule['original_epoch'],
                                 'source_is_protected_capsule_not_a_fabricated_old_run': True}}
                    db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,NULL)',
                        (operation_id, run_id, 'external_write', 'committed', digest(canonical(capsule['request'])), canonical(value).decode()))
                    for resource in capsule['resources']:
                        existing = store.one('SELECT operation_id FROM resource_claims WHERE resource=?', (resource,))
                        if existing and existing['operation_id'] != operation_id:
                            raise EvolveError('CLAIM', 'Restored external protection overlaps another actual owner', exit_code=4)
                        if not existing:
                            db.execute('INSERT INTO resource_claims VALUES (?,?,?,?,1)',
                                (resource, operation_id, 'held', canonical(generation).decode()))
                for item in observations:
                    store.event(run_id, 'external_sender_observed', {'operation_id': operation_id, 'observation': item, 'business_success': 'not_inferred'})
        # No write dispatch, file edits or long target queries under the writer lock.
        observation = effect_probe(root, capsule, True)
        with writer_lock(root):
            observation_gate(store, request, run_id)
            value = record_effect(store, run_id, operation_id, capsule, reference, observation)
            original = store.one('SELECT * FROM phase_runs WHERE id=?', (capsule['run_id'],))
            if original and original['status'] == 'started':
                store.finish(original['id'], {'committed': True, 'outcome': 'external_registration_reconciled',
                    'operation_id': operation_id, 'finalized_by': run_id, 'command_replayed': False,
                    'effect_outcome': value['effect_outcome'], 'business_acceptance': 'not_inferred'}, status='interrupted')
            return store.finish(run_id, {'committed': True, 'outcome': 'external_reconciled',
                'operation_id': operation_id, 'effect_outcome': value['effect_outcome'], 'effect_record': value,
                'latest_observation': observation, 'reported_observation': reported, 'command_replayed': False, 'business_acceptance': 'not_inferred'})
    finally:
        if store is not None:
            store.close()


def check_existing(root, payload, *, method='external.execute'):
    """Continue only task checks for an already confirmed operation; never dispatch."""
    root, request = Path(root).resolve(), normalize(payload)
    for effect in ('project_records', 'external_read', 'checks'):
        require_effect(request, effect)
    store = None
    try:
        with writer_lock(root, recover_dead=True) as generation:
            store = Store(root)
            previous = store.lookup(request, action='apply', method=method, owner='evolve-apply')
            if previous is not None:
                return previous[1]
            index, _, pending, operation, capsule, _ = resolve_operation(store, request['input'].get('operation_id'))
            require_target_grant(request, capsule['candidate']['target'])
            value = json.loads(operation['result_json']) if operation and operation['result_json'] else {}
            if pending or not value.get('terminal_confirmed') or value.get('effect_outcome') != 'succeeded':
                raise EvolveError('EXTERNAL_PENDING', 'Only a confirmed ended operation can continue task checks; reconcile without resend first', exit_code=4)
            from .external_work import bind, assert_check_candidate
            binding, change, revision, task, definition = bind(store, request)
            assert_check_candidate(store, binding, capsule['candidate'])
            if capsule['candidate'].get('work_binding') is None:
                raise EvolveError('EXTERNAL_TASK', 'The source operation does not belong to this work task')
            for resource in capsule['resources']:
                if store.one('SELECT operation_id FROM resource_claims WHERE resource=?', (resource,)):
                    raise EvolveError('CLAIM', 'Related work/data scope remains owned', exit_code=3)
            run_id, _ = store.start(request, action='apply', method=method, owner='evolve-apply')
            check_operation_id = identifier()
            with store.transaction() as db:
                db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,NULL)',
                    (check_operation_id, run_id, 'project_records', 'running', digest(canonical(request)), '{}'))
                for resource in capsule['resources']:
                    db.execute('INSERT INTO resource_claims VALUES (?,?,?,?,1)',
                        (resource, check_operation_id, 'task_checks', canonical(generation).decode()))
                if revision['accepted_event_id'] is None:
                    accepted = store.event(run_id, 'plan_accepted', {'revision_id': revision['id'], 'plan_digest': revision['plan_digest'],
                        'authorization': request['authorization'], 'external_dispatch': False})
                    db.execute('UPDATE plan_revisions SET accepted_event_id=? WHERE id=?', (accepted, revision['id']))
                store.event(run_id, 'external_task_checks_started', {'operation_id': capsule['operation_id'],
                    'owner_operation_id': check_operation_id, 'work_binding': binding, 'external_dispatch': False})
        from .external_work import run_task_checks
        result = run_task_checks(store, request, run_id, check_operation_id, capsule)
        fault_point('task_checks_committed')
        with writer_lock(root):
            observation_gate(store, request, run_id)
            return store.finish(run_id, {'committed': True, 'outcome': 'external_task_checks', **result,
                'operation_id': capsule['operation_id'], 'command_replayed': False, 'external_dispatch': False})
    finally:
        if store is not None:
            store.close()
