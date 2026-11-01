"""Approved formal content applications and actual target verification, using the shared journal."""
import json
from pathlib import Path
import socket

from .continuation import sealed_result
from .errors import EvolveError
from .knowledge import baseline_path
from .knowledge_proposals import OWNER_METHODS, bound_proposal, latest_check, metadata, reference, source_facts
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .structured import text
from .work import change_context, claim_resources, fingerprint, gate, gate_identity, require_bound_targets, versions
from .workspace import current_digest, finish_journal, inside, install_files, prepare_files, process_alive, writer_lock
from .patches import dependency_gate, effect_state, resolve_effect, review_composition


def implementation_basis(store, data, path):
    basis = data.get('implementation_basis'); delivery = data.get('delivery') or {}
    associated = store.one('SELECT * FROM changes WHERE id=?', (delivery.get('change_id'),)) if delivery.get('change_id') else None
    business = associated and any(json.loads(t[0]).get('responsible_action') == 'apply' for t in store.connection.execute(
        'SELECT definition_json FROM tasks WHERE revision_id=?', (associated['current_revision'],)))
    if basis is None:
        if business and delivery.get('role') == 'followup':
            raise EvolveError('KNOWLEDGE_BASIS', 'Business-linked spec synchronization needs actual implementation verification')
        return None
    if not isinstance(basis, dict) or not isinstance(basis.get('verification_id'), str):
        raise EvolveError('KNOWLEDGE_BASIS', 'Implementation basis must identify its actual verification')
    text(basis.get('purpose'), 'implementation_basis.purpose')
    verification = store.one('SELECT * FROM verifications WHERE id=?', (basis['verification_id'],))
    change = store.one('SELECT * FROM changes WHERE id=?', (verification['change_id'],)) if verification else None
    from .work import check_basis, verification_source
    from .revisions import eligible_verifications
    if (not change or verification['status'] != 'passed' or verification['subject_kind'] != 'applied'
            or verification_source(store.connection, verification) is None
            or (associated and associated['id'] != change['id'])):
        raise EvolveError('KNOWLEDGE_BASIS', 'Spec synchronization needs finalized passing actual implementation evidence', exit_code=3)
    eligible = eligible_verifications(store.connection, change['id'], change['current_revision'])
    if verification['id'] not in {v['id'] for v in eligible}:
        raise EvolveError('KNOWLEDGE_BASIS', 'Implementation verification is not applicable to the current accepted definition', exit_code=3)
    observed = json.loads(verification['fingerprint_json']); target = json.loads(verification['items_json']).get('task_id')
    tasks = store.connection.execute('SELECT * FROM tasks WHERE ' + ('id=?' if target else 'revision_id=?'),
        (target or change['current_revision'],)).fetchall()
    paths = {p for task in tasks if json.loads(task['definition_json']).get('responsible_action') == 'apply'
             for p in json.loads(task['definition_json'])['scope']}
    if not paths or any(current_digest(inside(store.root, p)) != observed['scope'].get(p) for p in paths):
        raise EvolveError('KNOWLEDGE_BASIS', 'Actual implementation outputs changed after the cited verification', exit_code=3)
    if any(current_digest(inside(store.root, p)) != value for p, value in observed.get('context', {}).items() if p != path):
        raise EvolveError('KNOWLEDGE_BASIS', 'Declared implementation context changed', exit_code=3)
    check_basis(store.root, {'required_checks': [c['id'] for c in observed['checks']], 'checks_basis': observed['checks']})
    for newer in eligible:
        if newer['id'] == verification['id']:
            break
        if newer['status'] != 'passed' and paths & set(json.loads(newer['fingerprint_json'])['scope']):
            raise EvolveError('KNOWLEDGE_BASIS', 'A newer related required verification is not passing', exit_code=3)
    return {'verification_id': verification['id'], 'purpose': basis['purpose']}


