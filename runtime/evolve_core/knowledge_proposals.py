"""Versioned formal-content candidates; review facts are separate from file application."""
import json
from datetime import datetime
from pathlib import Path

from .continuation import sealed_result
from .errors import EvolveError
from .knowledge import baseline_path
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .structured import text
from .work import claim_resources, gate_identity
from .workspace import current_digest, writer_lock

FORMAT = 'knowledge-proposal-v2'
OWNER_METHODS = {'evolve-archive': ('sync', 'propose', 'apply', 'spec', 'sync'),
                 'evolve-init': ('init', 'baseline.propose', 'baseline.apply', 'baseline', 'init'),
                 'evolve-learn': ('learn', 'promote', 'promote', 'rule', 'learn')}


def metadata(proposal):
    owner = OWNER_METHODS.get(proposal['owner_skill'])
    if owner is None or proposal['target_kind'] != owner[3]:
        return None
    value = json.loads(proposal['source_json'])
    return value if isinstance(value, dict) and value.get('format') == FORMAT else None


def reference(proposal):
    return {'proposal_id': proposal['id'], 'proposal_version': proposal['version'],
            'candidate_digest': proposal['candidate_digest'], 'expected_digest': proposal['expected_digest']}


def bound_proposal(store, value):
    if not isinstance(value, dict):
        raise EvolveError('KNOWLEDGE_PROPOSAL', 'Identify the exact presented proposal version and baseline')
    proposal = store.one('SELECT * FROM knowledge_proposals WHERE id=?', (value.get('proposal_id'),))
    if not proposal or metadata(proposal) is None:
        raise EvolveError('KNOWLEDGE_OWNER', 'Select a supported typed formal-content candidate')
    if any(value.get(key) != expected for key, expected in reference(proposal).items()):
        raise EvolveError('KNOWLEDGE_VERSION', 'Prepared candidate reference changed; review its actual version', exit_code=3)
    return proposal


def source_facts(connection, run_id):
    row = connection.execute('SELECT * FROM phase_runs WHERE id=?', (run_id,)).fetchone()
    if not row or (row['action'], row['method']) not in (('sync', 'propose'), ('sync', 'check'), ('sync', 'review'), ('init', 'baseline.propose'), ('learn', 'promote')) or row['status'] == 'started':
        return None
    _, request, result = sealed_result(connection, {'run_id': run_id, 'result_digest': row['result_digest']})
    meta = dict(connection.execute('SELECT key,value FROM project_meta'))
    if request['project_id'] != meta['project_id'] or row['workspace_epoch'] != meta['workspace_epoch']:
        return None
    if row['status'] == 'interrupted':
        recovery = connection.execute("SELECT * FROM phase_runs WHERE id=? AND action='maintain' AND method='recover' AND status='completed'",
            (result.get('finalized_by'),)).fetchone()
        if not recovery:
            return None
        _, _, facts = sealed_result(connection, {'run_id': recovery['id'], 'result_digest': recovery['result_digest']})
        if (result.get('outcome') != 'reconciled_committed_metadata' or facts.get('original_run_id') != run_id
                or not facts.get('original_facts_committed') or facts.get('business_commands_run') is not False):
            return None
        result = result.get('saved_operation_result', {})
    elif row['status'] != 'completed':
        return None
    operation = connection.execute("SELECT result_json FROM operations WHERE run_id=? AND state='committed' AND effect_kind='project_records'", (run_id,)).fetchone()
    if not operation:
        return None
    saved = json.loads(operation[0])
    if any(result.get(key) != value for key, value in saved.items()):
        return None
    if not any(json.loads(event[0]).get('result_digest') == digest(canonical(saved)) for event in connection.execute(
            "SELECT payload_json FROM events WHERE run_id=? AND kind='knowledge_metadata_committed'", (run_id,))):
        return None
    return saved


def latest_check(connection, proposal):
    for event in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='knowledge_candidate_checked' ORDER BY rowid DESC"):
        value = json.loads(event['payload_json'])
        if value.get('proposal_id') == proposal['id']:
            facts = source_facts(connection, event['run_id'])
            return {'run_id': event['run_id'], 'recorded_status': value['status'],
                    'source_pending': facts is None or any(facts.get(key) != value.get(key) for key in ('proposal_id', 'status', 'evidence_ids'))
                        or facts.get('subject_kind') != 'candidate', 'evidence_ids': value['evidence_ids']}
    return None


