"""Exact approved byte edits and recorded application chains; no fuzzy rebasing."""
import json

from .errors import EvolveError
from .knowledge import baseline_path
from .package import digest
from .workspace import current_digest


def render(base, edits):
    result = base
    for edit in reversed(edits):
        if result[edit['start']:edit['end']] != edit['before'].encode():
            raise EvolveError('KNOWLEDGE_CHAIN', 'Approved byte range no longer has its original meaning', exit_code=3)
        result = result[:edit['start']] + edit['after'].encode() + result[edit['end']:]
    return result


def validate_edits(base, content, edits):
    if edits is None:
        return None
    if not isinstance(edits, list) or not edits or any(not isinstance(e, dict) for e in edits):
        raise EvolveError('KNOWLEDGE_PATCH', 'Declare a nonempty list of exact byte edits')
    selected = []
    targets = set()
    for edit in edits:
        if (any(type(edit.get(k)) is not int for k in ('start', 'end')) or not 0 <= edit['start'] <= edit['end'] <= len(base)
                or any(not isinstance(edit.get(k), str) for k in ('before', 'after', 'semantic_target'))
                or not edit['semantic_target'].strip() or edit['semantic_target'] in targets
                or edit['before'] == edit['after']):
            raise EvolveError('KNOWLEDGE_PATCH', 'Each edit needs a distinct semantic target, valid byte range and actual old/new text')
        try:
            base[:edit['start']].decode(); base[:edit['end']].decode()
        except UnicodeDecodeError:
            raise EvolveError('KNOWLEDGE_PATCH', 'Byte offsets cannot split UTF-8 characters')
        targets.add(edit['semantic_target']); selected.append({k: edit[k] for k in ('start', 'end', 'before', 'after', 'semantic_target')})
    selected.sort(key=lambda e: (e['start'], e['end']))
    if any(overlap(a, b) for i, a in enumerate(selected) for b in selected[i + 1:]):
        raise EvolveError('KNOWLEDGE_PATCH', 'A candidate cannot contain overlapping or ambiguous insertions')
    try:
        result = render(base, selected)
    except EvolveError:
        raise EvolveError('KNOWLEDGE_PATCH', 'Declared original bytes differ from the approved base')
    if result != content.encode():
        raise EvolveError('KNOWLEDGE_PATCH', 'Presented full text must exactly equal the declared edits on the approved base')
    return selected


def overlap(left, right):
    if left['start'] == left['end'] or right['start'] == right['end']:
        return max(left['start'], right['start']) <= min(left['end'], right['end'])
    return max(left['start'], right['start']) < min(left['end'], right['end'])


def translated(edits, applied):
    if applied is None:
        raise EvolveError('KNOWLEDGE_CHAIN', 'A full-document replacement cannot prove preservation of an independent old patch', exit_code=3)
    result = []
    for edit in edits:
        shift = 0
        for other in applied:
            if overlap(edit, other) or edit['semantic_target'] == other['semantic_target']:
                raise EvolveError('KNOWLEDGE_CONFLICT', 'Approved ranges or semantic targets conflict; preserve both candidates', exit_code=3)
            if other['end'] <= edit['start']:
                shift += len(other['after'].encode()) - len(other['before'].encode())
        result.append({**edit, 'start': edit['start'] + shift, 'end': edit['end'] + shift})
    return result


