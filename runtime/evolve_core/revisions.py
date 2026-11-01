"""Revision comparison and explicit, evidence-backed inheritance within one Change."""
import json
from pathlib import Path
import re
import tomllib

from .continuation import retained_source, sealed_result
from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .workspace import current_digest, inside, writer_lock


def task_semantics(definition):
    value = {key: item for key, item in definition.items() if key not in ('baseline', 'task_code', 'title')}
    for key in ('scope', 'required_deliverables', 'required_checks', 'preservation_checks', 'preservation_inputs', 'exclusions'):
        if key in value:
            value[key] = sorted(value[key])
    for key in ('acceptance', 'dependencies', 'external_dependencies', 'test_decisions'):
        if key in value:
            value[key] = sorted(value[key], key=lambda item: canonical(item))
    return value


def revision_source(connection, run_id):
    row = connection.execute('SELECT * FROM phase_runs WHERE id=?', (run_id,)).fetchone()
    if not row or row['action'] != 'update' or row['method'] != 'revise' or row['status'] == 'started':
        return None
    _, request, result = sealed_result(connection, {'run_id': row['id'], 'result_digest': row['result_digest']})
    if not retained_source(connection, row, request):
        return None
    operation = connection.execute("SELECT result_json FROM operations WHERE run_id=? AND state='committed' AND effect_kind='project_records'", (run_id,)).fetchone()
    if operation is None:
        return None
    revision_id = json.loads(operation['result_json']).get('revision_id')
    if not any(json.loads(event[0]).get('revision_id') == revision_id for event in connection.execute(
            "SELECT payload_json FROM events WHERE run_id=? AND kind='revision_committed'", (run_id,))):
        return None
    if row['status'] == 'interrupted':
        recovery = connection.execute("SELECT * FROM phase_runs WHERE id=? AND action='maintain' AND method='recover' AND status='completed'",
            (result.get('finalized_by'),)).fetchone()
        if not recovery:
            return None
        _, _, facts = sealed_result(connection, {'run_id': recovery['id'], 'result_digest': recovery['result_digest']})
        if (result.get('outcome') != 'reconciled_committed_metadata' or not facts.get('original_facts_committed')
                or facts.get('original_run_id') != row['id']):
            return None
    return row


def presentation(connection, revision_id):
    for row in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='revision_presented' ORDER BY rowid DESC"):
        value = json.loads(row['payload_json'])
        if value['revision_id'] == revision_id:
            return row, value
    return None, None


def require_ready(connection, revision):
    row, value = presentation(connection, revision['id'])
    if row and revision_source(connection, row['run_id']) is None:
        raise EvolveError('REVISION_PENDING', 'Revision facts need safe finalization or metadata recovery', exit_code=4)
    return value


def require_accepted(connection, revision):
    value = require_ready(connection, revision)
    if value and value['requires_acceptance'] and revision['accepted_event_id'] is None:
        raise EvolveError('PLAN_ACCEPTANCE', 'Accept the concrete changed revision before implementation or acceptance', exit_code=3)


def origin_tasks(connection, task):
    result, seen = [dict(task)], {task['id']}
    current = task
    while True:
        found = None
        for row in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='task_definition_reused' ORDER BY rowid DESC"):
            value = json.loads(row['payload_json'])
            if value['task_id'] == current['id']:
                found = row, value
                break
        if found is None or revision_source(connection, found[0]['run_id']) is None:
            return result
        value = found[1]
        old = connection.execute('SELECT * FROM tasks WHERE id=?', (value['from_task_id'],)).fetchone()
        if (not old or old['id'] in seen or old['change_id'] != task['change_id']
                or old['definition_digest'] != current['definition_digest']
                or task_semantics(json.loads(old['definition_json'])) != task_semantics(json.loads(current['definition_json']))
                or value['definition_digest'] != current['definition_digest']):
            raise EvolveError('REVISION_SOURCE', 'Task inheritance does not prove the same definition')
        result.append(dict(old)); seen.add(old['id']); current = old