def require_current(store, proposal, batch_ids=None):
    if proposal['state'] in ('superseded', 'rejected') or proposal['applied_operation_id'] is not None:
        raise EvolveError('KNOWLEDGE_STATE', 'Review the current unapplied candidate; history is retained', exit_code=3)
    if source_facts(store.connection, proposal['created_run_id']) is None:
        raise EvolveError('KNOWLEDGE_PENDING', 'Candidate source needs safe finalization or metadata recovery', exit_code=4)
    from .rules import require_rule_basis
    require_rule_basis(store.connection, proposal)
    from .patches import resolve_effect
    effect = resolve_effect(store.connection, store.root, proposal, batch_ids=batch_ids)
    if current_digest(baseline_path(store.root, proposal['target_path'])) != effect['base_digest']:
        raise EvolveError('FILE_CONFLICT', 'Formal target changed after the candidate was presented', exit_code=3)


def _record(root, payload, method, operation, *, action='sync', owner='evolve-archive'):
    root = Path(root).resolve(); request = normalize(payload); require_effect(request, 'project_records')
    store, run_id, operation_id = None, None, identifier()
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            run_id, previous = store.start(request, action=action, method=method, owner=owner)
            if previous is not None:
                return previous
            claim_resources(store, run_id, operation_id, generation, None, [], 'project_records')
            gate_identity(store, request, run_id)
            with store.transaction() as connection:
                result = operation(store, request['input'], run_id)
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?", (canonical(result).decode(), operation_id))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'knowledge_metadata_committed', {'method': method, 'result_digest': digest(canonical(result))})
            return store.finish(run_id, {'committed': True, 'operation_id': operation_id, **result})
    except EvolveError as error:
        if store is not None and run_id is not None:
            if not store.run_started(run_id):
                error.committed = True
                raise
            with writer_lock(root):
                with store.transaction() as connection:
                    connection.execute("UPDATE operations SET state='failed' WHERE id=? AND state!='committed'", (operation_id,))
                    connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                error.committed = True
        raise
    finally:
        if store is not None:
            store.close()


def adoption_definition(data, formal, *, owner):
    value = data.get('adoption')
    if value is None:
        return None
    if (not isinstance(value, dict) or owner == 'evolve-init' or not formal
            or value.get('formal_version_id') != formal['current_version'] or value.get('registered_digest') != formal['blob_digest']
            or data['expected_digest'] == formal['blob_digest'] or digest(data['content'].encode()) != data['expected_digest']):
        raise EvolveError('KNOWLEDGE_ADOPTION', 'Adopt only the exact observed external text against its actual distinct registered formal version', exit_code=3)
    for field in ('source', 'observer', 'observed_at', 'basis'):
        text(value.get(field), 'adoption.' + field)
    try:
        observed = datetime.fromisoformat(value['observed_at'])
        if observed.utcoffset() is None:
            raise ValueError('missing timezone')
    except ValueError as error:
        raise EvolveError('KNOWLEDGE_ADOPTION', 'External content observation requires its actual time with timezone') from error
    return {key: value[key] for key in ('formal_version_id', 'registered_digest', 'source', 'observer', 'observed_at', 'basis')}