def version_chain(connection, first, last):
    from .formal import application_source
    start = connection.execute('SELECT * FROM artifact_versions WHERE id=?', (first,)).fetchone()
    end = connection.execute('SELECT * FROM artifact_versions WHERE id=?', (last,)).fetchone()
    if not start or not end or start['artifact_id'] != end['artifact_id']:
        raise EvolveError('KNOWLEDGE_CHAIN', 'Formal versions do not belong to one actual artifact', exit_code=3)
    origin = connection.execute('SELECT * FROM spec_applications WHERE artifact_version_id=?', (first,)).fetchone()
    if origin:
        if application_source(connection, origin) is None:
            raise EvolveError('KNOWLEDGE_PENDING', 'Original formal application needs safe finalization', exit_code=4)
    elif connection.execute('SELECT status FROM phase_runs WHERE id=?', (start['source_run_id'],)).fetchone()[0] != 'completed':
        raise EvolveError('KNOWLEDGE_PENDING', 'Original formal version needs safe finalization', exit_code=4)
    rows = connection.execute('SELECT * FROM artifact_versions WHERE artifact_id=? ORDER BY rowid', (start['artifact_id'],)).fetchall()
    ids = [v['id'] for v in rows]
    if ids.index(first) > ids.index(last):
        raise EvolveError('KNOWLEDGE_CHAIN', 'Formal history cannot run backwards', exit_code=3)
    before = connection.execute('SELECT content FROM blobs WHERE digest=?', (start['blob_digest'],)).fetchone()[0]
    result = []
    for row in rows[ids.index(first) + 1:ids.index(last) + 1]:
        app = connection.execute('SELECT * FROM spec_applications WHERE artifact_version_id=?', (row['id'],)).fetchone()
        saved = application_source(connection, app) if app else None
        effect = saved.get('effect') if saved else None
        after = connection.execute('SELECT content FROM blobs WHERE digest=?', (row['blob_digest'],)).fetchone()[0]
        predecessor = effect.get('adoption', {}).get('registered_digest', app['baseline_digest']) if effect else None
        if (not effect or predecessor != digest(before) or app['result_digest'] != digest(after)
                or effect['base_digest'] != app['baseline_digest'] or effect['result_digest'] != app['result_digest']):
            raise EvolveError('KNOWLEDGE_CHAIN', 'A formal version has no finalized matching approved application proof', exit_code=4)
        if effect['actual_edits'] is not None and render(before, effect['actual_edits']) != after:
            raise EvolveError('KNOWLEDGE_CHAIN', 'Recorded patch effect does not produce the actual target version', exit_code=4)
        result.append((app, effect)); before = after
    return end, result


def grouped(connection, proposal_ids):
    from .knowledge_proposals import source_facts
    for event in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='knowledge_review_batch' ORDER BY rowid DESC"):
        batch = json.loads(event['payload_json'])['proposal_ids']
        if set(proposal_ids).issubset(batch):
            facts = source_facts(connection, event['run_id'])
            if facts and facts.get('batch_proposals') == batch:
                return True
    return False


def resolve_effect(connection, root, proposal, *, batch_ids=None, target_version=None):
    from .knowledge_proposals import metadata
    meta = metadata(proposal)
    formal = connection.execute("SELECT current_version FROM artifacts WHERE path=? AND kind='knowledge'", (proposal['target_path'],)).fetchone()
    if proposal['owner_skill'] == 'evolve-init' and meta['formal_version_id'] is None:
        existing = connection.execute('SELECT id FROM spec_applications WHERE proposal_id=?', (proposal['id'],)).fetchone()
        if formal and not existing:
            raise EvolveError('BASELINE_EXISTS', 'Another initial candidate already established this formal baseline', exit_code=3)
        content = connection.execute('SELECT content FROM blobs WHERE digest=?', (proposal['candidate_digest'],)).fetchone()[0]
        return {'base_digest': proposal['expected_digest'], 'result_digest': digest(content), 'content': content.decode(),
            'actual_edits': meta.get('edits'), 'chain': [], 'formal_version_id': None,
            'semantic_targets': sorted(e['semantic_target'] for e in (meta.get('edits') or []))}
    if not formal:
        raise EvolveError('KNOWLEDGE_CHAIN', 'Formal artifact mapping is missing', exit_code=3)
    if meta.get('adoption'):
        existing = connection.execute('SELECT artifact_version_id FROM spec_applications WHERE proposal_id=?', (proposal['id'],)).fetchone()
        if formal['current_version'] != meta['formal_version_id'] and (not existing or formal['current_version'] != existing[0]):
            raise EvolveError('KNOWLEDGE_ADOPTION', 'Registered formal authority changed after the external version was presented', exit_code=3)
        content = connection.execute('SELECT content FROM blobs WHERE digest=?', (proposal['candidate_digest'],)).fetchone()[0]
        return {'base_digest': proposal['expected_digest'], 'result_digest': digest(content), 'content': content.decode(),
            'actual_edits': meta.get('edits'), 'chain': [], 'formal_version_id': meta['formal_version_id'], 'adoption': meta['adoption'],
            'semantic_targets': sorted(e['semantic_target'] for e in (meta.get('edits') or []))}
    version, chain = version_chain(connection, meta['formal_version_id'], target_version or formal['current_version'])
    base = connection.execute('SELECT content FROM blobs WHERE digest=?', (version['blob_digest'],)).fetchone()[0]
    edits = meta.get('edits')
    if chain:
        ids = [proposal['id']] + [app['proposal_id'] for app, _ in chain]
        if edits is None:
            raise EvolveError('FILE_CONFLICT', 'A whole-document candidate requires its original exact formal baseline', exit_code=3)
        if not (batch_ids is not None and set(ids).issubset(batch_ids)) and not grouped(connection, ids):
            raise EvolveError('KNOWLEDGE_BATCH', 'Advancing an approved base requires the explicit related proposal batch', exit_code=3)
        for _, effect in chain:
            edits = translated(edits, effect['actual_edits'])
    content = render(base, edits) if edits is not None else connection.execute('SELECT content FROM blobs WHERE digest=?', (proposal['candidate_digest'],)).fetchone()[0]
    return {'base_digest': digest(base), 'result_digest': digest(content), 'content': content.decode(),
        'actual_edits': edits, 'chain': [app['id'] for app, _ in chain], 'formal_version_id': version['id'],
        'semantic_targets': sorted({e['semantic_target'] for e in (edits or [])} |
            {e['semantic_target'] for _, effect in chain for e in (effect['actual_edits'] or [])})}


