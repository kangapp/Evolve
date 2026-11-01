"""Fixed same-project prerequisites, using existing Task definitions and proofs."""
import json

from .errors import EvolveError
from .package import canonical, digest
from .workspace import current_digest, inside

KINDS = {'task_completed', 'verification_passed', 'artifact_available', 'knowledge_applied'}
FIELDS = {'upstream_change_id', 'upstream_task_id', 'required_revision_id',
          'required_definition_digest', 'condition_kind', 'basis'}


def validate(references):
    if not isinstance(references, list):
        raise EvolveError('DEPENDENCY', 'external_dependencies is an explicit array')
    seen = set()
    for ref in references:
        if (not isinstance(ref, dict) or not FIELDS.issubset(ref) or set(ref) - FIELDS - {'condition_ref'}
                or any(not isinstance(ref[key], str) or not ref[key].strip() for key in FIELDS)
                or ref['condition_kind'] not in KINDS):
            raise EvolveError('DEPENDENCY', 'External prerequisites bind actual target, revision, definition, condition and basis')
        if ref['condition_kind'] in ('artifact_available', 'knowledge_applied'):
            if not isinstance(ref.get('condition_ref'), str) or not ref['condition_ref'].strip():
                raise EvolveError('DEPENDENCY', 'Artifact/knowledge conditions name an actual upstream output path')
        elif 'condition_ref' in ref:
            raise EvolveError('DEPENDENCY', 'Only artifact/knowledge path conditions take condition_ref')
        key = (ref['upstream_change_id'], ref['upstream_task_id'], ref['condition_kind'], ref.get('condition_ref'))
        if key in seen:
            raise EvolveError('DEPENDENCY', 'An external condition must not repeat')
        seen.add(key)


def target(connection, ref):
    change = connection.execute('SELECT * FROM changes WHERE id=?', (ref['upstream_change_id'],)).fetchone()
    task = connection.execute('SELECT * FROM tasks WHERE id=? AND change_id=?',
                              (ref['upstream_task_id'], ref['upstream_change_id'])).fetchone()
    if (not change or not task or change['current_revision'] != ref['required_revision_id']
            or task['revision_id'] != ref['required_revision_id']
            or task['definition_digest'] != ref['required_definition_digest']):
        return None
    return change, task, json.loads(task['definition_json'])


def freeze(connection, references, change_id):
    validate(references)
    for ref in references:
        selected = target(connection, ref)
        if not selected or ref['upstream_change_id'] == change_id:
            raise EvolveError('DEPENDENCY', 'Cross-work prerequisites bind a current task in another Change of this project')
        _, _, definition = selected
        if ref['condition_kind'] in ('artifact_available', 'knowledge_applied') and ref['condition_ref'] not in definition['scope']:
            raise EvolveError('DEPENDENCY', 'Condition output is not owned by the referenced task')
        if ref['condition_kind'] == 'knowledge_applied' and definition.get('responsible_action') not in ('init', 'sync', 'learn'):
            raise EvolveError('DEPENDENCY', 'Applied knowledge must reference its actual formal-document task')
    return references


def input_paths(connection, references):
    outputs, inputs, seen = set(), set(), set()
    def include(task):
        if task['id'] in seen:
            return
        seen.add(task['id'])
        definition = json.loads(task['definition_json'])
        outputs.update(definition['scope'])
        inputs.update(definition['scope'])
        inputs.update(definition.get('context', {}))
        inputs.update(definition.get('dependency_inputs', []))
        peers = connection.execute('SELECT * FROM tasks WHERE change_id=? AND revision_id=?',
                                   (task['change_id'], task['revision_id'])).fetchall()
        by_key = {json.loads(row['definition_json'])['local_key']: row for row in peers}
        for dependency in definition.get('dependencies', []):
            include(by_key[dependency['upstream_task']])
        for reference in definition.get('external_dependencies', []):
            selected = target(connection, reference)
            if selected:
                include(selected[1])
    for reference in references:
        include(target(connection, reference)[1])
    return outputs, inputs