def delivery_definition(store, data, *, owner='sync'):
    delivery = data.get('delivery')
    if delivery is None:
        return None
    if not isinstance(delivery, dict) or delivery.get('role') not in ('required', 'followup'):
        raise EvolveError('KNOWLEDGE_DELIVERY', 'Document delivery role must be required or followup')
    if delivery['role'] == 'followup':
        if set(delivery) - {'role', 'change_id'}:
            raise EvolveError('KNOWLEDGE_DELIVERY', 'Followup knowledge cannot silently satisfy task conditions')
        if delivery.get('change_id') and not store.one('SELECT id FROM changes WHERE id=?', (delivery['change_id'],)):
            raise EvolveError('KNOWLEDGE_DELIVERY', 'Followup change is not in this project')
        return delivery
    task = store.one('SELECT * FROM tasks WHERE id=?', (delivery.get('task_id'),))
    change = store.one('SELECT * FROM changes WHERE id=?', (delivery.get('change_id'),))
    definition = json.loads(task['definition_json']) if task else {}
    if (not task or not change or change['state'] in ('archived', 'cancelled')
            or task['change_id'] != change['id'] or task['revision_id'] != change['current_revision']
            or delivery.get('revision_id') != task['revision_id'] or delivery.get('definition_digest') != task['definition_digest']
            or definition.get('responsible_action') != owner or data['path'] not in definition['scope']):
        raise EvolveError('KNOWLEDGE_DELIVERY', 'Required candidate must bind an actual current task of its declared owner')
    accepted = delivery.get('acceptance_ids')
    if (not isinstance(accepted, list) or not accepted or any(not isinstance(v, str) for v in accepted)
            or len(set(accepted)) != len(accepted) or not set(accepted).issubset({a['id'] for a in definition['acceptance']})):
        raise EvolveError('KNOWLEDGE_DELIVERY', 'Required candidate must identify actual task acceptance conditions')
    return delivery


def approval_fact(store, proposal, approval_id):
    if proposal['state'] != 'approved' or proposal['approved_event_id'] != approval_id:
        raise EvolveError('KNOWLEDGE_APPROVAL', 'Use the current exact candidate approval, not a prior decision', exit_code=3)
    event = store.one("SELECT * FROM events WHERE id=? AND kind='knowledge_reviewed'", (approval_id,))
    value = json.loads(event['payload_json']) if event else {}
    facts = source_facts(store.connection, event['run_id']) if event else None
    if (value.get('proposal') != reference(proposal) or value.get('decision') != 'approved' or not facts
            or not any(item.get('decision_event_id') == approval_id and item.get('state') == 'approved'
                       and all(item.get(k) == v for k, v in reference(proposal).items()) for item in facts.get('decisions', []))):
        raise EvolveError('KNOWLEDGE_PENDING', 'Approval source is not safely finalized and bound to this candidate', exit_code=4)
    check = latest_check(store.connection, proposal)
    if not check or check['source_pending'] or check['recorded_status'] != 'passed':
        raise EvolveError('KNOWLEDGE_CHECK', 'Application requires the latest matching content check to pass', exit_code=3)
    return event, check


