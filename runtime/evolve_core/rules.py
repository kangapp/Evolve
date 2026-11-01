"""Exact experience basis and actual formal rule bindings, separate from authority."""
from .errors import EvolveError
from .learning import selected_entry, strings, text
from .package import canonical


def rule_basis(connection, data):
    scope = strings(data.get('rule_scope'), 'rule_scope', nonempty=True)
    sources = data.get('rule_sources')
    if not isinstance(sources, list) or not sources or any(not isinstance(s, dict) for s in sources):
        raise EvolveError('RULE_SOURCE', 'Rule proposals need actual experience versions, support and counterexamples')
    result, seen = [], set()
    for source in sources:
        item = selected_entry(connection, source.get('experience_ref'))
        key = item['experience_ref']['run_id']
        if key in seen:
            raise EvolveError('RULE_SOURCE', 'Do not count the same experience twice as independent support')
        seen.add(key)
        counterexamples = [f['feedback_ref'] for f in item['counterexamples']]
        if source.get('state_ref') != item['state_ref'] or source.get('counterexamples') != counterexamples:
            raise EvolveError('RULE_SOURCE_CHANGED', 'Inspect the exact current experience state and every known counterexample', exit_code=3)
        if (item['state'] not in ('candidate', 'active') or item['pending_counterexamples']
                or item['experience']['cause']['confidence'] != 'observed'
                or not any(f['evidence'] for f in item['sources'] + item['state_sources'])):
            raise EvolveError('RULE_REVIEW_REQUIRED', 'Hypotheses, retired or disputed sources need actual supported review before rule promotion', exit_code=3)
        text(source.get('basis'), 'rule_source.basis')
        result.append({'experience_ref': item['experience_ref'], 'state_ref': item['state_ref'],
                       'counterexamples': counterexamples, 'basis': source['basis']})
    return {'rule_scope': scope, 'rule_sources': result}


def require_rule_basis(connection, proposal):
    if proposal['owner_skill'] != 'evolve-learn':
        return
    from .knowledge_proposals import metadata
    rule_basis(connection, metadata(proposal))


def bind_rule(store, application_id, proposal, artifact_version_id):
    if proposal['owner_skill'] != 'evolve-learn':
        return
    from .knowledge_proposals import metadata
    value = metadata(proposal)
    store.connection.execute('INSERT INTO rule_bindings VALUES (?,?,?,?,?)',
        (application_id, proposal['id'], artifact_version_id,
         canonical(value['rule_sources']).decode(), canonical(value['rule_scope']).decode()))


def rule_state(connection, proposal):
    from .knowledge_proposals import metadata
    value = metadata(proposal)
    result = {'scope': value['rule_scope'], 'sources': value['rule_sources']}
    try:
        require_rule_basis(connection, proposal)
        return {**result, 'applicability': 'supported_basis', 'semantic_validity': 'requires_actual_content_observation'}
    except EvolveError as error:
        return {**result, 'applicability': 'needs_review', 'code': error.code, 'message': str(error)}


def rule_views(connection, root, path):
    from .patches import effect_state
    result = []
    for binding in connection.execute('SELECT * FROM rule_bindings WHERE proposal_id IN (SELECT id FROM knowledge_proposals WHERE target_path=?)', (path,)):
        proposal = connection.execute('SELECT * FROM knowledge_proposals WHERE id=?', (binding['proposal_id'],)).fetchone()
        application = connection.execute('SELECT * FROM spec_applications WHERE id=?', (binding['application_id'],)).fetchone()
        result.append({'application_id': application['id'], 'proposal_id': proposal['id'],
            'artifact_version_id': binding['artifact_version_id'], 'effect_state': effect_state(connection, root, application),
            **rule_state(connection, proposal)})
    return result
