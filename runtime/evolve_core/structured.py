"""Presented specifications and revision-local task definitions, without a scheduler."""
import json
from pathlib import Path
import tomllib

from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .workspace import current_digest, inside, writer_lock


DOCUMENT_FIELDS = ('title', 'plan', 'completion', 'scope', 'acceptance', 'required_checks', 'spec', 'tasks')


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise EvolveError('INPUT', 'Structured plan requires ' + label)


def strings(value, label, *, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise EvolveError('INPUT', label + ' requires an explicit string array')
    if len(set(value)) != len(value):
        raise EvolveError('INPUT', label + ' must not contain duplicates')


def document(data):
    result = {key: data.get(key) for key in DOCUMENT_FIELDS}
    if data.get('analysis_basis') is not None:
        result['analysis_basis'] = data['analysis_basis']
    if data.get('knowledge_impact') is not None:
        result['knowledge_impact'] = data['knowledge_impact']
    if data.get('impact_resolutions') is not None:
        result['impact_resolutions'] = data['impact_resolutions']
    if data.get('knowledge_review') is not None:
        result['knowledge_review'] = data['knowledge_review']
    if data.get('review_policy') is not None:
        result['review_policy'] = data['review_policy']
    return result


def validate(root, data):
    from .plans import task_path
    for key in ('title', 'plan', 'completion'):
        text(data.get(key), key)
    if data.get('required_knowledge') or data.get('spec_delta') not in (None, 'none', [], {}) or data.get('dependencies') or data.get('external_dependencies'):
        raise EvolveError('UNAVAILABLE', 'Formal knowledge delivery and cross-change dependencies need their owning workflow')
    strings(data.get('scope'), 'scope', nonempty=True)
    paths = [inside(root, name).resolve() for name in data['scope']]
    if len(set(paths)) != len(paths):
        raise EvolveError('SCOPE', 'Structured scope contains aliased duplicate files')
    strings(data.get('required_checks'), 'required_checks')
    spec = data.get('spec')
    if not isinstance(spec, dict):
        raise EvolveError('INPUT', 'Complex work requires a complete spec')
    text(spec.get('problem'), 'spec.problem')
    for key in ('goals', 'non_goals', 'behavior', 'constraints', 'tradeoffs', 'test_decisions'):
        strings(spec.get(key), 'spec.' + key, nonempty=key in ('goals', 'behavior', 'test_decisions'))
    questions = spec.get('open_questions')
    if not isinstance(questions, list):
        raise EvolveError('INPUT', 'Spec requires explicit open_questions, including an empty list')
    acceptance = data.get('acceptance')
    if not isinstance(acceptance, list) or not acceptance or any(not isinstance(a, dict) for a in acceptance):
        raise EvolveError('INPUT', 'Structured acceptance requires stable keys and behavioral text')
    for item in acceptance:
        text(item.get('key'), 'acceptance.key')
        text(item.get('text'), 'acceptance.text')
    ac_keys = {a['key'] for a in acceptance}
    if len(ac_keys) != len(acceptance):
        raise EvolveError('INPUT', 'Acceptance keys must be unique')
    tasks = data.get('tasks')
    if not isinstance(tasks, list) or not tasks or any(not isinstance(t, dict) for t in tasks):
        raise EvolveError('INPUT', 'Complex work requires explicit outcome tasks')
    if data.get('analysis_basis') is not None and len(tasks) != 1:
        raise EvolveError('ANALYSIS_REFERENCE', 'Multiple tasks must declare their own exact analysis_basis')
    keys = set()
    covered, checks = set(), set(data['required_checks'])
    for task in tasks:
        from .external_work import definition_fields
        definition_fields(root, task)
        if task.get('required_knowledge') or task.get('spec_delta') not in (None, 'none', [], {}):
            raise EvolveError('UNAVAILABLE', 'Required formal knowledge cannot be silently omitted from a task')
        for key in ('local_key', 'title', 'completion', 'validation'):
            text(task.get(key), 'task.' + key)
        if task['local_key'] in keys:
            raise EvolveError('INPUT', 'Task local keys must be unique')
        keys.add(task['local_key'])
        for key in ('scope', 'acceptance', 'required_checks', 'context_paths', 'exclusions', 'test_decision_refs'):
            strings(task.get(key), 'task.' + key, nonempty=key in ('scope', 'acceptance', 'test_decision_refs'))
        for name in task['scope']:
            task_path(root, name, task.get('responsible_action', 'apply'))
        if task.get('responsible_action', 'apply') != 'apply' and task.get('pre_refactor'):
            raise EvolveError('KNOWLEDGE_OWNER', 'Formal document tasks use candidate checks, not business pre-refactor execution')
        if data.get('analysis_basis') is not None and 'analysis_basis' in task and task['analysis_basis'] != data['analysis_basis']:
            raise EvolveError('ANALYSIS_REFERENCE', 'Root and single-task investigation references must agree')
        if task.get('analysis_basis', data.get('analysis_basis')) is not None:
            if task.get('responsible_action', 'apply') != 'apply':
                raise EvolveError('KNOWLEDGE_OWNER', 'Diagnostic repair bindings belong to business implementation tasks')
        decision_refs = {'spec.test_decisions/' + str(index) for index in range(len(spec['test_decisions']))}
        if not set(task['test_decision_refs']).issubset(decision_refs):
            raise EvolveError('CONTEXT', 'Task test decisions must reference the presented spec')
        if not set(task['scope']).issubset(data['scope']) or not set(task['acceptance']).issubset(ac_keys):
            raise EvolveError('SCOPE', 'Task must use the presented file scope and acceptance keys')
        covered.update(task['acceptance'])
        checks.update(task['required_checks'])
        dependencies = task.get('dependencies')
        if 'external_dependencies' in task:
            from .cross_dependencies import validate as validate_external
            validate_external(task['external_dependencies'])
        if not isinstance(dependencies, list) or any(not isinstance(d, dict) for d in dependencies):
            raise EvolveError('DEPENDENCY', 'Each task requires explicit conditional dependencies')
        seen = set()
        for dep in dependencies:
            text(dep.get('upstream_task'), 'dependency.upstream_task')
            text(dep.get('basis'), 'dependency.basis')
            if dep['upstream_task'] in seen:
                raise EvolveError('DEPENDENCY', 'A task dependency must not repeat')
            seen.add(dep['upstream_task'])
            if dep.get('condition_kind') not in ('task_completed', 'verification_passed', 'artifact_available'):
                raise EvolveError('UNAVAILABLE', 'This slice supports same-change task, verification and artifact conditions')
        if type(task.get('pre_refactor', False)) is not bool:
            raise EvolveError('INPUT', 'pre_refactor must be boolean')
        if task.get('pre_refactor'):
            strings(task.get('preservation_checks'), 'preservation_checks', nonempty=True)
            strings(task.get('preservation_inputs'), 'preservation_inputs', nonempty=True)
            if not set(task['preservation_checks']).issubset(task['required_checks']) or not set(task['preservation_inputs']).issubset(task['context_paths']):
                raise EvolveError('PRESERVATION', 'Behavior preservation uses registered task checks and frozen context inputs')
            if {inside(root, name).resolve() for name in task['preservation_inputs']} & {task_path(root, name).resolve() for name in task['scope']}:
                raise EvolveError('PRESERVATION', 'Preservation inputs must remain unchanged during the refactor task')
    if covered != ac_keys or set().union(*(set(t['scope']) for t in tasks)) != set(data['scope']):
        raise EvolveError('COVERAGE', 'Every required acceptance condition and scoped file needs an outcome task')
    by_key = {task['local_key']: task for task in tasks}
    ancestors, order = {}, []
    def visit(key, active):
        if key in ancestors:
            return ancestors[key]
        if key in active:
            raise EvolveError('DEPENDENCY_CYCLE', 'Task dependencies must be acyclic')
        result = set()
        for dep in by_key[key]['dependencies']:
            upstream = dep['upstream_task']
            if upstream not in by_key:
                raise EvolveError('DEPENDENCY', 'Dependency target is not in the current change')
            if dep['condition_kind'] == 'artifact_available' and dep.get('condition_ref') not in by_key[upstream]['scope']:
                raise EvolveError('DEPENDENCY', 'Artifact condition must name an upstream scoped output')
            result.add(upstream)
            result.update(visit(upstream, active | {key}))
        ancestors[key] = result
        order.append(key)
        return result
    for key in by_key:
        visit(key, set())
    for task in tasks:
        produced = {inside(root, name).resolve() for key in ancestors[task['local_key']] for name in by_key[key]['scope']}
        for name in task['context_paths']:
            path = inside(root, name)
            if not path.is_file() and (path.exists() or path.resolve() not in produced):
                raise EvolveError('CONTEXT', 'Context must be an observed file or a declared upstream output: ' + name)
    from .planning_impacts import observe
    observe(root, tasks, data.get('impact_resolutions'))
    for index, left in enumerate(tasks):
        for right in tasks[index + 1:]:
            if set(left['scope']) & set(right['scope']) and left['local_key'] not in ancestors[right['local_key']] and right['local_key'] not in ancestors[left['local_key']]:
                raise EvolveError('DEPENDENCY', 'Tasks sharing an output require a real ordering condition')
    question_keys = set()
    for question in questions:
        if not isinstance(question, dict) or type(question.get('blocking')) is not bool:
            raise EvolveError('INPUT', 'Open questions require identity, question, blocking and task_keys')
        for key in ('id', 'question'):
            text(question.get(key), 'open_question.' + key)
        strings(question.get('task_keys'), 'open_question.task_keys', nonempty=question['blocking'])
        if question['id'] in question_keys or not set(question['task_keys']).issubset(keys):
            raise EvolveError('INPUT', 'Open question identity or affected tasks are invalid')
        question_keys.add(question['id'])
    if type(spec.get('broad_migration', False)) is not bool:
        raise EvolveError('INPUT', 'broad_migration must be boolean')
    if spec.get('broad_migration'):
        text(spec.get('integration_boundary'), 'spec.integration_boundary')
        if not data['required_checks']:
            raise EvolveError('CHECK_CONFIG', 'A broad migration needs final integration checks')
    presentation = data.get('presentation')
    if not isinstance(presentation, dict) or not presentation.get('source') or presentation.get('document') != document(data):
        raise EvolveError('PRESENTATION', 'Persist the entire structured document actually presented, including spec and tasks')
    configured = tomllib.loads(inside(root, 'evolve/config.toml').read_text()).get('verification', {}).get('checks', [])
    from .knowledge_impact import freeze_review, validate_review_impacts
    validate_review_impacts(freeze_review(root, data), data.get('knowledge_impact'))
    from .verify import policy_fields
    policy_fields(data)
    for task in tasks:
        policy_fields(task)
    if not checks.issubset({c['id'] for c in configured}):
        raise EvolveError('CHECK_CONFIG', 'Structured work references a check not registered by init')
    return order, configured


def definitions(root, data, order, configured, acceptance, *, connection=None, change_id=None):
    from .plans import task_path
    result = {}
    ancestor_outputs = {}
    ac = {item['key']: item for item in acceptance}
    tasks = {task['local_key']: task for task in data['tasks']}
    from .planning_impacts import observe
    impacts = observe(root, data['tasks'], data.get('impact_resolutions'))
    for key in order:
        source = tasks[key]
        ancestor_outputs[key] = {name for dep in source['dependencies']
            for name in (set(tasks[dep['upstream_task']]['scope']) | ancestor_outputs[dep['upstream_task']])}
        ancestor_targets = {inside(root, name).resolve() for name in ancestor_outputs[key]}
        definition = {name: source[name] for name in ('local_key', 'title', 'completion', 'validation', 'exclusions', 'scope', 'required_checks')}
        definition.update({'acceptance': [ac[k] for k in source['acceptance']],
            'checks_basis': [c for c in configured if c['id'] in source['required_checks']],
            'baseline': {name: current_digest(task_path(root, name, source.get('responsible_action', 'apply'))) for name in source['scope']},
            'context': {name: current_digest(inside(root, name)) for name in source['context_paths']
                        if inside(root, name).resolve() not in ancestor_targets},
            'test_decisions': [{'reference': ref, 'digest': digest(canonical(data['spec']['test_decisions'][int(ref.rsplit('/', 1)[1])]))}
                               for ref in source['test_decision_refs']],
            'dependencies': [{**dep, 'required_definition_digest': result[dep['upstream_task']]['digest']} for dep in source['dependencies']],
            'dependency_inputs': sorted({name for dep in source['dependencies']
                for name in (tasks[dep['upstream_task']]['scope'] + tasks[dep['upstream_task']]['context_paths']
                             + result[dep['upstream_task']]['definition']['dependency_inputs'])}),
            'blocking_questions': [q for q in data['spec']['open_questions'] if q['blocking'] and key in q['task_keys']],
            'responsible_action': source.get('responsible_action', 'apply'), 'required_deliverables': source['scope'],
            'spec_delta': 'owner_candidate_required' if source.get('responsible_action', 'apply') != 'apply' else 'none',
            'structured': True, 'pre_refactor': source.get('pre_refactor', False),
            'preservation_checks': source.get('preservation_checks', []), 'preservation_inputs': source.get('preservation_inputs', [])})
        produced_context = {name: inside(root, name).resolve().relative_to(root).as_posix() for name in source['context_paths']
                            if inside(root, name).resolve() in ancestor_targets}
        if produced_context:
            definition['produced_context'] = produced_context
        from .external_work import definition_fields
        definition.update(definition_fields(root, source))
        related = [item for item in impacts if key in (item['producer'], item['consumer'])]
        if related:
            definition['input_impacts'] = related
        from .verify import policy_fields
        definition.update(policy_fields(source if 'review_policy' in source else data))
        if connection is not None:
            from .knowledge_impact import freeze as freeze_knowledge_impact
            impact_source = source if 'knowledge_impact' in source else data
            knowledge_impact = freeze_knowledge_impact(connection, root, impact_source, source['scope'])
            if knowledge_impact is not None:
                definition['knowledge_impact'] = knowledge_impact
            from .knowledge_impact import freeze_review
            review = freeze_review(root, data)
            if review is not None:
                definition['knowledge_review'] = review
        if source.get('external_dependencies'):
            from .cross_dependencies import freeze, input_paths
            definition['external_dependencies'] = freeze(connection, source['external_dependencies'], change_id)
            produced, inputs = input_paths(connection, definition['external_dependencies'])
            definition['context'] = {name: value for name, value in definition['context'].items() if name not in produced}
            definition['dependency_inputs'] = sorted(set(definition['dependency_inputs']) | inputs)
        basis = source.get('analysis_basis', data.get('analysis_basis'))
        if basis is not None:
            from .analysis import repair_basis
            _, adopted = repair_basis(connection, basis, definition['checks_basis'], root=root)
            definition['analysis_basis'] = basis
            if adopted['analysis'].get('symptom') is not None:
                definition['symptom_before'] = adopted['analysis']['symptom']
        semantic = {k: v for k, v in definition.items() if k != 'baseline'}
        result[key] = {'definition': definition, 'digest': digest(canonical(semantic))}
    if connection is not None:
        from .cross_dependencies import check_graph
        check_graph(connection, change_id, result)
    return result


def current_tasks(connection, change_id, revision_id):
    return connection.execute('SELECT * FROM tasks WHERE change_id=? AND revision_id=? ORDER BY rowid',
                              (change_id, revision_id)).fetchall()


def dependency_basis(connection, task, peers):
    by_key = {json.loads(row['definition_json'])['local_key']: row for row in peers}
    result = {}
    for dep in json.loads(task['definition_json']).get('dependencies', []):
        upstream = by_key.get(dep['upstream_task'])
        saved = json.loads(upstream['result_json']) if upstream and upstream['result_json'] else None
        proof = None
        if upstream and upstream['state'] == 'done' and saved and saved.get('definition_digest') == upstream['definition_digest']:
            proof = {'definition_digest': upstream['definition_digest'], 'scope': saved['fingerprint']['scope'],
                     'context': saved['fingerprint'].get('context', {}), 'dependencies': saved.get('dependency_basis', {})}
            proof.update({key: saved['fingerprint'][key] for key in ('environment', 'input_policy') if key in saved['fingerprint']})
        result[dep['upstream_task']] = digest(canonical(proof)) if proof is not None else None
    from .cross_dependencies import basis
    result.update(basis(connection, json.loads(task['definition_json'])))
    return result


def recorded_outputs(peers):
    outputs = {}
    for task in peers:
        if task['state'] in ('done', 'in_progress') and task['result_json']:
            result = json.loads(task['result_json'])
            if result.get('definition_digest') == task['definition_digest']:
                outputs.update(result['fingerprint']['scope'])
    return outputs


def whole_definition(revision, peers):
    checks = json.loads(revision['checks_json'])
    context = {}
    for task in peers:
        for path, value in json.loads(task['definition_json']).get('context', {}).items():
            if path in context and context[path] != value:
                raise EvolveError('CONTEXT', 'Task context versions disagree; revise the affected tasks: ' + path)
            context[path] = value
    policy = {'review_policy': 'independent'} if any(json.loads(task['definition_json']).get('review_policy') == 'independent' for task in peers) else {}
    return {**policy, 'whole_change': True, 'structured': True, 'scope': json.loads(revision['scope_json']),
            'required_deliverables': json.loads(revision['scope_json']), 'context': context,
            'acceptance': json.loads(revision['acceptance_json']), 'required_checks': [c['id'] for c in checks], 'checks_basis': checks}


def implementation_state(connection, root, change, revision, task, definition):
    from .formal import verification_applications
    documents_complete, _ = verification_applications(connection, root, change, revision, task, definition)
    if not definition.get('structured'):
        saved = json.loads(task['result_json']) if task['result_json'] else None
        if saved and documents_complete and definition.get('responsible_action') in ('sync', 'init', 'learn'):
            saved = {**saved, 'fingerprint': {**saved['fingerprint'], 'scope': {p: current_digest(inside(root, p)) for p in definition['scope']}}}
        from .external_work import recorded_complete
        complete = task['state'] == 'done' and documents_complete and recorded_complete(connection, root, task, definition, saved)
        from .work import context_changes
        complete = complete and not context_changes(root, definition)
        if complete and definition.get('pre_refactor'):
            from .preservation import completion_proven
            complete = bool(saved and completion_proven(connection, root, task, definition, saved, None))
        return complete, saved
    peers = current_tasks(connection, change['id'], revision['id'])
    selected = peers if definition.get('whole_change') else [task]
    complete = documents_complete
    for item in selected:
        from .work import check_basis
        check_basis(root, json.loads(item['definition_json']))
        saved = json.loads(item['result_json']) if item['result_json'] else None
        item_definition = json.loads(item['definition_json'])
        from .external_work import recorded_complete
        complete &= recorded_complete(connection, root, item, item_definition, saved)
        if item['state'] == 'done' and saved and item_definition.get('pre_refactor'):
            from .preservation import completion_proven
            complete &= completion_proven(connection, root, item, item_definition, saved, dependency_basis(connection, item, peers))
        complete &= bool(item['state'] == 'done' and saved and saved.get('definition_digest') == item['definition_digest']
                         and saved.get('dependency_basis', {}) == dependency_basis(connection, item, peers)
                         and not readiness(connection, root, item, peers)['unmet'])
        if definition.get('whole_change') and item_definition.get('symptom_before') is not None:
            from .analysis import repair_task_verified
            complete &= repair_task_verified(connection, root, item, item_definition)
    if definition.get('whole_change'):
        outputs = recorded_outputs(peers)
        if documents_complete:
            for item in peers:
                item_definition = json.loads(item['definition_json'])
                if item_definition.get('responsible_action') in ('sync', 'init', 'learn'):
                    outputs.update({p: current_digest(inside(root, p)) for p in item_definition['scope']})
        return complete, {'fingerprint': {'scope': outputs}}
    saved = json.loads(task['result_json']) if task['result_json'] else None
    if saved and documents_complete and definition.get('responsible_action') in ('sync', 'init', 'learn'):
        saved = {**saved, 'fingerprint': {**saved['fingerprint'], 'scope': {p: current_digest(inside(root, p)) for p in definition['scope']}}}
    return complete, saved


def invalidate_dependents(store, run_id, change_id, revision_id):
    # Keep the old result and immutable source run; only related current tasks reopen.
    for task in current_tasks(store.connection, change_id, revision_id):
        if task['state'] != 'done' or not task['result_json']:
            continue
        peers = current_tasks(store.connection, change_id, revision_id)
        saved = json.loads(task['result_json'])
        if saved.get('dependency_basis', {}) != dependency_basis(store.connection, task, peers):
            store.connection.execute("UPDATE tasks SET state='todo',row_version=row_version+1 WHERE id=?", (task['id'],))
            store.event(run_id, 'task_dependency_invalidated', {'task_id': task['id'],
                'old_result_digest': digest(canonical(saved)), 'reason': 'Actual required upstream result changed'})


def readiness(connection, root, task, peers, *, pending=None):
    from .formal import document_applications
    definition = json.loads(task['definition_json'])
    unmet = []
    for impact in definition.get('input_impacts', []):
        if impact['requires_review']:
            unmet.append({'kind': 'planning_impact', 'reference': impact['paths'],
                          'reason': 'Review producer/input overlap and revise the concrete dependency or independent-impact decision.'})
    change = connection.execute('SELECT state FROM changes WHERE id=?', (task['change_id'],)).fetchone()
    if task['state'] == 'cancelled' or change['state'] == 'cancelled':
        unmet.append({'kind': 'cancelled', 'reference': task['id'], 'reason': 'Work was explicitly cancelled; physical results remain historical.'})
    if task['state'] == 'done' and definition.get('responsible_action') in ('sync', 'init', 'learn'):
        if not document_applications(connection, root, task, pending=pending)[0]:
            unmet.append({'kind': 'document_application', 'reference': task['id'],
                'reason': 'Actual document application is changed, incomplete or not safely finalized'})
    from .work import check_basis
    try:
        check_basis(root, definition)
    except EvolveError as error:
        unmet.append({'kind': 'check_config_changed', 'reference': definition['local_key'], 'reason': str(error)})
    for question in definition.get('blocking_questions', []):
        unmet.append({'kind': 'open_question', 'reference': question['id'], 'reason': question['question']})
    for name, expected in definition.get('context', {}).items():
        if current_digest(inside(root, name)) != expected:
            unmet.append({'kind': 'context_changed', 'reference': name, 'reason': 'Declared context changed; inspect and revise the affected task'})
    for name, target in definition.get('produced_context', {}).items():
        path = inside(root, name)
        if path.resolve().relative_to(root).as_posix() != target:
            unmet.append({'kind': 'context_target_changed', 'reference': name, 'reason': 'Declared upstream context now resolves to a different output'})
        elif not path.is_file():
            unmet.append({'kind': 'context_missing', 'reference': name, 'reason': 'Declared upstream context has not been produced as a file'})
    by_key = {json.loads(row['definition_json'])['local_key']: row for row in peers}
    outputs = recorded_outputs(peers)
    for dep in definition.get('dependencies', []):
        upstream = by_key.get(dep['upstream_task'])
        result = json.loads(upstream['result_json']) if upstream and upstream['result_json'] else None
        applicable = bool(upstream and result and upstream['definition_digest'] == dep['required_definition_digest']
                          and result.get('definition_digest') == upstream['definition_digest'])
        satisfied = applicable and upstream['state'] == 'done'
        if satisfied:
            upstream_definition = json.loads(upstream['definition_json'])
            satisfied = (result.get('dependency_basis', {}) == dependency_basis(connection, upstream, peers)
                         and not readiness(connection, root, upstream, peers, pending=pending)['unmet']
                         and all(current_digest(inside(root, name)) == expected for name, expected in upstream_definition.get('context', {}).items())
                         and (document_applications(connection, root, upstream, pending=pending)[0]
                              if upstream_definition.get('responsible_action') in ('sync', 'init', 'learn')
                              else all(current_digest(inside(root, name)) == outputs.get(name) for name in upstream_definition['scope'])))
        if satisfied and dep['condition_kind'] == 'artifact_available':
            name = dep['condition_ref']
            satisfied = (result['fingerprint']['scope'].get(name) is not None
                         and current_digest(inside(root, name)) == outputs.get(name))
        elif satisfied and dep['condition_kind'] == 'verification_passed':
            verification = None
            from .revisions import eligible_verifications
            for row in eligible_verifications(connection, upstream['change_id'], upstream['revision_id'], upstream):
                verification = row
                break
            if verification is not None:
                from .work import verification_source
                observed = json.loads(verification['fingerprint_json'])
                satisfied = verification['status'] == 'passed' and verification_source(connection, verification) is not None
                if upstream_definition.get('responsible_action') in ('sync', 'init', 'learn'):
                    inspected = json.loads(verification['items_json']).get('document_applications', {})
                    satisfied &= bool(result.get('document_applications')) and set(result['document_applications'].values()).issubset(inspected.values())
                else:
                    satisfied &= (observed.get('task_basis_digest') is not None
                                  and observed['task_basis_digest'] == result['fingerprint'].get('task_basis_digest'))
            else:
                satisfied = False
        if not satisfied:
            unmet.append({'kind': dep['condition_kind'], 'reference': dep['upstream_task'], 'reason': dep['basis']})
    from .cross_dependencies import observations
    unmet.extend(observations(connection, root, definition, pending=pending))
    saved = json.loads(task['result_json']) if task['result_json'] else None
    if task['state'] == 'done' and definition.get('pre_refactor'):
        from .preservation import completion_proven
        try:
            proven = bool(saved and completion_proven(connection, root, task, definition, saved, dependency_basis(connection, task, peers)))
            if not proven:
                unmet.append({'kind': 'behavior_proof', 'reference': task['id'], 'reason': 'Before/after behavior proof is incomplete'})
        except EvolveError as error:
            unmet.append({'kind': 'behavior_proof', 'reference': task['id'], 'reason': str(error)})
    if task['state'] == 'done' and definition.get('execution_kind') == 'external_write':
        from .external_work import recorded_complete
        if not recorded_complete(connection, root, task, definition, saved):
            unmet.append({'kind': 'external_scope_unconfirmed', 'reference': task['id'], 'reason': 'Data/check cutoff is not current; reconcile and check without redispatch.'})
    changed_basis = bool(saved and saved.get('dependency_basis', {}) != dependency_basis(connection, task, peers))
    return {'ready': not unmet and (task['state'] != 'done' or changed_basis), 'unmet': unmet,
            'revalidation_required': bool(task['state'] == 'done' and (unmet or changed_basis))}


def propose(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    data = request['input']
    order, configured = validate(root, data)
    from .planning_impacts import observe, workspace_observations
    impacts = observe(root, data['tasks'], data.get('impact_resolutions'))
    if not request.get('project_id') or not request.get('expected_workspace_epoch'):
        raise EvolveError('INPUT', 'Prepared request must freeze project identity and epoch')
    with writer_lock(root):
        store = Store(root)
        try:
            run_id, previous = store.start(request, action='propose', method='create', owner='evolve-propose')
            if previous is not None:
                return previous
            try:
                change_id, revision_id = identifier(), identifier()
                with store.transaction() as connection:
                    workspace_impacts = workspace_observations(connection, root, data['scope'],
                        [name for task in data['tasks'] for name in task['context_paths']])
                    if workspace_impacts:
                        store.event(run_id, 'workspace_impacts_observed', {'impacts': workspace_impacts})
                    acceptance = [{'key': item['key'], 'id': store.number('AC'), 'text': item['text'], 'required': True} for item in data['acceptance']]
                    planned = definitions(root, data, order, configured, acceptance, connection=connection, change_id=change_id)
                    plan_digest = store.blob(canonical(document(data)))
                    definition_digest = digest(canonical({'spec': data['spec'], 'completion': data['completion'],
                        'tasks': {key: item['digest'] for key, item in planned.items()},
                        'acceptance': acceptance, 'required_checks': data['required_checks']}))
                    code = 'CHG-' + now()[:10].replace('-', '') + '-' + change_id[:8]
                    connection.execute('INSERT INTO changes VALUES (?,?,?,?,?,?,?,?)',
                        (change_id, code, data['title'], 'modification', 'complex', 'ready', revision_id, 1))
                    connection.execute('INSERT INTO plan_revisions VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (revision_id, change_id, 1, plan_digest, definition_digest, canonical(data['scope']).decode(),
                         canonical(acceptance).decode(), canonical([c for c in configured if c['id'] in data['required_checks']]).decode(), now(), None))
                    tasks = []
                    for key, item in planned.items():
                        task_id = identifier()
                        task_code = 'TASK-' + store.number('TASK:' + change_id).rsplit('-', 1)[1]
                        item['definition']['task_code'] = task_code
                        connection.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)',
                            (task_id, change_id, revision_id, canonical(item['definition']).decode(), item['digest'], 'todo', 1, None))
                        tasks.append({'id': task_id, 'local_key': key, 'task_code': task_code, 'change_id': change_id,
                                      'definition_digest': item['digest'], 'state': 'todo', 'row_version': 1})
                        basis = item['definition'].get('analysis_basis')
                        if basis:
                            store.link_source(run_id, basis['run_id'], basis['result_digest'], 'repair_analysis_basis')
                    store.event(run_id, 'plan_presented', {'revision_id': revision_id, 'plan_digest': plan_digest,
                        'source': data['presentation']['source'], 'structured': True})
                    plan_ref = store.artifact(None, 'structured_spec', canonical(document(data)), run_id, data['presentation']['source'])
                return store.finish(run_id, {'committed': True, 'outcome': 'planned', 'change_id': change_id,
                    'change_code': code, 'revision_id': revision_id, 'revision': 1, 'definition_digest': definition_digest,
                    'plan_digest': plan_digest, 'tasks': tasks, 'change_version': 1, 'acceptance': acceptance,
                    'plan_ref': plan_ref, 'accepted': False,
                    'planning_impacts': impacts, 'workspace_impacts': workspace_impacts})
            except EvolveError as error:
                if store.run_started(run_id):
                    store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'error': {'code': error.code, 'message': str(error)}}, status='blocked')
                error.committed = True
                raise
        finally:
            store.close()
