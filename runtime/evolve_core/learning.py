"""Immutable project experience and separate retrieval, decision and result facts."""
from datetime import datetime
import json
from pathlib import Path

from .continuation import sealed_result
from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store
from .work import gate_identity
from .workspace import current_digest, inside, writer_lock


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise EvolveError('LEARNING_INPUT', label + ' must be explicit nonempty text')
    return value


def strings(value, label, *, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise EvolveError('LEARNING_INPUT', label + ' must be an explicit string array')
    return value


def reference(row):
    return {'run_id': row['id'], 'result_digest': row['result_digest']}


def source_facts(connection, ref):
    try:
        row, request, result = sealed_result(connection, ref)
        meta = dict(connection.execute('SELECT key,value FROM project_meta'))
        if request['project_id'] != meta['project_id'] or row['workspace_epoch'] != meta['workspace_epoch']:
            raise EvolveError('LEARNING_SOURCE', 'Source belongs to another project or epoch')
        retained = []
        ids = sorted(set(strings(ref.get('evidence_ids', []), 'evidence_ids')))
        for key in ids:
            evidence = connection.execute('SELECT * FROM evidence WHERE id=? AND source_run_id=?', (key, row['id'])).fetchone()
            blob = connection.execute('SELECT content FROM blobs WHERE digest=?', (evidence['content_digest'],)).fetchone() if evidence else None
            if not evidence or not blob or digest(blob[0]) != evidence['content_digest']:
                raise EvolveError('LEARNING_SOURCE', 'Referenced source evidence is missing or changed')
            retained.append(dict(evidence))
        return {'reference': {**reference(row), 'evidence_ids': ids}, 'action': row['action'],
                'method': row['method'], 'run_status': row['status'], 'recorded_at': row['ended_at'],
                'package_version': row['package_version'], 'package_digest': row['package_digest'],
                'evidence': retained, 'result': result,
                'work': {key: result.get(key, request['input'].get(key)) for key in ('change_id', 'revision_id', 'definition_digest')}}
    except EvolveError as error:
        rejected = (EvolveError('LEARNING_SOURCE', 'Cannot read the exact sealed source: ' + str(error))
                    if error.code in ('CONTINUATION', 'RUN_RESULT_INVALID') else error)
        rejected.input_check_reference = ref
        raise rejected


def catalog(connection):
    entries, decisions, feedback, states = {}, {}, [], []
    try:
        for row in connection.execute("SELECT * FROM phase_runs WHERE action='learn' AND method!='promote' AND status='completed' ORDER BY started_at,id"):
            _, _, result = sealed_result(connection, reference(row))
            kind = result.get('kind')
            if kind == 'experience':
                item = result['experience']
                if item['experience_id'] != row['id']:
                    raise EvolveError('LEARNING_RECORD_INVALID', 'Experience identity does not match its original run')
                sources = [source_facts(connection, ref) for ref in result['sources']]
                entries[row['id']] = {'experience': item, 'experience_ref': reference(row), 'state_ref': reference(row),
                    'recorded_state': 'candidate', 'reviewed_counterexamples': [], 'sources': sources,
                    'state_sources': [], 'applications': [], 'counterexamples': []}
            elif kind == 'decision':
                decisions[row['id']] = {**result, 'decision_ref': reference(row)}
            elif kind == 'feedback':
                source_facts(connection, result['result_source'])
                feedback.append({**result, 'feedback_ref': reference(row)})
            elif kind == 'state':
                states.append({**result, 'state_ref': reference(row)})
            elif kind == 'no_new_learning':
                source_facts(connection, result['source'])
            else:
                raise EvolveError('LEARNING_RECORD_INVALID', 'Unsupported completed learning result')
        state_rows = {item['state_ref']['run_id']: item for item in states}
        children = {}
        for state in states:
            item = entries.get(state['experience_ref']['run_id'])
            previous = state['previous_state_ref']
            predecessor = state_rows.get(previous['run_id'])
            expected = predecessor['state_ref'] if predecessor else item['experience_ref'] if item else None
            if (not item or item['experience_ref'] != state['experience_ref'] or previous != expected
                    or (predecessor and predecessor['experience_ref'] != state['experience_ref'])
                    or previous['run_id'] in children):
                raise EvolveError('LEARNING_RECORD_INVALID', 'Experience state chain is missing or branched')
            children[previous['run_id']] = state
        visited = set()
        for item in entries.values():
            while item['state_ref']['run_id'] in children:
                state = children[item['state_ref']['run_id']]
                if state['state_ref']['run_id'] in visited:
                    raise EvolveError('LEARNING_RECORD_INVALID', 'Experience state chain contains a cycle')
                visited.add(state['state_ref']['run_id'])
                item.update(recorded_state=state['state'], state_ref=state['state_ref'],
                            reviewed_counterexamples=state['reviewed_counterexamples'],
                            state_sources=[source_facts(connection, ref) for ref in state['sources']])
        if len(visited) != len(states):
            raise EvolveError('LEARNING_RECORD_INVALID', 'Experience state chain is disconnected')
        for key, decision in decisions.items():
            item = entries.get(decision['experience_ref']['run_id'])
            if not item or item['experience_ref'] != decision['experience_ref']:
                raise EvolveError('LEARNING_RECORD_INVALID', 'Adoption decision lost its exact experience version')
            item['applications'].append(decision)
        seen = set()
        for result in feedback:
            decision = decisions.get(result['decision_ref']['run_id'])
            if not decision or decision['decision_ref'] != result['decision_ref'] or decision['run_id'] in seen:
                raise EvolveError('LEARNING_RECORD_INVALID', 'Feedback has an invalid or repeated decision source')
            seen.add(decision['run_id'])
            item = entries[decision['experience_ref']['run_id']]
            item['applications'][item['applications'].index(decision)] = {**decision, 'feedback': result}
            if result['outcome'] == 'counterexample':
                item['counterexamples'].append(result)
        for item in entries.values():
            pending = [f for f in item['counterexamples'] if f['run_id'] not in item['reviewed_counterexamples']]
            item['pending_counterexamples'] = pending
            item['state'] = ('needs_review' if pending and item['recorded_state'] != 'retired' else item['recorded_state'])
            item['recommendation_allowed'] = item['state'] in ('candidate', 'active')
            item['formal_rule'] = False
            item['modification_authorization'] = False
        return entries
    except EvolveError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise EvolveError('LEARNING_RECORD_INVALID', 'Cannot reconstruct project experience facts') from error


def search_catalog(connection, query):
    query = text(query, 'query')
    entries = catalog(connection)
    tokens = query.casefold().split()
    matches = []
    for item in entries.values():
        entry = item['experience']
        document = ' '.join([entry[key] for key in ('topic', 'problem', 'advice', 'applicability', 'version_context')] +
                            entry['scope'] + entry['exclusions'] + entry['tags'] + [entry['cause']['statement'], entry['experience_id']]).casefold()
        score = sum(token in document for token in tokens)
        if score:
            matches.append((score, item['experience']['experience_id'], item))
    matches.sort(key=lambda row: (not row[2]['recommendation_allowed'], -row[0], row[1]))
    results = [item for _, _, item in matches[:5]]
    # Changes to ordinary Task records do not invalidate an unchanged experience catalog.
    basis = [{'experience_ref': item['experience_ref'], 'state_ref': item['state_ref'], 'state': item['state'],
              'counterexamples': [ref['feedback_ref'] for ref in item['counterexamples']]} for _, item in sorted(entries.items())]
    observation = {'query': query, 'catalog_digest': digest(canonical(basis)),
                   'matches': [item['experience_ref'] for item in results]}
    incomplete = [{'run_id': row['id'], 'method': row['method'], 'run_status': row['status'],
                   'input_digest': row['input_digest'], 'requires_recovery': row['status'] == 'started'}
                  for row in connection.execute("SELECT id,method,status,input_digest FROM phase_runs WHERE action='learn' AND method!='promote' AND status IN ('started','interrupted')")]
    return {'outcome': 'matched' if results else 'incomplete' if incomplete else 'no_match',
            'query': query, 'results': results, 'incomplete_records': incomplete,
            'search_ref': {**observation, 'digest': digest(canonical(observation))},
            'matched_count': len(matches), 'returned_count': len(results),
            'search_source': 'authoritative_run_scan', 'materialized_index': False,
            'limitations': ['Literal project-local term matching; at most five results; relevance is not validity.']}


def search(root, query):
    from .reading import current_state, history_snapshot
    root = Path(root).resolve()
    text(query, 'query')
    project = current_state(root)
    if project['state'] != 'connected':
        return {'committed': False, 'outcome': 'not_connected', 'results': [], 'formal_context': []}
    with history_snapshot(root) as (connection, meta):
        if meta['checkpoint'] != project['checkpoint']:
            raise EvolveError('PROJECT_CHANGED', 'History changed before experience search', exit_code=3)
        result = search_catalog(connection, query)
    return {**result, 'committed': False, 'run_id': None, 'formal_context': project['knowledge_refs'],
            'pending_knowledge': project['pending_knowledge']}


def selected_entry(connection, ref):
    if not isinstance(ref, dict):
        raise EvolveError('LEARNING_VERSION', 'Select an observed experience version')
    item = catalog(connection).get(ref.get('run_id'))
    if not item or item['experience_ref'] != ref:
        raise EvolveError('LEARNING_VERSION', 'Experience version is missing or changed')
    return item


def sources(connection, refs):
    if not isinstance(refs, list) or not refs:
        raise EvolveError('LEARNING_SOURCE', 'Experience requires actual sealed work sources')
    facts = [source_facts(connection, ref) for ref in refs]
    if any(f['action'] == 'learn' for f in facts):
        raise EvolveError('LEARNING_SOURCE', 'Citations alone are not independent work evidence')
    return [f['reference'] for f in facts], facts


def experience_result(connection, data, run_id):
    item = data.get('experience')
    if not isinstance(item, dict):
        raise EvolveError('LEARNING_INPUT', 'Experience must describe an actual finding')
    for key in ('topic', 'problem', 'advice', 'applicability', 'version_context', 'observer'):
        text(item.get(key), key)
    for key in ('scope', 'exclusions', 'tags', 'limitations'):
        strings(item.get(key), key, nonempty=key in ('scope', 'limitations'))
    cause = item.get('cause')
    if not isinstance(cause, dict) or cause.get('confidence') not in ('hypothesis', 'observed'):
        raise EvolveError('LEARNING_INPUT', 'Distinguish a cause hypothesis from observed support')
    text(cause.get('statement'), 'cause.statement')
    refs, _ = sources(connection, data.get('sources'))
    content = {key: item[key] for key in ('topic', 'problem', 'advice', 'applicability', 'version_context',
                                        'observer', 'scope', 'exclusions', 'tags', 'limitations', 'cause')}
    source_set = {canonical(ref) for ref in refs}
    for existing in catalog(connection).values():
        old = {key: value for key, value in existing['experience'].items() if key not in ('experience_id', 'state')}
        if old == content and {canonical(fact['reference']) for fact in existing['sources']} == source_set:
            raise EvolveError('LEARNING_DUPLICATE', 'This exact finding and work sources already exist: ' + existing['experience']['experience_id'])
    return {'kind': 'experience', 'outcome': 'experience_recorded', 'sources': refs,
            'experience': {**content, 'experience_id': run_id, 'state': 'candidate'}}


def target_context(connection, data):
    change = connection.execute('SELECT * FROM changes WHERE id=?', (data.get('change_id'),)).fetchone()
    if not change or change['state'] == 'archived' or change['current_revision'] != data.get('revision_id'):
        raise EvolveError('LEARNING_TARGET', 'Adoption needs the actual open work revision')
    tasks = connection.execute('SELECT * FROM tasks WHERE change_id=? AND revision_id=?', (change['id'], change['current_revision'])).fetchall()
    selected = [t for t in tasks if t['definition_digest'] == data.get('definition_digest')
                and (data.get('task_id') is None or t['id'] == data['task_id'])]
    if len(selected) != 1:
        raise EvolveError('LEARNING_TARGET', 'Adoption must bind one actual current Task definition')
    return json.loads(selected[0]['definition_json'])


def decision_result(connection, root, data):
    item = selected_entry(connection, data.get('experience_ref'))
    observation = data.get('search_ref')
    if not isinstance(observation, dict):
        raise EvolveError('LEARNING_RETRIEVAL', 'Preserve the actual search observation before a decision')
    actual = search_catalog(connection, observation.get('query'))
    if observation != actual['search_ref'] or item['experience_ref'] not in observation['matches']:
        raise EvolveError('LEARNING_RETRIEVAL', 'Search result changed or did not retrieve this experience')
    decision = data.get('decision')
    if decision not in ('adopted', 'rejected', 'not_used'):
        raise EvolveError('LEARNING_INPUT', 'Record retrieval separately from actual adoption or rejection')
    if decision == 'adopted' and item['state'] in ('needs_review', 'retired'):
        raise EvolveError('LEARNING_REVIEW_REQUIRED', 'This experience needs review before use as a recommendation')
    text(data.get('applicability_basis'), 'applicability_basis')
    strings(data.get('limitations'), 'limitations', nonempty=True)
    definition = target_context(connection, data)
    expected = data.get('observed_files')
    if not isinstance(expected, dict) or not expected or not set(expected).issubset(definition['scope']):
        raise EvolveError('LEARNING_TARGET', 'Recheck actual target files within the work scope')
    for name, value in expected.items():
        if value != current_digest(inside(root, name)):
            raise EvolveError('LEARNING_TARGET', 'Target file observation changed before the decision')
    return {'kind': 'decision', 'outcome': 'decision_recorded', 'experience_ref': item['experience_ref'],
            'observed_state_ref': item['state_ref'], 'observed_state': item['state'],
            'search_ref': actual['search_ref'], 'decision': decision, 'change_id': data['change_id'],
            'revision_id': data['revision_id'], 'definition_digest': data['definition_digest'],
            'observed_files': expected, 'applicability_basis': data['applicability_basis'],
            'limitations': data['limitations'], 'effect': 'unknown', 'formal_rule': False,
            'modification_authorization': False}


def feedback_result(connection, data):
    row, _, decision = sealed_result(connection, data.get('decision_ref'))
    if row['action'] != 'learn' or row['method'] != 'review' or decision.get('kind') != 'decision':
        raise EvolveError('LEARNING_FEEDBACK', 'Select the actual saved adoption decision')
    entries = catalog(connection)
    item = entries.get(decision['experience_ref']['run_id'])
    if not item or any(a['run_id'] == row['id'] and a.get('feedback') for a in item['applications']):
        raise EvolveError('LEARNING_FEEDBACK', 'Feedback is already recorded or its experience is unavailable')
    outcome = data.get('outcome')
    if outcome not in ('helped', 'not_helped', 'unknown', 'counterexample'):
        raise EvolveError('LEARNING_INPUT', 'Feedback must state effect or unknown explicitly')
    if outcome in ('helped', 'not_helped') and decision['decision'] != 'adopted':
        raise EvolveError('LEARNING_FEEDBACK', 'A retrieved or rejected suggestion was not adopted')
    source = source_facts(connection, data.get('result_source'))
    if source['action'] not in ('apply', 'verify') or any(source['work'].get(key) != decision[key] for key in ('change_id', 'revision_id', 'definition_digest')):
        raise EvolveError('LEARNING_FEEDBACK', 'Effect evidence belongs to another work definition')
    source_row = connection.execute('SELECT started_at FROM phase_runs WHERE id=?', (data['result_source']['run_id'],)).fetchone()
    if source_row['started_at'] < row['ended_at']:
        raise EvolveError('LEARNING_FEEDBACK', 'Outcome predates the saved adoption decision')
    text(data.get('basis'), 'basis')
    strings(data.get('limitations'), 'limitations', nonempty=True)
    return {'kind': 'feedback', 'outcome': outcome, 'decision_ref': reference(row),
            'experience_ref': decision['experience_ref'], 'result_source': source['reference'],
            'basis': data['basis'], 'limitations': data['limitations'],
            'attribution': 'observer_assessment_not_inferred_from_task_status'}


def state_result(connection, data, *, disable=False):
    item = selected_entry(connection, data.get('experience_ref'))
    if data.get('expected_state_ref') != item['state_ref']:
        raise EvolveError('LEARNING_VERSION', 'Experience state changed before review')
    state = 'retired' if disable else data.get('state')
    if state not in ('candidate', 'active', 'needs_review', 'retired'):
        raise EvolveError('LEARNING_INPUT', 'Unknown experience state')
    text(data.get('basis'), 'basis')
    counterexamples = [f['run_id'] for f in item['counterexamples']]
    reviewed = strings(data.get('reviewed_counterexamples', []), 'reviewed_counterexamples')
    if sorted(reviewed) != sorted(counterexamples):
        raise EvolveError('LEARNING_REVIEW_REQUIRED', 'Review every recorded counterexample explicitly')
    refs, facts = sources(connection, data.get('sources'))
    if state == 'active' and (item['experience']['cause']['confidence'] == 'hypothesis'
                             or not any(f['evidence'] for f in facts)):
        raise EvolveError('LEARNING_REVIEW_REQUIRED', 'Active experience needs scoped observed support; a business hypothesis stays candidate')
    if state == 'active' and counterexamples:
        last = max(connection.execute('SELECT ended_at FROM phase_runs WHERE id=?', (key,)).fetchone()[0] for key in counterexamples)
        cutoff = datetime.fromisoformat(last)
        fresh = False
        for fact in facts:
            for evidence in fact['evidence']:
                try:
                    observed = datetime.fromisoformat(evidence['observed_at'])
                except (TypeError, ValueError):
                    continue
                fresh |= observed.utcoffset() is not None and observed > cutoff
        if not fresh:
            raise EvolveError('LEARNING_REVIEW_REQUIRED', 'Support needs an actual new observation, not a newer archive receipt')
    return {'kind': 'state', 'outcome': 'state_reviewed', 'experience_ref': item['experience_ref'],
            'previous_state_ref': item['state_ref'], 'state': state, 'sources': refs,
            'reviewed_counterexamples': counterexamples, 'basis': data['basis'],
            'formal_rule': False, 'user_approval': 'not_implied'}


def learn(root, payload, *, method):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    if method == 'promote':
        if request['input'].get('stage') == 'propose':
            from .knowledge_proposals import propose_knowledge
            return propose_knowledge(root, payload, owner='evolve-learn')
        if request['input'].get('stage') == 'apply':
            from .formal import apply_knowledge
            return apply_knowledge(root, payload, owner='evolve-learn')
        raise EvolveError('LEARNING_INPUT', 'Rule promotion must explicitly choose propose or apply stage')
    with writer_lock(root):
        store = Store(root)
        run_id = None
        try:
            repeated = store.lookup(request, action='learn', method=method, owner='evolve-learn')
            if repeated is not None:
                return repeated[1]
            run_id, _ = store.start(request, action='learn', method=method, owner='evolve-learn')
            data = request['input']
            with store.transaction() as connection:
                gate_identity(store, request, run_id)
                if method == 'record' or (method == 'retro' and data.get('experience') is not None):
                    result = experience_result(connection, data, run_id)
                    if method == 'retro' and data.get('source') is not None:
                        subject = source_facts(connection, data['source'])
                        if not any(ref['run_id'] == subject['reference']['run_id'] and ref['result_digest'] == subject['reference']['result_digest'] for ref in result['sources']):
                            raise EvolveError('LEARNING_SOURCE', 'The retrospected work must be one of the finding sources')
                elif method == 'retro':
                    fact = source_facts(connection, data.get('source'))
                    if fact['action'] == 'learn':
                        raise EvolveError('LEARNING_SOURCE', 'Retrospection must inspect actual work, not just a learning citation')
                    text(data.get('checked_basis'), 'checked_basis')
                    text(data.get('observer'), 'observer')
                    result = {'kind': 'no_new_learning', 'outcome': 'no_new_learning',
                              'source': fact['reference'], 'checked_basis': data['checked_basis'], 'observer': data['observer']}
                elif method == 'disable':
                    result = state_result(connection, data, disable=True)
                elif method == 'review' and data.get('kind') == 'decision':
                    result = decision_result(connection, root, data)
                elif method == 'review' and data.get('kind') == 'feedback':
                    result = feedback_result(connection, data)
                elif method == 'review' and data.get('kind') == 'state':
                    result = state_result(connection, data)
                else:
                    raise EvolveError('LEARNING_INPUT', 'Choose an explicit learning method and review kind')
                refs = list(result.get('sources', []))
                for key in ('source', 'experience_ref', 'decision_ref', 'result_source', 'previous_state_ref'):
                    if result.get(key):
                        refs.append(result[key])
                unique = {(ref['run_id'], ref['result_digest']) for ref in refs}
                for source_id, source_digest in unique:
                    store.link_source(run_id, source_id, source_digest, 'learning_' + result['kind'])
            return store.finish(run_id, {'committed': True, **result})
        except EvolveError as error:
            if run_id is not None:
                if store.run_started(run_id):
                    if hasattr(error, 'input_check_reference'):
                        with store.transaction():
                            store.rejected_source(run_id, error.input_check_reference, 'learning_' + method, error)
                    store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'error': {'code': error.code, 'message': str(error)}}, status='blocked')
                error.committed = True
            raise
        except OSError as error:
            raise EvolveError('LEARNING_INCOMPLETE', 'Learning record receipt requires inspection; do not infer completed learning',
                              exit_code=4, committed=run_id is not None) from error
        finally:
            store.close()


