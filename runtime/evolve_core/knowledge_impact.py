"""Plan-bound knowledge impact and post-implementation observations at the archive cutoff."""
import json

from .errors import EvolveError
from .package import canonical, digest
from .project_knowledge import catalog_view, document_verified, nonempty, observed_sources
from .workspace import current_digest, inside


def freeze(connection, root, data, scope):
    enabled = connection.execute("SELECT id FROM events WHERE kind IN ('knowledge_survey_recorded','knowledge_document_applied') LIMIT 1").fetchone()
    values = data.get('knowledge_impact')
    if values is None and not enabled:
        return None
    if not isinstance(values, list):
        raise EvolveError('KNOWLEDGE_IMPACT', 'Managed projects declare knowledge_impact, including an explicit empty list')
    docs = [d for d in catalog_view(connection, root)['documents'] if d['active']]
    scoped_paths = [inside(root, p).resolve() for p in scope]
    related = {d['topic'] for d in docs if any(
        inside(root, name).resolve() == scoped or scoped in inside(root, name).resolve().parents
        for name in [d['path'], *(s['path'] for s in d['sources'])] for scoped in scoped_paths)}
    result, seen = [], set()
    for value in values:
        if not isinstance(value, dict) or value.get('disposition') not in ('required', 'followup', 'unchanged'):
            raise EvolveError('KNOWLEDGE_IMPACT', 'Knowledge impact needs required, followup or unchanged disposition')
        topic = nonempty(value.get('topic'), 'knowledge_impact.topic')
        nonempty(value.get('reason'), 'knowledge_impact.reason')
        if topic in seen:
            raise EvolveError('KNOWLEDGE_IMPACT', 'Knowledge topics cannot repeat')
        previous = next((d for d in docs if d['topic'] == topic), None)
        target = value.get('target_path')
        if value['disposition'] == 'required':
            if not isinstance(target, str) or not target.startswith('evolve/') or inside(root, target).suffix != '.md':
                raise EvolveError('KNOWLEDGE_IMPACT', 'Required knowledge identifies its evolve/ Markdown target')
        result.append({**value, 'baseline_version_id': previous['artifact_version_id'] if previous else None})
        seen.add(topic)
    if related - seen:
        raise EvolveError('KNOWLEDGE_IMPACT', 'Missing related knowledge topics: ' + ', '.join(sorted(related - seen)))
    return result


def declared_impacts(connection, revision_id):
    result = {}
    for row in connection.execute('SELECT definition_json FROM tasks WHERE revision_id=?', (revision_id,)):
        for item in json.loads(row[0]).get('knowledge_impact', []):
            old = result.get(item['topic'])
            if old and old != item:
                raise EvolveError('KNOWLEDGE_IMPACT', 'Tasks disagree on the same knowledge topic')
            result[item['topic']] = item
    return list(result.values())


def work_snapshot(connection, root, revision):
    from .structured import whole_definition
    from .work import fingerprint
    tasks = connection.execute('SELECT * FROM tasks WHERE revision_id=?', (revision['id'],)).fetchall()
    definition = whole_definition(revision, tasks) if len(tasks) > 1 or json.loads(tasks[0]['definition_json']).get('structured') else json.loads(tasks[0]['definition_json'])
    return fingerprint(root, definition)['digest']


