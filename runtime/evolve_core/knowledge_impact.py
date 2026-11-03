"""Plan-bound knowledge impact and post-implementation observations at the archive cutoff."""
import json

from .errors import EvolveError
from .package import canonical, digest
from .project_knowledge import KINDS, catalog_view, document_verified, nonempty, observed_sources
from .workspace import current_digest, inside

REVIEW_VIEWS = tuple(kind for kind in KINDS if kind != 'project')


def freeze_review(root, data):
    values = data.get('knowledge_review')
    if values is None:
        return None
    if not isinstance(values, list) or not values:
        raise EvolveError('KNOWLEDGE_REVIEW', 'Declare grouped observations for all knowledge views')
    result, covered = [], set()
    for item in values:
        if (not isinstance(item, dict) or item.get('result') not in ('changed', 'unchanged', 'unknown', 'not_applicable')
                or not isinstance(item.get('views'), list) or not item['views']
                or any(view not in REVIEW_VIEWS for view in item['views'])
                or len(item['views']) != len(set(item['views'])) or covered & set(item['views'])):
            raise EvolveError('KNOWLEDGE_REVIEW', 'Classify each knowledge view exactly once with an actual basis')
        nonempty(item.get('basis'), 'knowledge_review.basis')
        paths = item.get('source_paths', [])
        if not isinstance(paths, list) or any(not isinstance(name, str) or not name for name in paths):
            raise EvolveError('KNOWLEDGE_REVIEW', 'Knowledge review sources must be explicit project paths')
        sources = {name: current_digest(inside(root, name)) for name in paths}
        if any(value is None for value in sources.values()):
            raise EvolveError('KNOWLEDGE_REVIEW', 'Use existing observed sources; describe absent implementation as unknown or not applicable')
        result.append({'views': item['views'], 'result': item['result'], 'basis': item['basis'],
                       'source_paths': paths, 'source_observations': sources})
        covered.update(item['views'])
    if covered != set(REVIEW_VIEWS):
        raise EvolveError('KNOWLEDGE_REVIEW', 'Unclassified knowledge views: ' + ', '.join(sorted(set(REVIEW_VIEWS) - covered)))
    return result


def review_results(review):
    return {view: item['result'] for item in review or [] for view in item['views']}


def declared_review(connection, revision_id):
    reviews = [json.loads(row[0])['knowledge_review'] for row in connection.execute(
        'SELECT definition_json FROM tasks WHERE revision_id=?', (revision_id,)) if 'knowledge_review' in json.loads(row[0])]
    if reviews and any(value != reviews[0] for value in reviews):
        raise EvolveError('KNOWLEDGE_REVIEW', 'Current tasks disagree on the change knowledge review')
    return reviews[0] if reviews else None


def validate_review_impacts(review, impacts):
    changed = {view for view, result in review_results(review).items() if result == 'changed'}
    if not changed:
        return
    if not isinstance(impacts, list) or any(not isinstance(item, dict) for item in impacts):
        raise EvolveError('KNOWLEDGE_REVIEW', 'Changed views require concrete knowledge_impact entries')
    declared = {view for item in impacts or [] if item['disposition'] in ('required', 'followup') for view in item.get('views', [])}
    if changed - declared:
        raise EvolveError('KNOWLEDGE_REVIEW', 'Changed views need concrete required/followup topics and views: ' + ', '.join(sorted(changed - declared)))


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
        if 'views' in value and (not isinstance(value['views'], list) or any(view not in REVIEW_VIEWS for view in value['views'])
                                 or len(value['views']) != len(set(value['views']))):
            raise EvolveError('KNOWLEDGE_IMPACT', 'Impact views must identify distinct supported knowledge kinds')
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
    planned_review = declared_review(store.connection, revision['id'])
    actual_review = freeze_review(store.root, data) if planned_review is not None else None
    if planned_review is not None and (actual_review is None or review_results(actual_review) != review_results(planned_review)):
        raise EvolveError('KNOWLEDGE_REVIEW', 'Observe every planned knowledge view; changed conclusions require a concrete revision')
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
             'workspace_digest': work_snapshot(store.connection, store.root, revision), 'observations': observed,
             'knowledge_review': actual_review, 'planned_review_digest': digest(canonical(planned_review))}
    store.event(run_id, 'knowledge_impact_assessed', value)
    return {'outcome': 'knowledge_impact_assessed', **value}


def assess(root, payload):
    from .knowledge_proposals import _record
    return _record(root, payload, 'assess', _assess)


def closure_gate(connection, root, change, revision):
    impacts = declared_impacts(connection, revision['id'])
    review = declared_review(connection, revision['id'])
    if not impacts and review is None:
        return
    from .knowledge_proposals import source_facts
    latest = next((json.loads(e['payload_json']) for e in connection.execute(
        "SELECT run_id,payload_json FROM events WHERE kind='knowledge_impact_assessed' ORDER BY rowid DESC")
        if (lambda value: value['change_id'] == change['id'] and value['revision_id'] == revision['id'])(json.loads(e['payload_json']))
        and source_facts(connection, e['run_id']) is not None), None)
    if not latest or latest['definition_digest'] != revision['definition_digest'] or latest['workspace_digest'] != work_snapshot(connection, root, revision):
        raise EvolveError('KNOWLEDGE_INCOMPLETE', 'Assess all knowledge impacts at the current implementation cutoff', exit_code=3)
    if review is not None:
        if latest.get('planned_review_digest') != digest(canonical(review)) or review_results(latest.get('knowledge_review')) != review_results(review):
            raise EvolveError('KNOWLEDGE_INCOMPLETE', 'Knowledge view observations do not match this accepted plan', exit_code=3)
        if any(current_digest(inside(root, name)) != expected for item in latest['knowledge_review']
               for name, expected in item['source_observations'].items()):
            raise EvolveError('KNOWLEDGE_INCOMPLETE', 'Observed knowledge review sources changed after assessment', exit_code=3)
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
