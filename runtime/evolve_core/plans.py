"""Persist a presented short plan; no business modification or implicit approval."""
import json
from pathlib import Path
import tomllib

from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .workspace import current_digest, inside, writer_lock


def business_path(root, name):
    path = inside(root, name)
    relative = path.relative_to(Path(root).resolve())
    resolved = path.resolve().relative_to(Path(root).resolve())
    excluded = {'.git', '.evolve-local', 'evolve', '.codex', '.claude', '.agents'}
    if not relative.parts or not resolved.parts or path.is_dir() or relative.parts[0] in excluded or resolved.parts[0] in excluded:
        raise EvolveError('SCOPE', 'Business implementation cannot write records or host configuration: ' + name)
    return path


def task_path(root, name, owner='apply'):
    if owner == 'apply':
        return business_path(root, name)
    if owner in ('sync', 'init', 'learn'):
        from .knowledge import baseline_path
        return baseline_path(root, name)
    raise EvolveError('UNAVAILABLE', 'This plan supports business apply or formal document init/sync/learn tasks')


def validate_plan(root, data):
    if (data.get('complexity', 'simple') != 'simple'
            or any(data.get(key) for key in ('tasks', 'dependencies', 'external_dependencies', 'required_knowledge', 'spec'))
            or data.get('spec_delta') not in (None, 'none', [], {})):
        raise EvolveError('UNAVAILABLE', 'Complex tasks or required knowledge delivery need the later structured workflow; they are not ignored')
    for field in ('title', 'plan', 'completion'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise EvolveError('INPUT', 'Short plan requires ' + field)
    scope = data.get('scope')
    if not isinstance(scope, list) or not scope or any(not isinstance(p, str) for p in scope):
        raise EvolveError('SCOPE', 'Plan requires explicit file scope')
    paths = [task_path(root, p, data.get('responsible_action', 'apply')) for p in scope]
    if len({p.resolve() for p in paths}) != len(paths):
        raise EvolveError('SCOPE', 'Plan file scope contains duplicate targets')
    acceptance = data.get('acceptance')
    if not isinstance(acceptance, list) or not acceptance or any(not isinstance(a, str) or not a.strip() for a in acceptance):
        raise EvolveError('INPUT', 'Plan requires nonempty behavioral acceptance conditions')
    presentation = data.get('presentation')
    if not isinstance(presentation, dict) or presentation.get('text') != data['plan'] or not presentation.get('source'):
        raise EvolveError('PRESENTATION', 'Persist the exact plan text actually presented and its source')
    from .external_work import definition_fields
    definition_fields(root, data)
    required_checks = data.get('required_checks')
    if not isinstance(required_checks, list) or any(not isinstance(c, str) for c in required_checks):
        raise EvolveError('INPUT', 'required_checks must be an explicit array (may be empty for inspection-only work)')
    if len(required_checks) != len(set(required_checks)):
        raise EvolveError('INPUT', 'Required checks must not repeat')


def propose(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    data = request['input']
    if data.get('complexity') == 'complex':
        from .structured import propose as structured_propose
        return structured_propose(root, request)
    validate_plan(root, data)
    if not request.get('project_id') or not request.get('expected_workspace_epoch'):
        raise EvolveError('INPUT', 'Prepared request must freeze project identity and workspace epoch')
    config = tomllib.loads(inside(root, 'evolve/config.toml').read_text())
    configured = {c['id'] for c in config.get('verification', {}).get('checks', [])}
    if not set(data['required_checks']).issubset(configured):
        raise EvolveError('CHECK_CONFIG', 'Plan references checks not registered by init')
    with writer_lock(root):
        store = Store(root)
        try:
            run_id, previous = store.start(request, action='propose', method='create', owner='evolve-propose')
            if previous is not None:
                return previous
            try:
                change_id, revision_id, task_id = identifier(), identifier(), identifier()
                owner = data.get('responsible_action', 'apply')
                baseline = {p: current_digest(task_path(root, p, owner)) for p in data['scope']}
                with store.transaction() as connection:
                    code = 'CHG-' + now()[:10].replace('-', '') + '-' + change_id[:8]
                    acceptance = [{'id': store.number('AC'), 'text': text, 'required': True}
                                  for text in data['acceptance']]
                    check_basis = config.get('verification', {}).get('checks', [])
                    check_basis = [c for c in check_basis if c['id'] in data['required_checks']]
                    analysis_basis = None
                    if data.get('analysis_basis') is not None:
                        from .analysis import repair_basis
                        analysis_basis = repair_basis(connection, data['analysis_basis'], check_basis, root=root)
                    definition = {'local_key': 'TASK-001', 'title': data['title'],
                                  'completion': data['completion'], 'scope': data['scope'],
                                  'baseline': baseline, 'acceptance': acceptance,
                                  'required_checks': data['required_checks'], 'checks_basis': check_basis,
                                  'responsible_action': owner, 'required_deliverables': data['scope']}
                    from .external_work import definition_fields
                    definition.update(definition_fields(root, data))
                    from .knowledge_impact import freeze as freeze_knowledge_impact
                    knowledge_impact = freeze_knowledge_impact(connection, root, data, data['scope'])
                    if knowledge_impact is not None:
                        definition['knowledge_impact'] = knowledge_impact
                    definition['spec_delta'] = 'none' if owner == 'apply' else 'owner_candidate_required'
                    if analysis_basis:
                        definition['analysis_basis'] = data['analysis_basis']
                        if analysis_basis[1]['analysis'].get('symptom') is not None:
                            definition['symptom_before'] = analysis_basis[1]['analysis']['symptom']
                        store.link_source(run_id, analysis_basis[0]['id'], analysis_basis[0]['result_digest'], 'repair_analysis_basis')
                    definition_digest = digest(canonical(definition))
                    plan_digest = store.blob(data['plan'].encode('utf-8'))
                    connection.execute('INSERT INTO changes VALUES (?,?,?,?,?,?,?,?)',
                                       (change_id, code, data['title'], 'modification', 'simple', 'ready', revision_id, 1))
                    connection.execute('INSERT INTO plan_revisions VALUES (?,?,?,?,?,?,?,?,?,?)',
                                       (revision_id, change_id, 1, plan_digest, definition_digest,
                                        canonical(data['scope']).decode(), canonical(acceptance).decode(),
                                        canonical(check_basis).decode(), now(), None))
                    connection.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)',
                                       (task_id, change_id, revision_id, canonical(definition).decode(),
                                        definition_digest, 'todo', 1, None))
                    store.event(run_id, 'plan_presented', {'revision_id': revision_id,
                                'plan_digest': plan_digest, 'source': data['presentation']['source']})
                    plan_ref = store.artifact(None, 'short_plan', data['plan'].encode('utf-8'), run_id,
                                              data['presentation']['source'])
                    for name in data['scope']:
                        path = task_path(root, name, owner)
                        if path.is_file():
                            formal = store.one("SELECT current_version FROM artifacts WHERE path=? AND kind='knowledge'", (name,))
                            if formal:
                                store.event(run_id, 'formal_context_observed', {'path': name,
                                            'registered_version': formal['current_version'], 'actual_digest': current_digest(path)})
                            else:
                                store.artifact(name, 'source_observation', path.read_bytes(), run_id, 'workspace_observation')
                return store.finish(run_id, {'committed': True, 'outcome': 'planned', 'change_id': change_id,
                                    'change_code': code, 'revision_id': revision_id, 'revision': 1,
                                    'definition_digest': definition_digest, 'plan_digest': plan_digest,
                                    'task_id': task_id, 'task_version': 1, 'change_version': 1,
                                    'acceptance': acceptance, 'plan_ref': plan_ref, 'accepted': False})
            except EvolveError as error:
                if not store.run_started(run_id):
                    error.committed = True
                    raise
                store.finish(run_id, {'committed': True, 'outcome': 'blocked',
                                      'error': {'code': error.code, 'message': str(error)}}, status='blocked')
                error.committed = True
                raise
        finally:
            store.close()