def application_source(connection, application):
    run = connection.execute('SELECT * FROM phase_runs WHERE id=?', (application['source_run_id'],)).fetchone()
    operation = connection.execute("SELECT * FROM operations WHERE id=? AND state='committed' AND effect_kind='knowledge'",
        (application['operation_id'],)).fetchone()
    proposal = connection.execute('SELECT owner_skill FROM knowledge_proposals WHERE id=?', (application['proposal_id'],)).fetchone()
    actor = OWNER_METHODS.get(proposal['owner_skill']) if proposal else None
    if (not run or not operation or run['status'] not in ('completed', 'interrupted')
            or not actor or (run['action'], run['method'], run['owner_skill']) != (actor[0], actor[2], proposal['owner_skill']) or operation['run_id'] != run['id']):
        return None
    _, request, result = sealed_result(connection, {'run_id': run['id'], 'result_digest': run['result_digest']})
    meta = dict(connection.execute('SELECT key,value FROM project_meta'))
    if request['project_id'] != meta['project_id'] or run['workspace_epoch'] != meta['workspace_epoch']:
        return None
    event_run = run['id']
    if run['status'] == 'interrupted':
        recovery = connection.execute("SELECT * FROM phase_runs WHERE id=? AND action='maintain' AND method='recover' AND status='completed'",
            (result.get('finalized_by'),)).fetchone()
        if not recovery:
            return None
        _, _, recovered = sealed_result(connection, {'run_id': recovery['id'], 'result_digest': recovery['result_digest']})
        if (result.get('outcome') != 'reconciled_knowledge_application' or recovered.get('original_run_id') != run['id']
                or recovered.get('application_id') != application['id'] or recovered.get('business_commands_run') is not False):
            return None
        event_run = recovery['id'] if recovered.get('facts_created') else run['id']
        result = result.get('saved_operation_result', {})
    saved = json.loads(operation['result_json'])
    if (saved.get('application_id') != application['id'] or saved.get('proposal_id') != application['proposal_id']
            or saved.get('actual_digest') != application['result_digest']
            or saved.get('artifact', {}).get('entity_id') != application['artifact_version_id']
            or any(result.get(k) != v for k, v in saved.items())):
        return None
    if not any(json.loads(e[0]).get('operation_id') == operation['id'] and json.loads(e[0]).get('result_digest') == digest(canonical(saved)) for e in connection.execute(
            "SELECT payload_json FROM events WHERE run_id=? AND kind='formal_application_committed'", (event_run,))):
        return None
    artifact = connection.execute('SELECT * FROM artifact_versions WHERE id=?', (application['artifact_version_id'],)).fetchone()
    if not artifact or artifact['blob_digest'] != application['result_digest']:
        return None
    if proposal['owner_skill'] == 'evolve-learn':
        binding = connection.execute('SELECT * FROM rule_bindings WHERE application_id=?', (application['id'],)).fetchone()
        full = connection.execute('SELECT * FROM knowledge_proposals WHERE id=?', (application['proposal_id'],)).fetchone()
        value = metadata(full)
        if (not binding or binding['proposal_id'] != full['id'] or binding['artifact_version_id'] != artifact['id']
                or json.loads(binding['sources_json']) != value['rule_sources'] or json.loads(binding['scope_json']) != value['rule_scope']):
            return None
    return saved


def document_applications(connection, root, task, *, active_run=None, pending=None):
    definition = json.loads(task['definition_json'])
    if definition.get('responsible_action') not in ('sync', 'init', 'learn'):
        return True, {}
    result = json.loads(task['result_json']) if task['result_json'] else {}
    selected = result.get('document_applications', {})
    if result.get('definition_digest') != task['definition_digest'] or set(selected) != set(definition['scope']):
        return False, selected
    covered = set()
    for path, application_id in selected.items():
        application = connection.execute('SELECT * FROM spec_applications WHERE id=?', (application_id,)).fetchone()
        proposal = connection.execute('SELECT * FROM knowledge_proposals WHERE id=?', (application['proposal_id'],)).fetchone() if application else None
        delivery = metadata(proposal).get('delivery') if proposal and metadata(proposal) else None
        if proposal:
            from .rules import require_rule_basis
            try:
                require_rule_basis(connection, proposal)
            except EvolveError:
                return False, selected
        if (not application or not delivery or delivery.get('role') != 'required'
                or delivery['change_id'] != task['change_id'] or delivery['definition_digest'] != task['definition_digest'] or proposal['target_path'] != path
                or (current_digest(baseline_path(root, path)) != application['result_digest'] if application['source_run_id'] == active_run
                    else not effect_state(connection, root, application, pending=pending)['preserved'])
                or (application['source_run_id'] != active_run and application_source(connection, application) is None)):
            return False, selected
        covered.update(delivery['acceptance_ids'])
    return covered >= {a['id'] for a in definition['acceptance'] if a['required']}, selected


def verification_applications(connection, root, change, revision, task, definition):
    from .structured import current_tasks
    peers = current_tasks(connection, change['id'], revision['id']) if definition.get('whole_change') else [task]
    result = {}
    for item in peers:
        complete, selected = document_applications(connection, root, item)
        if not complete:
            return False, result
        result.update({item['id'] + ':' + path: app for path, app in selected.items()})
    return True, result


