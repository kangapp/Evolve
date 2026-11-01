"""Explicit cancellation, sourced observations and separately approved compensation."""
import json
from pathlib import Path

from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store
from .workspace import writer_lock
from . import external_registry as registry


def cancel(root, payload):
    request, root = normalize(payload), Path(root).resolve()
    require_effect(request, 'project_records')
    reason = request['input'].get('reason')
    if not isinstance(reason, str) or not reason.strip():
        raise EvolveError('INPUT', 'State the actual reason to revoke future dispatch')
    with writer_lock(root, recover_dead=True):
        store = Store(root)
        try:
            previous = store.lookup(request, action='maintain', method='cancel', owner='evolve-maintain')
            if previous is not None:
                return previous[1]
            operation_id = request['input'].get('external_operation_id')
            registry.record_path(root, operation_id)
            index, _ = registry.load_index(root, store.meta)
            pending = next((r for r in index['pending'] if r['operation_id'] == operation_id), None)
            operation = store.one("SELECT * FROM operations WHERE id=? AND effect_kind='external_write'", (operation_id,))
            value = json.loads(operation['result_json']) if operation and operation['result_json'] else {}
            registry.require_recorded_reference(pending, value if operation else None)
            reference = pending or value.get('capsule')
            if not reference:
                raise EvolveError('EXTERNAL_SOURCE_UNKNOWN', 'Cancellation needs this exact recorded or protected external source')
            capsule = registry.read_capsule(root, {**reference, 'operation_id': operation_id}, store.meta['project_id'])
            run_id, _ = store.start(request, action='maintain', method='cancel', owner='evolve-maintain')
            result = {'committed': True, 'outcome': 'external_future_dispatch_revoked', 'operation_id': operation_id,
                      'reason': reason, 'physical_effects_reversed': False, 'claims_released': False,
                      'pending_effects_preserved': bool(pending), 'business_commands_run': False,
                      'limitations': ['Revocation cannot stop or reverse work already admitted at the provider; observe that original operation.']}
            with store.transaction() as db:
                store.event(run_id, 'authorization_revoked', {'request_id': capsule['request']['request_id'],
                    'operation_id': operation_id, 'reason': reason, 'source': request['authorization']})
                store.event(run_id, 'external_future_dispatch_revoked', result)
                if operation:
                    db.execute('UPDATE operations SET result_json=? WHERE id=?',
                        (canonical({**value, 'future_dispatch_revoked_by': run_id}).decode(), operation_id))
            return store.finish(run_id, result)
        finally:
            store.close()


def reported_observation(request, capsule):
    value = request['input'].get('observation')
    if (not isinstance(value, dict) or any(not isinstance(value.get(k), str) or not value[k].strip()
            for k in ('source', 'basis', 'observed_at', 'scope'))
            or value.get('scope') != capsule['candidate']['target']['scope']
            or value.get('reported_outcome') not in ('not_started', 'running', 'succeeded', 'failed', 'unknown')
            or any(not isinstance(value.get(k), list) for k in ('known_effects', 'unknown_scope', 'limitations'))):
        raise EvolveError('EXTERNAL_OBSERVATION_SOURCE', 'Supply the actual observation source/time/basis, exact scope, reported outcome, known effects, unknown scope and limitations')
    from datetime import datetime
    try:
        if datetime.fromisoformat(value['observed_at'].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('timezone required')
    except ValueError:
        raise EvolveError('EXTERNAL_OBSERVATION_SOURCE', 'Observation time must be an actual timezone-aware ISO timestamp')
    return value


def compensation_source(store, request, expected=None):
    from .external import resolve_operation, require_target_grant
    source_id = (expected or {}).get('operation_id') or request['input'].get('compensates_operation_id')
    _, _, pending, operation, capsule, _ = resolve_operation(store, source_id)
    require_target_grant(request, capsule['candidate']['target'])
    value = json.loads(operation['result_json']) if operation and operation['result_json'] else {}
    if (pending or not value.get('terminal_confirmed') or value.get('effect_outcome') not in ('succeeded', 'failed')
            or not value.get('confirmed_observation_digest')):
        raise EvolveError('EXTERNAL_COMPENSATION_UNKNOWN', 'Only confirmed ended operations with complete known effects can support compensation; reconcile without resend first')
    source = {'operation_id': source_id, 'confirmed_observation_digest': value['confirmed_observation_digest'],
              'capsule_digest': digest(canonical(capsule))}
    if expected is not None and any(expected.get(k) != source[k] for k in source):
        raise EvolveError('EXTERNAL_COMPENSATION_CHANGED', 'The exact confirmed compensation source changed')
    return source, capsule


def observe_compensation(root, original, candidate):
    from .external import effect_probe
    from .external_work import stable_goal_basis
    if candidate['target_snapshot'] != original['candidate']['target_snapshot']:
        raise EvolveError('EXTERNAL_COMPENSATION_SCOPE', 'Compensation must remain within the exact original target/object/scope')
    current = effect_probe(root, original, True)
    if not current['terminal_confirmed']:
        raise EvolveError('EXTERNAL_COMPENSATION_UNKNOWN', 'Current complete original effects cannot be established')
    return stable_goal_basis(current)


def compensate(root, payload):
    from .external import execute
    return execute(root, payload, method='external.compensate')


def record(root, payload):
    from .external import reconcile
    return reconcile(root, payload, method='external.record')