def check_graph(connection, change_id, definitions):
    """Replace just the proposed Change in the current declared task graph."""
    tasks = connection.execute('SELECT t.* FROM tasks t JOIN changes c ON c.id=t.change_id WHERE t.revision_id=c.current_revision').fetchall()
    all_tasks = {row['id']: row for row in connection.execute('SELECT * FROM tasks')}
    docs = {(row['change_id'], json.loads(row['definition_json'])['local_key']): json.loads(row['definition_json'])
            for row in tasks if row['change_id'] != change_id}
    docs.update({(change_id, key): value['definition'] for key, value in definitions.items()})
    edges = {}
    for node, doc in docs.items():
        edges[node] = [(node[0], dep['upstream_task']) for dep in doc.get('dependencies', [])]
        for ref in doc.get('external_dependencies', []):
            old = all_tasks.get(ref['upstream_task_id'])
            if old:
                edges[node].append((old['change_id'], json.loads(old['definition_json'])['local_key']))
    done = set()
    def visit(node, active):
        if node in active:
            raise EvolveError('DEPENDENCY_CYCLE', 'Cross-work task prerequisites must be acyclic')
        if node in done:
            return
        for other in edges.get(node, []):
            visit(other, active | {node})
        done.add(node)
    for node in edges:
        visit(node, set())


def recorded_proof(connection, ref):
    selected = target(connection, ref)
    if selected is None:
        return None
    change, task, definition = selected
    if change['state'] == 'cancelled' or task['state'] != 'done' or not task['result_json']:
        return None
    result = json.loads(task['result_json'])
    if result.get('definition_digest') != task['definition_digest']:
        return None
    for row in connection.execute("SELECT input_json FROM phase_runs WHERE status='started'"):
        if json.loads(row[0])['request']['input'].get('change_id') == change['id']:
            return None
    proof = {'task_id': task['id'], 'definition_digest': task['definition_digest'],
             'result_digest': digest(canonical(result)), 'condition_kind': ref['condition_kind']}
    if ref['condition_kind'] == 'verification_passed':
        from .revisions import eligible_verifications
        from .work import verification_source
        verification = next(iter(eligible_verifications(connection, change['id'], task['revision_id'],
            task if change['complexity'] == 'complex' else None)), None)
        if verification is None or verification['status'] != 'passed' or verification_source(connection, verification) is None:
            return None
        proof['verification_id'] = verification['id']
        if definition.get('responsible_action') in ('init', 'sync', 'learn'):
            proof['verification_basis'] = json.loads(verification['items_json']).get('document_applications', {})
        else:
            inspected = json.loads(verification['fingerprint_json'])
            proof['verification_basis'] = inspected.get('task_basis_digest' if definition.get('structured') else 'digest')
    return proof


def basis(connection, definition):
    result = {}
    for ref in definition.get('external_dependencies', []):
        proof = recorded_proof(connection, ref)
        equivalent = {key: value for key, value in proof.items() if key != 'verification_id'} if proof else None
        result['external:' + digest(canonical(ref))] = digest(canonical(equivalent)) if equivalent else None
    return result