def _context(store, request, proposal, *, pending=None):
    delivery = metadata(proposal).get('delivery')
    if not delivery or delivery['role'] != 'required':
        if request['input'].get('change_id'):
            raise EvolveError('KNOWLEDGE_DELIVERY', 'Only declared required delivery can complete a Change task')
        return None
    change, revision, task, definition = change_context(store, request, require_task=True)
    if any(delivery.get(k) != v for k, v in {'change_id': change['id'], 'revision_id': revision['id'],
            'task_id': task['id'], 'definition_digest': task['definition_digest']}.items()):
        raise EvolveError('KNOWLEDGE_DELIVERY', 'Required candidate belongs to another task or revision', exit_code=3)
    if definition.get('responsible_action') != OWNER_METHODS[proposal['owner_skill']][4] or proposal['target_path'] not in definition['scope']:
        raise EvolveError('KNOWLEDGE_OWNER', 'Only the declared document owner may produce these task outputs')
    if request['input'].get('accepted_plan_digest') != revision['plan_digest']:
        raise EvolveError('PLAN_ACCEPTANCE', 'Document application requires acceptance of the actual presented plan', exit_code=3)
    if revision['ordinal'] > 1:
        from .revisions import require_accepted
        require_accepted(store.connection, revision)
    if definition.get('structured'):
        from .structured import current_tasks, readiness
        if readiness(store.connection, store.root, task, current_tasks(store.connection, change['id'], revision['id']), pending=pending)['unmet']:
            raise EvolveError('DEPENDENCY_NOT_READY', 'Document task dependencies are not ready', exit_code=3)
    return change, revision, task, definition


def prepared_effect(store, operation_id):
    operation = store.one('SELECT run_id FROM operations WHERE id=?', (operation_id,))
    for row in store.connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind='formal_application_prepared'", (operation['run_id'],)):
        value = json.loads(row[0])
        if value['operation_id'] == operation_id:
            return value['effect']
    raise EvolveError('KNOWLEDGE_CHAIN', 'Original application effect was not safely prepared', exit_code=4)


def _commit_application(store, original_run, event_run, operation_id, proposal, check, context):
    existing = store.one('SELECT * FROM spec_applications WHERE operation_id=?', (operation_id,))
    if existing:
        return json.loads(store.one('SELECT result_json FROM operations WHERE id=?', (operation_id,))[0])
    path = baseline_path(store.root, proposal['target_path']); content = path.read_bytes()
    effect = prepared_effect(store, operation_id)
    if digest(content) != effect['result_digest']:
        raise EvolveError('FILE_CONFLICT', 'Applied formal target changed before facts were committed', exit_code=3)
    actual = store.artifact(proposal['target_path'], 'knowledge', content, event_run, proposal['owner_skill'] + ':approved-' + proposal['target_kind'])
    delta = metadata(proposal)['delta_id']; application_id = identifier()
    store.connection.execute('INSERT INTO spec_applications VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)',
        (application_id, delta, proposal['id'], proposal['version'], proposal['approved_event_id'], check['run_id'],
         effect['base_digest'], effect['result_digest'], actual['entity_id'], operation_id, original_run))
    store.connection.execute('UPDATE knowledge_proposals SET applied_operation_id=? WHERE id=?', (operation_id, proposal['id']))
    from .rules import bind_rule
    bind_rule(store, application_id, proposal, actual['entity_id'])
    if context:
        change, revision, task, definition = context
        saved = json.loads(task['result_json']) if task['result_json'] else {}
        selected = dict(saved.get('document_applications', {})) if saved.get('definition_digest') == task['definition_digest'] else {}
        selected[proposal['target_path']] = application_id
        snapshot = fingerprint(store.root, definition)
        task_result = {'definition_digest': task['definition_digest'], 'fingerprint': snapshot,
            'document_applications': selected, 'artifacts': [actual], 'check_evidence': [],
            'implementation_source': 'owner:' + OWNER_METHODS[proposal['owner_skill']][4]}
        if definition.get('structured'):
            from .structured import current_tasks, dependency_basis
            task_result['dependency_basis'] = dependency_basis(store.connection, task, current_tasks(store.connection, change['id'], revision['id']))
        store.connection.execute('UPDATE tasks SET result_json=? WHERE id=?', (canonical(task_result).decode(), task['id']))
        updated = store.one('SELECT * FROM tasks WHERE id=?', (task['id'],))
        complete, _ = document_applications(store.connection, store.root, updated, active_run=original_run)
        store.connection.execute('UPDATE tasks SET state=?,row_version=row_version+1 WHERE id=?', ('done' if complete else 'in_progress', task['id']))
        store.connection.execute("UPDATE changes SET state='active',row_version=row_version+1 WHERE id=?", (change['id'],))
        if revision['accepted_event_id'] is None:
            accepted = store.event(event_run, 'plan_accepted', {'revision_id': revision['id'], 'plan_digest': revision['plan_digest'], 'owner': OWNER_METHODS[proposal['owner_skill']][4]})
            store.connection.execute('UPDATE plan_revisions SET accepted_event_id=? WHERE id=?', (accepted, revision['id']))
        if definition.get('structured'):
            from .structured import invalidate_dependents
            invalidate_dependents(store, event_run, change['id'], revision['id'])
    result = {'application_id': application_id, 'proposal_id': proposal['id'], 'delta_id': delta, 'artifact': actual,
              'actual_digest': effect['result_digest'], 'effect': effect, 'applied': True, 'overall_verification': 'not_run'}
    if effect.get('adoption'):
        result.update(adopted_external_bytes=True, file_bytes_written=False)
    store.connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?", (canonical(result).decode(), operation_id))
    store.connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
    store.event(event_run, 'formal_application_committed', {'operation_id': operation_id, 'result_digest': digest(canonical(result))})
    return result