def review_composition(effect, review):
    if not effect['chain']:
        return
    if (not isinstance(review, dict) or review.get('base_digest') != effect['base_digest'] or review.get('result_digest') != effect['result_digest']
            or review.get('status') != 'passed' or review.get('semantic_targets') != effect['semantic_targets']
            or any(not isinstance(review.get(k), str) or not review[k].strip() for k in ('observer', 'basis'))):
        raise EvolveError('KNOWLEDGE_COMPOSITION', 'Inspect the actual composed text and bind its base, result and semantic targets; unchanged approval is retained', exit_code=3)


def effect_state(connection, root, application, *, physical=None, pending=None):
    from .formal import application_source
    proposal = connection.execute('SELECT * FROM knowledge_proposals WHERE id=?', (application['proposal_id'],)).fetchone()
    formal = connection.execute('SELECT current_version FROM artifacts WHERE path=?', (proposal['target_path'],)).fetchone()
    saved = application_source(connection, application)
    if not saved:
        return {'preserved': False, 'reason': 'source_pending'}
    try:
        last, chain = version_chain(connection, application['artifact_version_id'], formal['current_version'])
        actual = (physical or {}).get(proposal['target_path'], current_digest(baseline_path(root, proposal['target_path'])))
        content = connection.execute('SELECT content FROM blobs WHERE digest=?', (last['blob_digest'],)).fetchone()[0]
        staged = (pending and pending['target_path'] == proposal['target_path']
                  and pending['base_digest'] == last['blob_digest']
                  and actual in (pending['base_digest'], pending['result_digest'])
                  and digest(pending['content'].encode()) == pending['result_digest'])
        if staged:
            if pending['actual_edits'] is None or render(content, pending['actual_edits']) != pending['content'].encode():
                return {'preserved': False, 'reason': 'pending_scope_unproven'}
            content = pending['content'].encode()
        elif actual != last['blob_digest']:
            return {'preserved': False, 'reason': 'external_bytes'}
        own = saved['effect']['actual_edits']
        if (chain or staged) and own is None:
            return {'preserved': False, 'reason': 'whole_document_changed'}
        ranges, shift = [], 0
        for edit in own or []:
            start = edit['start'] + shift
            ranges.append({**edit, 'start': start, 'end': start + len(edit['after'].encode()), 'before': edit['after']})
            shift += len(edit['after'].encode()) - len(edit['before'].encode())
        for _, effect in chain:
            ranges = translated(ranges, effect['actual_edits'])
        if staged:
            ranges = translated(ranges, pending['actual_edits'])
        if any(content[e['start']:e['end']] != e['before'].encode() for e in ranges):
            return {'preserved': False, 'reason': 'approved_target_changed'}
        return {'preserved': True, 'chain': [app['id'] for app, _ in chain], 'current_digest': actual,
                'pending_effect_checked': bool(staged),
                'pending_effect_applied': bool(staged and actual == pending['result_digest'])}
    except EvolveError as error:
        return {'preserved': False, 'reason': error.code}


def dependency_gate(connection, root, proposal, *, physical=None):
    from .knowledge_proposals import metadata
    for reference in metadata(proposal).get('dependencies', []):
        other = connection.execute('SELECT * FROM knowledge_proposals WHERE id=?', (reference['proposal_id'],)).fetchone()
        if not other or any(other[k if k != 'proposal_id' else 'id'] != v for k, v in reference.items() if k != 'proposal_version') or other['version'] != reference['proposal_version']:
            raise EvolveError('KNOWLEDGE_DEPENDENCY', 'Declared candidate dependency changed', exit_code=3)
        app = connection.execute('SELECT * FROM spec_applications WHERE proposal_id=?', (other['id'],)).fetchone()
        if not app or not effect_state(connection, root, app, physical=physical)['preserved']:
            raise EvolveError('KNOWLEDGE_DEPENDENCY', 'Required approved document effect is not safely applied and current', exit_code=3)