def compatible_revisions(connection, revision_id):
    result, current = {revision_id}, revision_id
    while True:
        row, value = presentation(connection, current)
        if not row or not value['semantic_same'] or revision_source(connection, row['run_id']) is None:
            return result
        previous = value['from_revision_id']
        if previous in result:
            raise EvolveError('REVISION_SOURCE', 'Revision inheritance contains a cycle')
        a = connection.execute('SELECT change_id,definition_digest FROM plan_revisions WHERE id=?', (current,)).fetchone()
        b = connection.execute('SELECT change_id,definition_digest FROM plan_revisions WHERE id=?', (previous,)).fetchone()
        if not b or a['change_id'] != b['change_id'] or a['definition_digest'] != b['definition_digest']:
            raise EvolveError('REVISION_SOURCE', 'Whole-change inheritance changed its definition')
        result.add(previous); current = previous


def eligible_verifications(connection, change_id, revision_id, task=None):
    from .structured import current_tasks
    tasks = [task] if task is not None else current_tasks(connection, change_id, revision_id)
    task_ids = {old['id'] for current in tasks for old in origin_tasks(connection, current)}
    revisions = compatible_revisions(connection, revision_id)
    rows = []
    for row in connection.execute('SELECT * FROM verifications WHERE change_id=? ORDER BY observed_at DESC,id DESC', (change_id,)):
        target = json.loads(row['items_json']).get('task_id')
        if (target is None and task is None and row['revision_id'] in revisions) or target in task_ids:
            rows.append(row)
    return rows


def _spec_contract(spec):
    return {key: sorted(spec.get(key, [])) for key in ('goals', 'non_goals', 'behavior', 'constraints', 'tradeoffs')}


def _view(document, planned, acceptance, checks):
    spec = {key: value for key, value in document.get('spec', {}).items() if key != 'problem'}
    spec.update(_spec_contract(spec))
    return {'spec': spec, 'completion': document['completion'], 'scope': sorted(document['scope']),
            'acceptance': sorted(acceptance, key=lambda a: a['id']), 'checks_basis': sorted(checks, key=lambda c: c['id']),
            'tasks': {key: item['digest'] for key, item in planned.items()}}


def _old_document(connection, change, revision, tasks):
    body = connection.execute('SELECT content FROM blobs WHERE digest=?', (revision['plan_digest'],)).fetchone()[0].decode()
    if change['complexity'] == 'complex':
        return json.loads(body)
    definition = json.loads(tasks[0]['definition_json'])
    return {'title': change['title'], 'plan': body, 'completion': definition['completion'],
            'scope': definition['scope'], 'acceptance': [a['text'] for a in definition['acceptance']],
            'required_checks': definition['required_checks'], 'responsible_action': definition['responsible_action'],
            **{k: definition[k] for k in ('execution_kind', 'external_target', 'knowledge_impact') if k in definition}}


def _acceptance_preview(data, old):
    if data.get('complexity', 'simple') == 'complex':
        known = {a.get('key'): a for a in old if a.get('key') is not None}
        available = [a for a in old if a.get('key') is None]
        result = []
        for item in data['acceptance']:
            found = known.get(item['key']) or next((a for a in available if a['text'] == item['text']), None)
            if found in available: available.remove(found)
            result.append({'key': item['key'], 'id': found['id'] if found else 'NEW:' + item['key'],
                'text': item['text'], 'required': True})
        return result
    available = list(old)
    result = []
    for index, text in enumerate(data['acceptance']):
        found = next((a for a in available if a['text'] == text), None)
        if found:
            available.remove(found)
        result.append({'id': found['id'] if found else 'NEW:' + str(index), 'text': text, 'required': True})
    return result