def learning_status(connection, source_run_id):
    try:
        entries = catalog(connection)
        related = [item['experience_ref'] for item in entries.values() if any(f['reference']['run_id'] == source_run_id for f in item['sources'])]
        checked = []
        for row in connection.execute("SELECT * FROM phase_runs WHERE action='learn' AND status='completed'"):
            _, _, result = sealed_result(connection, reference(row))
            if result.get('kind') == 'no_new_learning' and result['source']['run_id'] == source_run_id:
                source_facts(connection, result['source'])
                checked.append(reference(row))
        return {'status': 'recorded' if related else 'no_new_learning' if checked else 'pending',
                'experiences': related, 'checked_no_new_learning': checked}
    except EvolveError as error:
        return {'status': 'unavailable', 'error': {'code': error.code, 'message': str(error)}}


def work_learning(connection, change_id):
    """Restore prior adoption separately from the current suggestion's validity."""
    try:
        applications = []
        for item in catalog(connection).values():
            for decision in item['applications']:
                if decision['change_id'] == change_id:
                    applications.append({'experience': item['experience'], 'experience_ref': item['experience_ref'],
                        'current_state': item['state'], 'current_state_ref': item['state_ref'],
                        'recommendation_allowed': item['recommendation_allowed'],
                        'state_changed_since_decision': decision['observed_state_ref'] != item['state_ref'] or bool(item['pending_counterexamples']),
                        'decision': decision})
        return {'status': 'observed', 'applications': applications}
    except EvolveError as error:
        return {'status': 'unavailable', 'error': {'code': error.code, 'message': str(error)}}