def apply_knowledge(root, payload, *, owner='evolve-archive'):
    root = Path(root).resolve(); request = normalize(payload)
    require_effect(request, 'project_records'); require_effect(request, 'knowledge')
    store, run_id, operation_id = None, None, identifier()
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            actor = OWNER_METHODS[owner]
            run_id, previous = store.start(request, action=actor[0], method=actor[2], owner=owner)
            if previous is not None:
                return previous
            proposal = bound_proposal(store, request['input'].get('proposal'))
            if proposal['owner_skill'] != owner:
                raise EvolveError('KNOWLEDGE_OWNER', 'Only the declared owner may apply this exact proposal')
            existing = store.one('SELECT * FROM spec_applications WHERE proposal_id=?', (proposal['id'],))
            if existing:
                if application_source(store.connection, existing) is None:
                    raise EvolveError('KNOWLEDGE_PENDING', 'Prior application needs safe finalization', exit_code=4)
                return store.finish(run_id, {'committed': True, 'outcome': 'already_applied', 'application_id': existing['id'],
                    'applied': True, 'current_matches': current_digest(baseline_path(root, proposal['target_path'])) == existing['result_digest']})
            if source_facts(store.connection, proposal['created_run_id']) is None:
                raise EvolveError('KNOWLEDGE_PENDING', 'Candidate needs safe finalization', exit_code=4)
            approval, check = approval_fact(store, proposal, request['input'].get('approved_event_id'))
            if proposal['target_path'] not in request['authorization'].get('paths', []):
                raise EvolveError('AUTHORIZATION', 'Formal target is outside explicit knowledge authorization')
            context = _context(store, request, proposal)
            implementation_basis(store, metadata(proposal), proposal['target_path'])
            from .rules import require_rule_basis
            require_rule_basis(store.connection, proposal)
            path = baseline_path(root, proposal['target_path'])
            effect = resolve_effect(store.connection, root, proposal)
            review_composition(effect, request['input'].get('composition_review'))
            effect['composition_review'] = request['input'].get('composition_review')
            if current_digest(path) != effect['base_digest']:
                raise EvolveError('FILE_CONFLICT', 'Approved formal baseline changed; do not overwrite the current meaning', exit_code=3)
            dependency_gate(store.connection, root, proposal)
            if context:
                # Reject a candidate that breaks its own upstream meaning before
                # claiming resources or preparing a recoverable file operation.
                _context(store, request, proposal, pending={**effect, 'target_path': proposal['target_path']})
            paths = context[3]['scope'] if context else [proposal['target_path']]
            claim_resources(store, run_id, operation_id, generation, context[0] if context else None, paths, 'knowledge')
            def application_gate():
                if context:
                    gate(store, request, run_id, operation_id, request['expected_versions'])
                else:
                    gate_identity(store, request, run_id); require_bound_targets(store, operation_id, paths)
                approval_fact(store, store.one('SELECT * FROM knowledge_proposals WHERE id=?', (proposal['id'],)), approval['id'])
                implementation_basis(store, metadata(proposal), proposal['target_path'])
                require_rule_basis(store.connection, proposal)
                current = resolve_effect(store.connection, root, proposal)
                if any(current[k] != effect[k] for k in current) or current_digest(path) not in (effect['base_digest'], effect['result_digest']):
                    raise EvolveError('KNOWLEDGE_CHAIN', 'Prepared approved effect or actual target changed during application', exit_code=3)
                dependency_gate(store.connection, root, proposal, physical={proposal['target_path']: effect['base_digest']})
            application_gate()
            with store.transaction():
                store.blob(effect['content'].encode())
                store.event(run_id, 'formal_application_prepared', {'operation_id': operation_id, 'effect': effect})
                if effect['chain']:
                    blob = store.blob(canonical(effect['composition_review']))
                    store.connection.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)', (identifier(), run_id, None, 'candidate',
                        effect['composition_review']['observer'], 'approved-patch-composition', blob, now(), 'Named content observation on exact composed text; no new approval inferred.'))
            journal = prepare_files(root, operation_id, [{'path': proposal['target_path'], 'expected_digest': effect['base_digest'], 'content': effect['content']}])
            with store.transaction() as connection:
                connection.execute('UPDATE operations SET journal_path=? WHERE id=?', ('.evolve-local/control/operations/' + operation_id + '.json', operation_id))
            install_files(root, journal, before_write=application_gate)
            application_gate()
            with store.transaction():
                result = _commit_application(store, run_id, run_id, operation_id, proposal, check, context)
            finish_journal(root, journal)
            return store.finish(run_id, {'committed': True, 'outcome': 'knowledge_applied', 'operation_id': operation_id, **result})
    except (EvolveError, OSError) as error:
        if store is not None and run_id is not None and store.run_started(run_id):
            with writer_lock(root):
                pending = inside(root, '.evolve-local/control/operations/' + operation_id + '.json').exists()
                with store.transaction() as connection:
                    connection.execute("UPDATE operations SET state=? WHERE id=? AND state!='committed'", ('needs_recovery' if pending else 'failed', operation_id))
                    if not pending:
                        connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    store.event(run_id, 'knowledge_application_interrupted', {'writer_stopped': True, 'message': str(error)})
                if not pending:
                    store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
        if isinstance(error, EvolveError):
            error.committed = store is not None and run_id is not None
            raise
        raise EvolveError('NEEDS_RECOVERY', 'Formal application requires observation before retry', exit_code=4, committed=run_id is not None)
    finally:
        if store is not None:
            store.close()