def _planned(root, connection, data, order, configured, acceptance, old_tasks, old_doc, impact):
    from .plans import task_path
    from .structured import definitions
    old = {json.loads(t['definition_json'])['local_key']: t for t in old_tasks}
    if data.get('complexity', 'simple') == 'complex':
        change_id = old_tasks[0]['change_id']
        planned = definitions(root, data, order, configured, acceptance, connection=connection, change_id=change_id)
    else:
        definition = {'local_key': 'TASK-001', 'title': data['title'], 'completion': data['completion'],
            'scope': data['scope'], 'baseline': {name: current_digest(task_path(root, name, data.get('responsible_action', 'apply'))) for name in data['scope']},
            'acceptance': acceptance, 'required_checks': data['required_checks'],
            'checks_basis': [c for c in configured if c['id'] in data['required_checks']],
            'responsible_action': data.get('responsible_action', 'apply'), 'required_deliverables': data['scope'],
            'spec_delta': 'owner_candidate_required' if data.get('responsible_action', 'apply') != 'apply' else 'none'}
        from .external_work import definition_fields
        definition.update(definition_fields(root, data))
        from .knowledge_impact import freeze as freeze_knowledge_impact
        knowledge_impact = freeze_knowledge_impact(connection, root, data, data['scope'])
        if knowledge_impact is not None:
            definition['knowledge_impact'] = knowledge_impact
        previous = json.loads(old['TASK-001']['definition_json']) if 'TASK-001' in old else {}
        if 'analysis_basis' not in data:
            for key in ('analysis_basis', 'symptom_before'):
                if key in previous: definition[key] = previous[key]
        elif data['analysis_basis'] is not None:
            from .analysis import repair_basis
            _, adopted = repair_basis(connection, data['analysis_basis'], definition['checks_basis'], root=root)
            definition['analysis_basis'] = data['analysis_basis']
            if adopted['analysis'].get('symptom') is not None: definition['symptom_before'] = adopted['analysis']['symptom']
        planned = {'TASK-001': {'definition': definition}}
    spec_changed = _spec_contract(old_doc.get('spec', {})) != _spec_contract(data.get('spec', {}))
    affected = set(impact['affected_tasks']) if impact is not None else set(planned)
    for key, item in planned.items():
        definition = item['definition']
        previous = json.loads(old[key]['definition_json']) if key in old else None
        if previous and 'knowledge_impact' in previous and 'knowledge_impact' in definition:
            without_versions = lambda values: [{k: v for k, v in item.items() if k != 'baseline_version_id'} for item in values]
            if without_versions(previous['knowledge_impact']) == without_versions(definition['knowledge_impact']):
                definition['knowledge_impact'] = previous['knowledge_impact']
        if previous and 'spec_basis' in previous: definition['spec_basis'] = previous['spec_basis']
        if spec_changed and key in affected:
            definition['spec_basis'] = digest(canonical(_spec_contract(data.get('spec', {}))))
        for dependency in definition.get('dependencies', []):
            dependency['required_definition_digest'] = planned[dependency['upstream_task']]['digest']
        same = previous is not None and task_semantics(previous) == task_semantics(definition)
        item['digest'] = old[key]['definition_digest'] if same else digest(canonical(task_semantics(definition)))
        item['same_definition'] = same
        if previous:
            saved = json.loads(old[key]['result_json']) if old[key]['result_json'] else None
            baseline = saved['fingerprint']['scope'] if saved else previous['baseline']
            definition['baseline'].update({name: baseline[name] for name in definition['scope'] if name in baseline})
    return planned


def _code(store, change_id, old_task):
    if old_task:
        definition = json.loads(old_task['definition_json'])
        return definition.get('task_code', definition['local_key'])
    prefix = 'TASK:' + change_id
    maximum = 0
    for row in store.connection.execute('SELECT definition_json FROM tasks WHERE change_id=?', (change_id,)):
        definition = json.loads(row[0]); code = definition.get('task_code', definition['local_key'])
        if re.fullmatch(r'TASK-\d+', code): maximum = max(maximum, int(code[5:]))
    store.connection.execute('INSERT INTO counters VALUES (?,?) ON CONFLICT(prefix) DO UPDATE SET value=max(value,excluded.value)', (prefix, maximum))
    return 'TASK-' + store.number(prefix).rsplit('-', 1)[1]