def _propose(store, data, run_id, *, owner='evolve-archive'):
    rule = {}
    if owner == 'evolve-learn':
        from .rules import rule_basis
        rule = rule_basis(store.connection, data)
    elif 'rule_sources' in data or 'rule_scope' in data:
        raise EvolveError('KNOWLEDGE_OWNER', 'Experience rule candidates belong to learn')
    for field in ('topic', 'reason', 'content'):
        text(data.get(field), field)
    if 'expected_digest' not in data:
        raise EvolveError('INPUT', 'Candidate requires its explicit formal target baseline')
    presentation = data.get('presentation')
    if not isinstance(presentation, dict) or presentation.get('text') != data['content'] or not presentation.get('source'):
        raise EvolveError('PRESENTATION', 'Persist the full candidate actually presented and its source')
    criteria = data.get('acceptance')
    if (not isinstance(criteria, list) or not criteria or any(not isinstance(c, dict) for c in criteria)
            or any(not isinstance(c.get('key'), str) or not c['key'].strip() or not isinstance(c.get('text'), str) or not c['text'].strip() for c in criteria)
            or len({c['key'] for c in criteria}) != len(criteria)):
        raise EvolveError('INPUT', 'Content criteria require distinct local keys and actual reviewable text')
    from .formal import delivery_definition, implementation_basis
    delivery = delivery_definition(store, data, owner=OWNER_METHODS[owner][4])
    basis = implementation_basis(store, data, data['path'])
    path = baseline_path(store.root, data.get('path'))
    if current_digest(path) != data['expected_digest']:
        raise EvolveError('FILE_CONFLICT', 'Formal target changed before candidate registration', exit_code=3)
    formal = store.one("SELECT a.current_version,v.blob_digest FROM artifacts a JOIN artifact_versions v ON v.id=a.current_version WHERE a.path=? AND a.kind='knowledge'", (data['path'],))
    initial = owner == 'evolve-init'
    if initial and formal:
        raise EvolveError('BASELINE_EXISTS', 'Initial baseline cannot revise already mapped formal knowledge')
    if not initial and not formal:
        raise EvolveError('KNOWLEDGE_OWNER', 'Initial formal baselines belong to init, not sync')
    adoption = adoption_definition(data, formal, owner=owner)
    if formal and formal['blob_digest'] != data['expected_digest'] and adoption is None:
        raise EvolveError('KNOWLEDGE_EXTERNAL', 'Inspect the external formal edit and form an explicit adoption candidate; it is not the approved baseline', exit_code=3)
    from .patches import version_chain
    if formal:
        version_chain(store.connection, formal['current_version'], formal['current_version'])
    if not initial and adoption is None and digest(data['content'].encode()) == data['expected_digest']:
        binding = store.one('SELECT b.* FROM rule_bindings b JOIN knowledge_proposals p ON p.id=b.proposal_id WHERE p.target_path=? ORDER BY b.rowid DESC LIMIT 1', (data['path'],)) if owner == 'evolve-learn' else None
        if owner != 'evolve-learn' or (binding and json.loads(binding['sources_json']) == rule['rule_sources'] and json.loads(binding['scope_json']) == rule['rule_scope']):
            raise EvolveError('KNOWLEDGE_NO_CHANGE', 'Candidate must change formal content or an actual rule basis')
    from .patches import validate_edits
    original = (store.one('SELECT content FROM blobs WHERE digest=?', (formal['blob_digest'],))[0] if adoption
                else path.read_bytes() if path.is_file() else b'')
    edits = validate_edits(original, data['content'], data.get('edits'))
    dependencies = data.get('dependencies', [])
    if not isinstance(dependencies, list):
        raise EvolveError('KNOWLEDGE_DEPENDENCY', 'Candidate dependencies must be exact proposal references')
    dependencies = [reference(bound_proposal(store, item)) for item in dependencies]
    if len({d['proposal_id'] for d in dependencies}) != len(dependencies):
        raise EvolveError('KNOWLEDGE_DEPENDENCY', 'Candidate dependencies cannot repeat')
    candidate_digest = digest(data['content'].encode())
    all_rows = [row for row in store.connection.execute(
        'SELECT * FROM knowledge_proposals WHERE target_path=? ORDER BY rowid DESC', (data['path'],)) if metadata(row)]
    rows = [row for row in all_rows if row['owner_skill'] == owner]
    matched = next((row for row in rows if metadata(row)['topic'] == data['topic'] or row['candidate_digest'] == candidate_digest), None)
    previous = next((row for row in rows if metadata(row)['family_id'] == metadata(matched)['family_id']), None) if matched else None
    old = metadata(previous) if previous else None
    reconsideration = data.get('reconsideration')
    if previous and previous['applied_operation_id'] is None and previous['state'] not in ('rejected', 'superseded'):
        if source_facts(store.connection, previous['created_run_id']) is None:
            raise EvolveError('KNOWLEDGE_PENDING', 'Safely finalize the existing candidate before replacing it', exit_code=4)
        if (previous['candidate_digest'] == digest(data['content'].encode()) and previous['expected_digest'] == data['expected_digest']
                and old['acceptance'] == criteria and old.get('delivery') == delivery and old.get('implementation_basis') == basis
                and old.get('edits') == edits and old.get('dependencies', []) == dependencies
                and old.get('adoption') == adoption
                and all(old.get(k) == v for k, v in rule.items())):
            store.event(run_id, 'knowledge_candidate_context_added', {'proposal_id': previous['id'], 'reason': data['reason'], 'source': presentation['source']})
            return {'outcome': 'proposal_already_present', **reference(previous), 'path': data['path'], 'applied': False}
    decisions = {}
    for event in store.connection.execute("SELECT payload_json FROM events WHERE kind='knowledge_reviewed' ORDER BY rowid"):
        decision = json.loads(event[0])
        decisions[decision['proposal']['proposal_id']] = decision['decision']
    rejected = previous if previous and previous['state'] == 'rejected' else next(
        (row for row in all_rows if row['candidate_digest'] == candidate_digest and decisions.get(row['id']) == 'rejected'), None)
    if rejected:
        if (not isinstance(reconsideration, dict) or reconsideration.get('proposal_id') != rejected['id']
                or reconsideration.get('proposal_version') != rejected['version']):
            raise EvolveError('KNOWLEDGE_REJECTED', 'A new identity cannot bypass the earlier rejection; preserve explicit reconsideration', exit_code=3)
        for field in ('source', 'text', 'reason'):
            text(reconsideration.get(field), 'reconsideration.' + field)
    proposal_id = identifier(); code = store.number('KP'); delta_id = identifier()
    candidate = store.blob(data['content'].encode()); base = store.blob(original)
    if current_digest(path) != data['expected_digest'] or (not adoption and data['expected_digest'] is not None and base != data['expected_digest']):
        raise EvolveError('FILE_CONFLICT', 'Formal file changed while its base bytes were being retained', exit_code=3)
    value = {'format': FORMAT, 'code': code, 'family_id': old['family_id'] if old else proposal_id,
             'topic': data['topic'], 'reason': data['reason'], 'acceptance': criteria, 'base_digest': base,
             'formal_version_id': formal['current_version'] if formal else None, 'presentation': presentation,
             'supersedes': previous['id'] if previous else None, 'reconsideration': reconsideration,
             'delivery': delivery, 'delta_id': delta_id, 'implementation_basis': basis, 'edits': edits, 'dependencies': dependencies,
             'adoption': adoption, **rule}
    version = previous['version'] + 1 if previous else 1
    if previous and previous['applied_operation_id'] is None:
        store.connection.execute("UPDATE knowledge_proposals SET state='superseded' WHERE id=?", (previous['id'],))
        store.event(run_id, 'knowledge_candidate_superseded', {'proposal_id': previous['id'], 'successor_id': proposal_id, 'reason': data['reason']})
    store.connection.execute('INSERT INTO knowledge_proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        (proposal_id, version, owner, OWNER_METHODS[owner][3], data['path'], data['expected_digest'], candidate, canonical(value).decode(), 'proposed', run_id, None, None))
    kind = 'add' if initial or (edits and all(not e['before'] for e in edits)) else 'remove' if edits and all(not e['after'] for e in edits) else 'modify'
    store.connection.execute('INSERT INTO delta_items VALUES (?,?,?,?,?,?,?,?)',
        (delta_id, proposal_id, kind, data['path'], data['expected_digest'], candidate, canonical(criteria).decode(), old['delta_id'] if old else None))
    store.event(run_id, 'knowledge_candidate_presented', {'proposal_id': proposal_id, 'candidate_digest': candidate, 'proposal_version': version})
    return {'outcome': 'knowledge_proposed', 'proposal_id': proposal_id, 'proposal_version': version, 'code': code,
            'candidate_digest': candidate, 'expected_digest': data['expected_digest'], 'path': data['path'], 'applied': False,
            'supersedes': previous['id'] if previous else None, 'delta_id': delta_id}


def _check(store, data, run_id):
    proposal = bound_proposal(store, data.get('proposal'))
    batch = batch_references(store, data, [reference(proposal)])
    require_current(store, proposal, batch)
    criteria = metadata(proposal)['acceptance']; observations = data.get('observations')
    if (not isinstance(observations, list) or any(not isinstance(o, dict) or not isinstance(o.get('criterion_key'), str) for o in observations)
            or len(observations) != len(criteria) or {o.get('criterion_key') for o in observations} != {c['key'] for c in criteria}):
        raise EvolveError('KNOWLEDGE_CHECK', 'Provide actual content observations for every declared criterion')
    evidence_ids = []
    for observation in observations:
        if observation.get('status') not in ('passed', 'failed', 'blocked'):
            raise EvolveError('KNOWLEDGE_CHECK', 'Content observations need explicit passed, failed or blocked status')
        for field in ('observer', 'basis'):
            text(observation.get(field), 'observation.' + field)
        body = {'subject_kind': 'candidate', **reference(proposal), 'observation': observation, 'observed_at': now(),
                'limitation': 'Actual host content review; no applied target or command success is inferred.'}
        evidence_id = identifier(); blob = store.blob(canonical(body))
        store.connection.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)',
            (evidence_id, run_id, None, 'candidate', observation['observer'], 'candidate-content-review', blob, now(), body['limitation']))
        evidence_ids.append(evidence_id)
    status = 'blocked' if any(o['status'] == 'blocked' for o in observations) else 'failed' if any(o['status'] == 'failed' for o in observations) else 'passed'
    store.event(run_id, 'knowledge_candidate_checked', {'proposal_id': proposal['id'], 'status': status, 'evidence_ids': evidence_ids})
    store.event(run_id, 'knowledge_review_batch', {'proposal_ids': batch})
    return {'outcome': 'candidate_checked', 'subject_kind': 'candidate', **reference(proposal), 'status': status, 'evidence_ids': evidence_ids, 'applied': False, 'batch_proposals': batch}


