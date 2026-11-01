"""Scoped path maintenance: derive every changed byte from retained identical source bytes."""
import copy
import json
import os
import re

from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .workspace import current_digest, inside
from .project_knowledge import DIMENSIONS, catalog_view, document_verified, nonempty


def candidate(store, data):
    path = nonempty(data.get('path'), 'facts.path')
    move = data.get('fact_update')
    if not isinstance(move, dict) or move.get('kind') != 'path_move':
        raise EvolveError('KNOWLEDGE_FACTS', 'Only verified identical-byte path relocation is supported')
    old, new = move.get('from_path'), move.get('to_path')
    for name in (old, new):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_./\-]+', name) or any(p in ('.', '..') for p in name.split('/')):
            raise EvolveError('KNOWLEDGE_FACTS', 'Path movement must use unambiguous project-relative path tokens')
        if inside(store.root, name).relative_to(store.root).parts[0] in ('.git', '.evolve-local', '.codex', '.claude', '.agents', 'evolve'):
            raise EvolveError('KNOWLEDGE_FACTS', 'Control, formal and host files are outside factual movement')
    if old == new or current_digest(inside(store.root, old)) is not None:
        raise EvolveError('KNOWLEDGE_FACTS', 'Original path must actually have moved')
    rows = [d for d in catalog_view(store.connection, store.root)['documents'] if d['active'] and d['path'] == path]
    if not rows or rows[0]['kind'] not in ('codemap', 'project', 'development') or rows[0]['mode'] != 'managed':
        raise EvolveError('KNOWLEDGE_FACTS', 'Only managed navigation documents support factual path maintenance')
    doc = rows[0]
    if doc['registered_digest'] != data.get('expected_digest') or doc['current_digest'] not in (doc['registered_digest'], data.get('_applying_digest')):
        raise EvolveError('FILE_CONFLICT', 'Navigation baseline changed', exit_code=3)
    if not document_verified(store.connection, {**doc, 'current_digest': doc['registered_digest']}):
        raise EvolveError('KNOWLEDGE_FACTS', 'Automatic facts retain a safely verified baseline; pending or failed content needs explicit review', exit_code=3)
    retained = next((s for s in doc['sources'] if s['path'] == old), None)
    if not retained or current_digest(inside(store.root, new)) != retained['expected_digest']:
        raise EvolveError('KNOWLEDGE_FACTS', 'Destination bytes differ from the recorded original source', exit_code=3)
    baseline = store.one('SELECT content FROM blobs WHERE digest=?', (doc['registered_digest'],))[0].decode()
    prose = re.sub(r'`[^`\n]+`', '', baseline)
    prose = re.sub(r'\]\([^)]+\)', ']', prose)
    if re.search(r'(?<![A-Za-z0-9_./-])' + re.escape(old) + r'(?![A-Za-z0-9_./-])', prose):
        raise EvolveError('KNOWLEDGE_FACTS', 'Path references in prose need an explicit content review')
    content = baseline.replace('`' + old + '`', '`' + new + '`')
    old_link = os.path.relpath(inside(store.root, old), inside(store.root, path).parent).replace(os.sep, '/')
    new_link = os.path.relpath(inside(store.root, new), inside(store.root, path).parent).replace(os.sep, '/')
    content = content.replace('](' + old_link + ')', '](' + new_link + ')')
    if content == baseline:
        raise EvolveError('KNOWLEDGE_FACTS', 'There is no supported exact path reference to maintain')
    diagrams = re.findall(r'```mermaid\s*\n(.*?)```', baseline, re.S)
    if diagrams != re.findall(r'```mermaid\s*\n(.*?)```', content, re.S):
        raise EvolveError('KNOWLEDGE_FACTS', 'Diagram changes require actual rendering and content review')
    diagram_basis = doc['verification_id'] if diagrams else None
    definition = {k: doc[k] for k in ('kind', 'roles', 'topic', 'scope', 'sections', 'topics', 'mode')}
    definition['sources'] = [{'path': new if s['path'] == old else s['path'], 'expected_digest': s['expected_digest']} for s in doc['sources']]
    definition['replaces'] = []
    definition['template_version'] = 1
    return {'path': path, 'expected_digest': doc['registered_digest'], 'content': content,
            'topic': doc['topic'], 'reason': 'Verified identical-byte relocation of ' + old + ' to ' + new,
            'document': definition, 'fact_update': {'kind': 'path_move', 'from_path': old, 'to_path': new,
                'baseline_version_id': doc['artifact_version_id'], 'source_digest': retained['expected_digest'],
                'baseline_verification_id': doc['verification_id'],
                'diagram_basis_verification_id': diagram_basis},
            'presentation': {'source': 'runtime:scoped-path-maintenance', 'text': content},
            'acceptance': [{'key': key, 'text': 'Only exact navigation path tokens change; source bytes and other text are preserved.'}
                           for key in (*DIMENSIONS, *(['diagrams'] if diagrams else []))]}