def revise(root, payload):
    from .plans import validate_plan
    from .structured import current_tasks, document, readiness, text, validate
    from .work import change_context, claim_resources, gate_identity
    root = Path(root).resolve(); request = normalize(payload); require_effect(request, 'project_records')
    data = request['input']; proposal = data.get('proposal')
    if not isinstance(proposal, dict): raise EvolveError('INPUT', 'Revision requires its complete presented proposal')
    text(data.get('reason'), 'revision reason')
    complex_work = proposal.get('complexity', 'simple') == 'complex'
    operation_id, run_id, store = identifier(), None, None
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            run_id, previous = store.start(request, action='update', method='revise', owner='evolve-propose')
            if previous is not None: return previous
            if complex_work:
                order, configured = validate(root, proposal); new_doc = document(proposal)
            else:
                validate_plan(root, proposal)
                configured = tomllib.loads(inside(root, 'evolve/config.toml').read_text()).get('verification', {}).get('checks', [])
                if not set(proposal['required_checks']).issubset({c['id'] for c in configured}): raise EvolveError('CHECK_CONFIG', 'Revision requires registered checks')
                order = ['TASK-001']; new_doc = {k: proposal[k] for k in ('title', 'plan', 'completion', 'scope', 'acceptance', 'required_checks')}
                new_doc['responsible_action'] = proposal.get('responsible_action', 'apply')
                if 'knowledge_impact' in proposal:
                    new_doc['knowledge_impact'] = proposal['knowledge_impact']
                from .external_work import definition_fields
                new_doc.update(definition_fields(root, proposal))
            impact = data.get('impact')
            if impact is not None:
                if (not isinstance(impact, dict) or not isinstance(impact.get('affected_tasks'), list)
                        or any(k not in order for k in impact['affected_tasks']) or len(set(impact['affected_tasks'])) != len(impact['affected_tasks'])):
                    raise EvolveError('INPUT', 'Spec impact must name distinct actual tasks')
                text(impact.get('basis'), 'spec impact basis')
            change, revision, _, _ = change_context(store, request)
            if data.get('task_id') is not None: raise EvolveError('WHOLE_CHANGE_REQUIRED', 'Revision changes the whole presented plan')
            require_ready(store.connection, revision)
            for row in store.connection.execute("SELECT id,input_json FROM phase_runs WHERE status='started' AND action IN ('apply','verify','archive','update') AND id!=?", (run_id,)):
                if json.loads(row['input_json'])['request']['input'].get('change_id') == change['id']:
                    raise EvolveError('RUN_ACTIVE', 'Safely end or recover relevant work before revising', exit_code=3)
            old_tasks = current_tasks(store.connection, change['id'], revision['id'])
            old_doc = _old_document(store.connection, change, revision, old_tasks)
            old_acceptance = json.loads(revision['acceptance_json'])
            preview = _acceptance_preview(proposal, old_acceptance)
            planned = _planned(root, store.connection, proposal, order, configured, preview, old_tasks, old_doc, impact)
            old_map = {json.loads(t['definition_json'])['local_key']: t for t in old_tasks}
            new_ids = {a['id'] for a in preview}
            removed = {'scope': sorted(set(old_doc['scope']) - set(new_doc['scope'])),
                       'acceptance': [a for a in old_acceptance if a['id'] not in new_ids]}
            rewritten = [{'before': old, 'after': new} for old in old_acceptance for new in preview if old['id'] == new['id'] and old['text'] != new['text']]
            removed_spec = {key: [value for value in values if value not in new_doc.get('spec', {}).get(key, [])]
                            for key, values in _spec_contract(old_doc.get('spec', {})).items() if isinstance(values, list)}
            removed_spec = {key: value for key, value in removed_spec.items() if value}
            resolved = {'scope': {name: current_digest(inside(root, name)) for name in sorted(set(proposal['scope']) | set(old_doc['scope']))},
                'contexts': {key: item['definition'].get('context', {}) for key, item in planned.items()},
                'checks': [c for c in configured if c['id'] in set(proposal['required_checks']) | {k for item in planned.values() for k in item['definition']['required_checks']}]}
            retained_analysis = {digest(canonical(item['definition']['analysis_basis'])) for item in planned.values() if item['definition'].get('analysis_basis')}
            removed_analysis = [json.loads(task['definition_json'])['analysis_basis'] for task in old_tasks
                if json.loads(task['definition_json']).get('analysis_basis')
                and digest(canonical(json.loads(task['definition_json'])['analysis_basis'])) not in retained_analysis]
            candidate = {'removed_analysis': removed_analysis, 'from_revision_id': revision['id'], 'document': new_doc, 'removed': removed,
                'rewritten_acceptance': rewritten, 'removed_spec': removed_spec, 'impact': impact, 'resolved_basis': resolved,
                'tasks': {key: 'same_definition' if item['same_definition'] else 'changed_or_new' for key, item in planned.items()},
                'removed_tasks': sorted(set(old_map) - set(planned)),
                'task_definition_digests': {key: item['digest'] for key, item in planned.items()}}
            old_required = [item for row in old_tasks for item in json.loads(row['definition_json']).get('knowledge_impact', []) if item['disposition'] == 'required']
            new_required = [item for item in planned.values() for item in item['definition'].get('knowledge_impact', []) if item['disposition'] == 'required']
            removed_knowledge = [item for item in old_required if not any(other['topic'] == item['topic'] and other.get('target_path') == item.get('target_path') for other in new_required)]
            if old_required or new_required:
                candidate['removed_knowledge'] = removed_knowledge
            candidate_digest = digest(canonical(candidate))
            approval = data.get('approval')
            row, existing_presentation = presentation(store.connection, revision['id'])
            same_document = new_doc == old_doc and set(planned) == set(old_map) and all(item['same_definition'] for item in planned.values())
            if same_document and existing_presentation:
                saved_candidate = existing_presentation['candidate']
                if saved_candidate['resolved_basis'] == resolved:
                    candidate = saved_candidate; candidate_digest = digest(canonical(candidate))
            if approval is not None:
                if not isinstance(approval, dict) or approval.get('candidate_digest') != candidate_digest:
                    raise EvolveError('REVISION_APPROVAL', 'Approval does not bind the current concrete revision candidate')
                text(approval.get('source'), 'approval source'); text(approval.get('text'), 'approval text')
            claim_resources(store, run_id, operation_id, generation, change, [], 'project_records')
            gate_identity(store, request, run_id)
            needs_scope_approval = bool(removed['scope'] or removed['acceptance'] or rewritten or removed_spec or removed_analysis or removed_knowledge)
            if needs_scope_approval and approval is None and not same_document:
                with store.transaction() as connection:
                    store.artifact(None, 'revision_candidate', canonical(candidate), run_id, proposal['presentation']['source'])
                    connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?", (canonical({'revision_id': revision['id']}).decode(), operation_id))
                    connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    store.event(run_id, 'revision_committed', {'revision_id': revision['id'], 'outcome': 'scope_confirmation_required'})
                return store.finish(run_id, {'committed': True, 'outcome': 'scope_confirmation_required', 'operation_id': operation_id,
                    'change_id': change['id'], 'revision_id': revision['id'], 'candidate': candidate, 'candidate_digest': candidate_digest})
            if same_document:
                with store.transaction() as connection:
                    if approval is not None and revision['accepted_event_id'] is None:
                        accepted = store.event(run_id, 'plan_accepted', {'revision_id': revision['id'], 'plan_digest': revision['plan_digest'], 'approval': approval})
                        connection.execute('UPDATE plan_revisions SET accepted_event_id=? WHERE id=?', (accepted, revision['id']))
                        connection.execute('UPDATE changes SET row_version=row_version+1 WHERE id=?', (change['id'],))
                    store.artifact(None, 'revision_candidate', canonical(candidate), run_id, proposal['presentation']['source'])
                    connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?", (canonical({'revision_id': revision['id']}).decode(), operation_id))
                    connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    store.event(run_id, 'revision_committed', {'revision_id': revision['id'], 'outcome': 'accepted' if approval else 'unchanged'})
                return store.finish(run_id, {'committed': True, 'outcome': 'accepted' if approval else 'unchanged', 'operation_id': operation_id,
                    'change_id': change['id'], 'revision_id': revision['id'], 'plan_digest': revision['plan_digest'],
                    'candidate': candidate, 'candidate_digest': candidate_digest, 'accepted': bool(approval or revision['accepted_event_id'])})
            old_planned = {key: {'digest': value['definition_digest']} for key, value in old_map.items()}
            new_checks = [c for c in configured if c['id'] in proposal['required_checks']]
            semantic_same = _view(old_doc, old_planned, old_acceptance, json.loads(revision['checks_json'])) == _view(new_doc, planned, preview, new_checks)
            result_tasks = []
            with store.transaction() as connection:
                acceptance = [{**a, 'id': store.number('AC') if a['id'].startswith('NEW:') else a['id']} for a in preview]
                planned = _planned(root, connection, proposal, order, configured, acceptance, old_tasks, old_doc, impact)
                new_revision = identifier(); plan_digest = store.blob(canonical(new_doc) if complex_work else proposal['plan'].encode())
                definition_digest = revision['definition_digest'] if semantic_same else (digest(canonical(_view(new_doc, planned, acceptance, new_checks)))
                    if complex_work else planned['TASK-001']['digest'])
                connection.execute('INSERT INTO plan_revisions VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (new_revision, change['id'], revision['ordinal']+1, plan_digest, definition_digest, canonical(proposal['scope']).decode(),
                     canonical(acceptance).decode(), canonical(new_checks).decode(), now(), None))
                for key, item in planned.items():
                    old = old_map.get(key); saved = json.loads(old['result_json']) if old and old['result_json'] else None
                    reused = bool(item['same_definition'] and saved)
                    if reused:
                        from .structured import recorded_outputs
                        outputs = recorded_outputs(old_tasks)
                        reused = all(current_digest(inside(root, name)) == outputs.get(name, value) for name, value in saved['fingerprint']['scope'].items())
                        reused &= all(current_digest(inside(root, name)) == value for name, value in json.loads(old['definition_json']).get('context', {}).items())
                        if reused and json.loads(old['definition_json']).get('structured'):
                            from .structured import dependency_basis
                            reused &= not readiness(connection, root, old, old_tasks)['unmet']
                            reused &= saved.get('dependency_basis', {}) == dependency_basis(connection, old, old_tasks)
                    task_id = identifier(); code = _code(store, change['id'], old)
                    item['definition']['task_code'] = code
                    connection.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)',
                        (task_id, change['id'], new_revision, canonical(item['definition']).decode(), item['digest'], old['state'] if reused else 'todo', 1,
                         old['result_json'] if reused else None))
                    basis = item['definition'].get('analysis_basis')
                    if basis:
                        store.link_source(run_id, basis['run_id'], basis['result_digest'], 'repair_analysis_basis')
                    if item['same_definition']:
                        store.event(run_id, 'task_definition_reused', {'task_id': task_id, 'from_task_id': old['id'],
                            'definition_digest': item['digest'], 'result_reused': reused,
                            'old_result_digest': digest(old['result_json'].encode()) if old['result_json'] else None})
                    result_tasks.append({'id': task_id, 'local_key': key, 'task_code': code, 'state': old['state'] if reused else 'todo',
                                         'definition_digest': item['digest'], 'result_reused': reused})
                store.event(run_id, 'revision_presented', {'revision_id': new_revision, 'from_revision_id': revision['id'],
                    'semantic_same': semantic_same, 'requires_acceptance': not semantic_same or bool(existing_presentation and existing_presentation['requires_acceptance'] and revision['accepted_event_id'] is None),
                    'candidate': candidate, 'reason': data['reason']})
                if approval is not None or (semantic_same and revision['accepted_event_id'] is not None):
                    accepted = store.event(run_id, 'plan_accepted' if approval else 'plan_acceptance_carried',
                        {'revision_id': new_revision, 'plan_digest': plan_digest, 'approval': approval, 'from_event_id': revision['accepted_event_id']})
                    connection.execute('UPDATE plan_revisions SET accepted_event_id=? WHERE id=?', (accepted, new_revision))
                connection.execute('UPDATE changes SET title=?,complexity=?,current_revision=?,row_version=row_version+1 WHERE id=?',
                    (proposal['title'], 'complex' if complex_work else 'simple', new_revision, change['id']))
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?", (canonical({'revision_id': new_revision}).decode(), operation_id))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'revision_committed', {'revision_id': new_revision, 'outcome': 'revised'})
            return store.finish(run_id, {'committed': True, 'outcome': 'revised', 'operation_id': operation_id,
                'change_id': change['id'], 'revision_id': new_revision, 'revision': revision['ordinal']+1, 'definition_digest': definition_digest,
                'plan_digest': plan_digest, 'candidate': candidate, 'candidate_digest': candidate_digest, 'tasks': result_tasks,
                'accepted': bool(approval or (semantic_same and revision['accepted_event_id'])), 'semantic_same': semantic_same})
    except EvolveError as error:
        if store is not None and run_id is not None:
            if not store.run_started(run_id): error.committed = True; raise
            with writer_lock(root):
                with store.transaction() as connection:
                    connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    connection.execute("UPDATE operations SET state='failed' WHERE id=? AND state!='committed'", (operation_id,))
                store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                error.committed = True
        raise
    finally:
        if store is not None: store.close()