def batch_references(store, data, defaults):
    values = data.get('batch', defaults)
    if not isinstance(values, list) or not values:
        raise EvolveError('KNOWLEDGE_BATCH', 'Batch contains only exact proposal references')
    selected = [bound_proposal(store, value) for value in values]
    ids = [row['id'] for row in selected]
    if len(set(ids)) != len(ids) or not {v['proposal_id'] for v in defaults}.issubset(ids):
        raise EvolveError('KNOWLEDGE_BATCH', 'Batch must include each selected candidate exactly once')
    if any(source_facts(store.connection, row['created_run_id']) is None for row in selected):
        raise EvolveError('KNOWLEDGE_PENDING', 'Batch candidate sources need safe finalization', exit_code=4)
    return ids


def _review(store, data, run_id):
    decisions = data.get('decisions')
    if not isinstance(decisions, list) or not decisions or any(not isinstance(d, dict) for d in decisions):
        raise EvolveError('KNOWLEDGE_REVIEW', 'Review an explicit nonempty list of candidate decisions')
    batch = batch_references(store, data, [reference(bound_proposal(store, d.get('proposal'))) for d in decisions])
    seen, results = set(), []
    for decision in decisions:
        proposal = bound_proposal(store, decision.get('proposal'))
        if proposal['id'] in seen:
            raise EvolveError('KNOWLEDGE_REVIEW', 'A batch must decide each candidate only once')
        seen.add(proposal['id'])
        selected = decision.get('decision')
        if selected not in ('approved', 'rejected', 'deferred'):
            raise EvolveError('KNOWLEDGE_REVIEW', 'Decision must be approved, rejected or deferred')
        for field in ('source', 'text', 'reason'):
            text(decision.get(field), 'decision.' + field)
        if proposal['state'] in ('superseded', 'rejected') or proposal['applied_operation_id'] is not None:
            raise EvolveError('KNOWLEDGE_STATE', 'Superseded, rejected or applied versions retain their prior decisions', exit_code=3)
        if source_facts(store.connection, proposal['created_run_id']) is None:
            raise EvolveError('KNOWLEDGE_PENDING', 'Candidate source is not safely finalized', exit_code=4)
        check = latest_check(store.connection, proposal)
        if selected == 'approved':
            require_current(store, proposal, batch)
            if not check or check['source_pending'] or check['recorded_status'] != 'passed':
                raise EvolveError('KNOWLEDGE_CHECK', 'Approval requires the latest safely finalized matching candidate content check', exit_code=3)
        event_id = store.event(run_id, 'knowledge_reviewed', {'proposal': reference(proposal), 'decision': selected,
            'source': decision['source'], 'text': decision['text'], 'reason': decision['reason'], 'candidate_check': check})
        store.connection.execute('UPDATE knowledge_proposals SET state=?,approved_event_id=? WHERE id=?',
            (selected, event_id if selected == 'approved' else proposal['approved_event_id'], proposal['id']))
        results.append({**reference(proposal), 'state': selected, 'decision_event_id': event_id, 'applied': False})
    store.event(run_id, 'knowledge_review_batch', {'proposal_ids': batch})
    return {'outcome': 'knowledge_reviewed', 'decisions': results, 'formal_files_written': False, 'batch_proposals': batch}