def verify_knowledge(root, payload):
    root = Path(root).resolve(); request = normalize(payload); require_effect(request, 'project_records')
    store, run_id, operation_id = None, None, identifier()
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            run_id, previous = store.start(request, action='verify', method='knowledge', owner='evolve-verify')
            if previous is not None:
                return previous
            app = store.one('SELECT * FROM spec_applications WHERE id=?', (request['input'].get('application_id'),))
            if not app or application_source(store.connection, app) is None:
                raise EvolveError('KNOWLEDGE_PENDING', 'Verify a safely finalized actual application, not a candidate', exit_code=4)
            proposal = store.one('SELECT * FROM knowledge_proposals WHERE id=?', (app['proposal_id'],))
            path = baseline_path(root, proposal['target_path']); content = path.read_bytes() if path.is_file() else None
            actual = digest(content) if content is not None else None
            observations = request['input'].get('observations'); criteria = metadata(proposal)['acceptance']
            if (not isinstance(observations, list) or any(not isinstance(o, dict) for o in observations)
                    or len(observations) != len(criteria) or any(not isinstance(o.get('criterion_key'), str) for o in observations)
                    or {o['criterion_key'] for o in observations} != {c['key'] for c in criteria}):
                raise EvolveError('KNOWLEDGE_CHECK', 'Observe every declared condition on the actual formal target')
            for observation in observations:
                if observation.get('status') not in ('passed', 'failed', 'blocked'):
                    raise EvolveError('KNOWLEDGE_CHECK', 'Actual target observations need explicit status')
                for field in ('observer', 'basis'):
                    text(observation.get(field), 'observation.' + field)
            check = latest_check(store.connection, proposal)
            state = effect_state(store.connection, root, app)
            changed = not state['preserved']
            basis_error = None
            try:
                implementation_basis(store, metadata(proposal), proposal['target_path'])
                from .rules import require_rule_basis
                require_rule_basis(store.connection, proposal)
            except EvolveError as error:
                basis_error = {'code': error.code, 'message': str(error)}
            status = ('blocked' if changed or basis_error or any(o['status'] == 'blocked' for o in observations)
                      else 'failed' if any(o['status'] == 'failed' for o in observations) else 'passed')
            verification_id = identifier(); observed_at = now()
            snapshot = {'path': proposal['target_path'], 'actual_digest': actual, 'artifact_version_id': app['artifact_version_id']}
            items = {'application_id': app['id'], 'observations': observations, 'current_matches_application': actual == app['result_digest'],
                'approved_effect_state': state,
                'implementation_basis_error': basis_error,
                'candidate_check': check, 'equivalent_candidate_check': bool(actual == proposal['candidate_digest'] and check and not check['source_pending'] and check['recorded_status'] == 'passed'),
                'limitations': 'Actual target bytes and named content observations; no code test or exhaustive semantic guarantee inferred.'}
            claim_resources(store, run_id, operation_id, generation, None, [proposal['target_path']], 'project_records')
            gate_identity(store, request, run_id)
            if current_digest(path) != actual:
                raise EvolveError('WORKSPACE_CHANGED', 'Formal target changed during actual content observation', exit_code=3)
            with store.transaction() as connection:
                snapshot['observed_blob_digest'] = store.blob(content) if content is not None else None
                connection.execute('INSERT INTO verifications VALUES (?,NULL,NULL,?,?,?,?,?,?)',
                    (verification_id, run_id, 'applied', status, canonical(snapshot).decode(), canonical(items).decode(), observed_at))
                blob = store.blob(canonical({**snapshot, **items, 'observed_at': observed_at}))
                connection.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)',
                    (identifier(), run_id, verification_id, 'applied', ', '.join(o['observer'] for o in observations), 'actual-formal-content', blob, observed_at, items['limitations']))
                connection.execute('UPDATE spec_applications SET verification_id=? WHERE id=?', (verification_id, app['id']))
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?", (canonical({'verification_id': verification_id, 'status': status}).decode(), operation_id))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'verification_observed', {'verification_id': verification_id, 'status': status, 'application_id': app['id']})
            return store.finish(run_id, {'committed': True, 'outcome': 'knowledge_verified', 'verification_id': verification_id, 'application_id': app['id'], 'subject_kind': 'applied', 'status': status})
    except EvolveError as error:
        if store is not None and run_id is not None and store.run_started(run_id):
            with store.transaction() as connection:
                connection.execute("UPDATE operations SET state='failed' WHERE id=? AND state!='committed'", (operation_id,))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
            store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
        error.committed = run_id is not None
        raise
    finally:
        if store is not None:
            store.close()