def validate_candidate(store, data):
    computed = candidate(store, data)
    for key in ('path', 'expected_digest', 'content', 'document'):
        if data.get(key) != computed[key]:
            raise EvolveError('KNOWLEDGE_FACTS', 'A factual candidate contains unsupported or semantic changes')
    return computed['fact_update']


def authority(store, proposal, request):
    from .knowledge_proposals import metadata
    value = metadata(proposal)
    move = value.get('fact_update') if value else None
    if not move:
        return
    require_effect(request, 'facts_maintenance')
    if proposal['target_path'] not in request['authorization'].get('paths', []):
        raise EvolveError('AUTHORIZATION', 'Factual maintenance needs its exact document path')
    permitted = request['authorization'].get('fact_moves', [])
    if {'from_path': move['from_path'], 'to_path': move['to_path']} not in permitted:
        raise EvolveError('AUTHORIZATION', 'Factual maintenance needs this exact relocation scope')
    content = store.one('SELECT content FROM blobs WHERE digest=?', (proposal['candidate_digest'],))[0].decode()
    computed = candidate(store, {'path': proposal['target_path'], 'expected_digest': proposal['expected_digest'],
                                 'fact_update': move, '_applying_digest': proposal['candidate_digest']})
    if computed['content'] != content or computed['fact_update'] != move or computed['document'] != value['document']:
        raise EvolveError('KNOWLEDGE_FACTS', 'Factual source or exact derived candidate changed', exit_code=3)


def maintain(root, payload):
    """A resumable sequence of ordinary candidate/check/decision/application operations."""
    from .store import Store
    from .workspace import writer_lock
    from .knowledge_proposals import propose_knowledge, check_candidate, review_candidates
    from .formal import apply_knowledge, verify_knowledge
    request = normalize(payload)
    require_effect(request, 'project_records'); require_effect(request, 'knowledge'); require_effect(request, 'facts_maintenance')
    parent = request['request_id']
    def child(stage, data):
        result = copy.deepcopy(request)
        result['request_id'] = digest(canonical({'parent': parent, 'stage': stage}))
        result['authorization_parent_request_id'] = parent
        result['input'] = data
        return result
    proposed_request = child('propose', {})
    with writer_lock(root):
        store = Store(root)
        try:
            existing = store.one('SELECT input_json FROM phase_runs WHERE request_id=? AND workspace_epoch=?',
                                 (proposed_request['request_id'], request['expected_workspace_epoch']))
            if existing:
                prior = json.loads(existing[0])['request']
                data = prior['input']
                if any(request['input'].get(k) != data.get(k) for k in ('path', 'expected_digest')) or request['input'].get('fact_update') != {k: data['fact_update'][k] for k in ('kind', 'from_path', 'to_path')}:
                    raise EvolveError('REQUEST_CONFLICT', 'A factual retry changed its original movement')
            else:
                data = candidate(store, request['input'])
            # No caller-supplied replacement text can enter the generated operation.
            if request['input'].get('content', data['content']) != data['content']:
                raise EvolveError('KNOWLEDGE_FACTS', 'Extra replacement text is outside factual maintenance')
        finally:
            store.close()
    proposed_request['input'] = data
    item = propose_knowledge(root, proposed_request)
    ref = {k: item[k] for k in ('proposal_id', 'proposal_version', 'candidate_digest', 'expected_digest')}
    observations = [{'criterion_key': c['key'], 'status': 'passed', 'observer': 'runtime:exact-path-diff',
                     'basis': ('Mermaid sources are byte-identical; retain actual prior document verification ' + data['fact_update']['diagram_basis_verification_id']
                               if c['key'] == 'diagrams' else 'Compared only derived path tokens and identical source bytes; retained baseline content verification ' + data['fact_update']['baseline_verification_id'])}
                    for c in data['acceptance']]
    check_candidate(root, child('check', {'proposal': ref, 'observations': observations}))
    decision = review_candidates(root, child('review', {'decisions': [{'proposal': ref, 'decision': 'approved',
        'source': request['authorization']['source'], 'text': request['authorization']['text'],
        'reason': 'Scoped factual authorization; deterministic path-only candidate.'}]}))
    result = apply_knowledge(root, child('apply', {'proposal': ref, 'approved_event_id': decision['decisions'][0]['decision_event_id']}))
    checked = verify_knowledge(root, child('verify', {'application_id': result['application_id'], 'observations': observations}))
    return {**result, 'fact_update': data['fact_update'], 'parent_request_id': parent, 'authority': 'scoped_facts',
            'factual_verification': checked}