def observations(connection, root, definition, *, pending=None):
    from .structured import current_tasks, dependency_basis, readiness, recorded_outputs
    from .work import check_basis, fingerprint
    unmet = []
    for ref in definition.get('external_dependencies', []):
        selected, proof = target(connection, ref), recorded_proof(connection, ref)
        satisfied = selected is not None and proof is not None
        if satisfied:
            change, task, upstream = selected
            result = json.loads(task['result_json'])
            peers = current_tasks(connection, change['id'], task['revision_id'])
            if upstream.get('structured'):
                satisfied = (not readiness(connection, root, task, peers, pending=pending)['unmet']
                    and result.get('dependency_basis', {}) == dependency_basis(connection, task, peers))
                expected = recorded_outputs(peers)
            else:
                expected = result['fingerprint']['scope']
            formal = upstream.get('responsible_action') in ('init', 'sync', 'learn')
            applications = {}
            try:
                check_basis(root, upstream)
                if formal:
                    from .formal import document_applications
                    complete, applications = document_applications(connection, root, task, pending=pending)
                    satisfied &= complete
                else:
                    satisfied &= all(current_digest(inside(root, name)) == expected.get(name) for name in upstream['scope'])
            except EvolveError:
                satisfied = False
            if satisfied and ref['condition_kind'] == 'verification_passed':
                verification = connection.execute('SELECT * FROM verifications WHERE id=?', (proof['verification_id'],)).fetchone()
                saved = json.loads(verification['fingerprint_json'])
                if formal:
                    inspected = json.loads(verification['items_json']).get('document_applications', {})
                    satisfied = bool(applications) and set(applications.values()).issubset(inspected.values())
                else:
                    current = fingerprint(root, upstream)
                    # Explicit structured context permits bounded reuse; simple
                    # plans retain the whole-workspace acceptance cutoff.
                    key = 'task_basis_digest' if upstream.get('structured') else 'digest'
                    satisfied = saved.get(key) is not None and saved.get(key) == current.get(key)
            if satisfied and ref['condition_kind'] == 'artifact_available':
                name = ref['condition_ref']
                satisfied = current_digest(inside(root, name)) is not None and current_digest(inside(root, name)) == expected.get(name)
            if satisfied and ref['condition_kind'] == 'knowledge_applied':
                from .formal import document_applications
                complete, applications = document_applications(connection, root, task, pending=pending)
                satisfied = complete and ref['condition_ref'] in applications
        if not satisfied:
            unmet.append({'kind': 'external_' + ref['condition_kind'], 'reference': ref['upstream_task_id'],
                          'upstream_change_id': ref['upstream_change_id'], 'reason': ref['basis'],
                          'recheck_required': True})
    return unmet


def snapshot(connection, change_id, data):
    change = connection.execute('SELECT current_revision FROM changes WHERE id=?', (change_id,)).fetchone()
    result = {}
    for task in connection.execute('SELECT * FROM tasks WHERE change_id=? AND revision_id=?', (change_id, change['current_revision'])):
        if data.get('task_id') is not None and data['task_id'] != task['id']:
            continue
        definition = json.loads(task['definition_json'])
        if definition.get('external_dependencies'):
            result[task['id']] = basis(connection, definition)
    return result


def proofs(connection, change_id, data):
    result = {}
    for task_id in snapshot(connection, change_id, data):
        row = connection.execute('SELECT definition_json FROM tasks WHERE id=?', (task_id,)).fetchone()
        result[task_id] = [{'reference': ref, 'observed_proof': recorded_proof(connection, ref)}
                          for ref in json.loads(row[0])['external_dependencies']]
    return result


def guard(connection, root, run_id, change_id, data):
    current = snapshot(connection, change_id, data)
    if not current:
        return
    events = connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind='cross_dependencies_bound'", (run_id,)).fetchall()
    if len(events) != 1 or json.loads(events[0][0])['task_bases'] != current:
        raise EvolveError('DEPENDENCY_CHANGED', 'A required upstream result or verification changed during execution', exit_code=3)
    pending = None
    prepared = connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind='formal_application_prepared'", (run_id,)).fetchall()
    if len(prepared) == 1:
        value = json.loads(prepared[0][0])
        operation = connection.execute('SELECT * FROM operations WHERE id=? AND run_id=?', (value['operation_id'], run_id)).fetchone()
        run = connection.execute('SELECT input_json FROM phase_runs WHERE id=?', (run_id,)).fetchone()
        request = json.loads(run[0])['request']['input']
        proposal = connection.execute('SELECT target_path FROM knowledge_proposals WHERE id=?',
            (request.get('proposal', {}).get('proposal_id'),)).fetchone()
        if operation and operation['effect_kind'] == 'knowledge' and proposal:
            pending = {**value['effect'], 'target_path': proposal['target_path']}
    for task_id in current:
        task = connection.execute('SELECT definition_json FROM tasks WHERE id=?', (task_id,)).fetchone()
        unmet = observations(connection, root, json.loads(task['definition_json']), pending=pending)
        if unmet:
            raise EvolveError('DEPENDENCY_NOT_READY', 'Current upstream prerequisites require rechecking: ' + json.dumps(unmet), exit_code=3)