def propose_knowledge(root, payload, *, owner='evolve-archive'):
    action, method, _, _, _ = OWNER_METHODS[owner]
    return _record(root, payload, method, lambda store, data, run: _propose(store, data, run, owner=owner), action=action, owner=owner)


def check_candidate(root, payload):
    return _record(root, payload, 'check', _check)


def review_candidates(root, payload):
    return _record(root, payload, 'review', _review)


def proposal_views(connection, root, target=None):
    result, decisions = [], {}
    rows = list(connection.execute('SELECT * FROM knowledge_proposals ORDER BY rowid'))
    successors = {}
    for row in rows:
        value = metadata(row)
        if value and value['supersedes']:
            successors.setdefault(value['supersedes'], []).append(reference(row))
    for event in connection.execute("SELECT id,run_id,payload_json FROM events WHERE kind='knowledge_reviewed' ORDER BY rowid"):
        value = json.loads(event['payload_json'])
        decisions.setdefault(value['proposal']['proposal_id'], []).append({'event_id': event['id'], 'source_run_id': event['run_id'],
            'source_pending': source_facts(connection, event['run_id']) is None, **value})
    for row in rows:
        value = metadata(row)
        if value is None or (target and target not in (row['id'], value['code'], value['topic'])):
            continue
        check = latest_check(connection, row)
        item = {**reference(row), 'code': value['code'], 'topic': value['topic'], 'owner_skill': row['owner_skill'],
                'path': row['target_path'], 'state': row['state'], 'applied_operation_id': row['applied_operation_id'],
                'associated_change_id': (value.get('delivery') or {}).get('change_id'), 'superseded_by': successors.get(row['id'], []),
                'supersedes': value['supersedes'], 'latest_decision': decisions.get(row['id'], [None])[-1], 'source_pending': source_facts(connection, row['created_run_id']) is None,
                'latest_candidate_check': check, 'current_matches_baseline': current_digest(baseline_path(root, row['target_path'])) == row['expected_digest']}
        if row['owner_skill'] == 'evolve-learn':
            from .rules import rule_state
            item['rule_state'] = rule_state(connection, row)
        application = connection.execute('SELECT * FROM spec_applications WHERE proposal_id=?', (row['id'],)).fetchone()
        if application:
            from .formal import application_source
            from .patches import effect_state
            item['application'] = {**dict(application), 'source_pending': application_source(connection, application) is None,
                'current_matches': current_digest(baseline_path(root, row['target_path'])) == application['result_digest'],
                'effect_state': effect_state(connection, root, application)}
        if target:
            item['candidate'] = connection.execute('SELECT content FROM blobs WHERE digest=?', (row['candidate_digest'],)).fetchone()[0].decode()
            item['base'] = connection.execute('SELECT content FROM blobs WHERE digest=?', (value['base_digest'],)).fetchone()[0].decode()
            item['definition'] = value
            item['decisions'] = decisions.get(row['id'], [])
            if not application:
                from .patches import resolve_effect
                try:
                    effect = resolve_effect(connection, root, row)
                    item['effective_candidate'] = {**effect, 'current_matches_base': current_digest(baseline_path(root, row['target_path'])) == effect['base_digest']}
                except EvolveError as error:
                    item['effective_candidate'] = {'blocked': True, 'code': error.code, 'message': str(error)}
        result.append(item)
    return result