def recover_application(store, request, original, operation):
    """Called under the recovery writer lock; never repeat checks or unknown file effects."""
    from .recover import protect_recovery, seal_unexecuted
    execution = json.loads(original['execution_instance'])
    stopped = any(json.loads(e[0]).get('writer_stopped') for e in store.connection.execute(
        "SELECT payload_json FROM events WHERE run_id=? AND kind='knowledge_application_interrupted'", (original['id'],)))
    if execution['host'] != socket.gethostname() or (process_alive(execution['pid']) and not stopped):
        raise EvolveError('WRITER_ACTIVE', 'Formal writer is not known to have stopped', exit_code=3)
    source = json.loads(original['input_json'])['request']; source['request_id'] = original['request_id']
    proposal = bound_proposal(store, source['input'].get('proposal'))
    journal_path = inside(store.root, '.evolve-local/control/operations/' + operation['id'] + '.json')
    if not journal_path.exists() and operation['journal_path'] is None:
        return seal_unexecuted(store, request, original, operation)
    if not journal_path.is_file() or operation['journal_path'] not in (None, journal_path.relative_to(store.root).as_posix()):
        raise EvolveError('JOURNAL_INVALID', 'Recover only the original formal operation journal', exit_code=4)
    journal = json.loads(journal_path.read_text()); effect = prepared_effect(store, operation['id'])
    expected = resolve_effect(store.connection, store.root, proposal, target_version=effect['formal_version_id'])
    if any(expected[k] != effect[k] for k in expected):
        raise EvolveError('KNOWLEDGE_CHAIN', 'Original prepared composition no longer has its exact recorded proof', exit_code=4)
    review_composition(effect, effect.get('composition_review'))
    content = effect['content']
    import base64
    files = journal.get('files', [])
    if (journal.get('operation_id') != operation['id'] or len(files) != 1 or files[0]['path'] != proposal['target_path']
            or files[0]['expected_digest'] != effect['base_digest'] or files[0]['candidate_digest'] != effect['result_digest']
            or base64.b64decode(files[0]['candidate_b64'], validate=True) != content.encode()):
        raise EvolveError('JOURNAL_INVALID', 'Formal journal differs from the original exact approved candidate', exit_code=4)
    existing = store.one('SELECT * FROM spec_applications WHERE operation_id=?', (operation['id'],))
    approval, check = approval_fact(store, proposal, source['input'].get('approved_event_id'))
    if current_digest(baseline_path(store.root, proposal['target_path'])) != effect['result_digest']:
        implementation_basis(store, metadata(proposal), proposal['target_path'])
        from .rules import require_rule_basis
        require_rule_basis(store.connection, proposal)
    context = None if existing else _context(store, source, proposal, pending={**effect, 'target_path': proposal['target_path']})
    paths = context[3]['scope'] if context else [proposal['target_path']]
    # Completed task facts can have changed the recorded version map; their original file binding is still required.
    if existing:
        from .work import recorded_targets
        paths = list(recorded_targets(store, operation['id']))
    require_bound_targets(store, operation['id'], paths)
    protection = protect_recovery(store, operation, journal, identifier())
    run_id, previous = store.start(request, action='maintain', method='recover', owner='evolve-maintain')
    if previous is not None:
        return previous
    actual = current_digest(baseline_path(store.root, proposal['target_path']))
    allowed = (effect['result_digest'],) if existing else (effect['base_digest'], effect['result_digest'])
    if actual not in allowed:
        return store.finish(run_id, {'committed': True, 'outcome': 'needs_recovery', 'conflicts': [proposal['target_path']],
            'protection': protection, 'business_commands_run': False}, status='blocked')
    def recovery_gate():
        gate_identity(store, request, run_id); require_bound_targets(store, operation['id'], paths)
        if context:
            from .cross_dependencies import guard
            guard(store.connection, store.root, original['id'], context[0]['id'], source['input'])
        for event in store.connection.execute("SELECT payload_json FROM events WHERE kind='authorization_revoked'"):
            if json.loads(event[0]).get('request_id') == original['request_id']:
                raise EvolveError('AUTHORIZATION', 'Original formal write authorization was revoked', exit_code=3)
        approval_fact(store, store.one('SELECT * FROM knowledge_proposals WHERE id=?', (proposal['id'],)), approval['id'])
        implementation_basis(store, metadata(proposal), proposal['target_path'])
        from .rules import require_rule_basis
        require_rule_basis(store.connection, proposal)
        dependency_gate(store.connection, store.root, proposal)
    gate_identity(store, request, run_id)
    install_files(store.root, journal, before_write=recovery_gate)
    gate_identity(store, request, run_id)
    with store.transaction():
        result = _commit_application(store, original['id'], run_id, operation['id'], proposal, check, context)
    finish_journal(store.root, journal)
    store.finish(original['id'], {'committed': True, 'outcome': 'reconciled_knowledge_application',
        'saved_operation_result': result, 'finalized_by': run_id}, status='interrupted')
    return store.finish(run_id, {'committed': True, 'outcome': 'recovered_knowledge', 'original_run_id': original['id'],
        'application_id': result['application_id'], 'facts_created': existing is None, 'protection': protection, 'business_commands_run': False})