def _assess(store, data, run_id):
    change = store.one('SELECT * FROM changes WHERE id=?', (data.get('change_id'),))
    if not change or change['state'] in ('archived', 'cancelled') or change['current_revision'] != data.get('revision_id'):
        raise EvolveError('KNOWLEDGE_IMPACT', 'Assessment identifies the current active change revision', exit_code=3)
    revision = store.one('SELECT * FROM plan_revisions WHERE id=?', (change['current_revision'],))
    impacts = declared_impacts(store.connection, revision['id'])
    observations = data.get('observations')
    if (not isinstance(observations, list) or any(not isinstance(o, dict) for o in observations)
            or len(observations) != len(impacts) or {o.get('topic') for o in observations} != {i['topic'] for i in impacts}):
        raise EvolveError('KNOWLEDGE_IMPACT', 'Observe each declared knowledge impact')
    docs = [d for d in catalog_view(store.connection, store.root)['documents'] if d['active']]
    observed = []
    for item in impacts:
        observation = next(o for o in observations if o['topic'] == item['topic'])
        nonempty(observation.get('observer'), 'impact.observer'); nonempty(observation.get('basis'), 'impact.basis')
        expected = {'required': 'updated', 'unchanged': 'unchanged', 'followup': 'deferred'}[item['disposition']]
        if observation.get('result') != expected:
            raise EvolveError('KNOWLEDGE_IMPACT', 'A required item cannot be silently deferred or declared unchanged')
        doc = next((d for d in docs if d['topic'] == item['topic']), None)
        if expected == 'updated':
            if (not doc or doc['path'] != item['target_path'] or doc['artifact_version_id'] == item['baseline_version_id']
                    or doc['current_digest'] != doc['registered_digest'] or doc['applicability'] != 'matching_local_bytes'
                    or not document_verified(store.connection, doc)):
                raise EvolveError('KNOWLEDGE_INCOMPLETE', 'Required knowledge lacks a current verified new version', exit_code=3)
        elif expected == 'unchanged' and (not doc or doc['artifact_version_id'] != item['baseline_version_id']
                or not document_verified(store.connection, doc)):
            raise EvolveError('KNOWLEDGE_IMPACT', 'Unchanged observation needs the exact original formal version', exit_code=3)
        sources = observed_sources(store.root, [{'path': s['path'], 'expected_digest': current_digest(inside(store.root, s['path']))} for s in doc['sources']], store) if doc else []
        entry = {**observation, 'path': doc['path'] if doc else None,
                 'application_id': doc['application_id'] if doc else None,
                 'artifact_version_id': doc['artifact_version_id'] if doc else None,
                 'document_digest': doc['current_digest'] if doc else None, 'sources': sources}
        observed.append(entry)
        if expected == 'unchanged':
            store.event(run_id, 'knowledge_applicability_observed', entry)
    value = {'change_id': change['id'], 'revision_id': revision['id'], 'definition_digest': revision['definition_digest'],
             'workspace_digest': work_snapshot(store.connection, store.root, revision), 'observations': observed}
    store.event(run_id, 'knowledge_impact_assessed', value)
    return {'outcome': 'knowledge_impact_assessed', **value}


def assess(root, payload):
    from .knowledge_proposals import _record
    return _record(root, payload, 'assess', _assess)


def closure_gate(connection, root, change, revision):
    impacts = declared_impacts(connection, revision['id'])
    if not impacts:
        return
    from .knowledge_proposals import source_facts
    latest = next((json.loads(e['payload_json']) for e in connection.execute(
        "SELECT run_id,payload_json FROM events WHERE kind='knowledge_impact_assessed' ORDER BY rowid DESC")
        if (lambda value: value['change_id'] == change['id'] and value['revision_id'] == revision['id'])(json.loads(e['payload_json']))
        and source_facts(connection, e['run_id']) is not None), None)
    if not latest or latest['definition_digest'] != revision['definition_digest'] or latest['workspace_digest'] != work_snapshot(connection, root, revision):
        raise EvolveError('KNOWLEDGE_INCOMPLETE', 'Assess all knowledge impacts at the current implementation cutoff', exit_code=3)
    docs = {d['topic']: d for d in catalog_view(connection, root)['documents'] if d['active']}
    for item in latest['observations']:
        if item['result'] == 'deferred':
            continue
        doc = docs.get(item['topic'])
        if (not doc or doc['path'] != item['path'] or doc['artifact_version_id'] != item['artifact_version_id']
                or doc['application_id'] != item.get('application_id') or not document_verified(connection, doc)):
            raise EvolveError('KNOWLEDGE_INCOMPLETE', 'Knowledge authority or its latest actual verification is no longer current', exit_code=3)
        if item['result'] != 'deferred' and (current_digest(inside(root, item['path'])) != item['document_digest'] or any(
                current_digest(inside(root, s['path'])) != s['expected_digest'] for s in item['sources'])):
            raise EvolveError('KNOWLEDGE_INCOMPLETE', 'Knowledge or its observed sources changed after assessment', exit_code=3)
