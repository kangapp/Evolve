"""Initial formal baseline: presented candidate, concrete approval, actual application."""
import json
from pathlib import Path

from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store, identifier
from .work import claim_resources, gate_identity, require_bound_targets
from .workspace import (current_digest, finish_journal, inside, install_files,
                        prepare_files, writer_lock)


def baseline_path(root, name):
    path = inside(root, name)
    relative = path.relative_to(Path(root).resolve())
    resolved = path.resolve().relative_to(Path(root).resolve())
    excluded = {'.git', '.evolve-local', '.codex', '.claude', '.agents'}
    if path.suffix != '.md' or not relative.parts or not resolved.parts or relative.parts[0] in excluded or resolved.parts[0] in excluded:
        raise EvolveError('KNOWLEDGE_PATH', 'A formal baseline must be a project Markdown file outside control/host configuration')
    return path


def propose_baseline(root, payload):
    if isinstance(payload, dict) and isinstance(payload.get('input'), dict) and any(key in payload['input'] for key in ('acceptance', 'delivery', 'edits', 'topic', 'adoption')):
        from .knowledge_proposals import propose_knowledge
        return propose_knowledge(root, payload, owner='evolve-init')
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    data = request['input']
    if not isinstance(data.get('content'), str) or not data['content'].strip() or 'expected_digest' not in data:
        raise EvolveError('INPUT', 'Baseline candidate needs actual content and its explicit target baseline')
    path = baseline_path(root, data.get('path'))
    presentation = data.get('presentation')
    if not isinstance(presentation, dict) or presentation.get('text') != data['content'] or not presentation.get('source'):
        raise EvolveError('PRESENTATION', 'Present exact candidate content and preserve its source')
    with writer_lock(root):
        store = Store(root)
        try:
            run_id, previous = store.start(request, action='init', method='baseline.propose', owner='evolve-init')
            if previous is not None:
                return previous
            try:
                if current_digest(path) != data['expected_digest']:
                    raise EvolveError('FILE_CONFLICT', 'Baseline target changed before proposal registration', exit_code=3)
                if store.one("SELECT id FROM artifacts WHERE path=? AND kind='knowledge'", (data['path'],)):
                    raise EvolveError('BASELINE_EXISTS', 'Existing formal knowledge revisions belong to sync, not initial init')
                proposal_id = identifier()
                with store.transaction() as connection:
                    candidate_digest = store.blob(data['content'].encode('utf-8'))
                    connection.execute('INSERT INTO knowledge_proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                                       (proposal_id, 1, 'evolve-init', 'baseline', data['path'], data['expected_digest'],
                                        candidate_digest, canonical({'format': 'initial-presentation-v1', 'presentation': presentation}).decode(), 'proposed', run_id, None, None))
                    store.event(run_id, 'baseline_candidate_presented', {'proposal_id': proposal_id,
                                'candidate_digest': candidate_digest, 'target_path': data['path'], 'source': presentation['source']})
                return store.finish(run_id, {'committed': True, 'outcome': 'baseline_proposed', 'proposal_id': proposal_id,
                                    'proposal_version': 1, 'candidate_digest': candidate_digest,
                                    'expected_digest': data['expected_digest'], 'path': data['path'], 'applied': False})
            except EvolveError as error:
                if not store.run_started(run_id):
                    error.committed = True
                    raise
                store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                error.committed = True
                raise
        finally:
            store.close()


def apply_baseline(root, payload):
    if isinstance(payload, dict) and isinstance(payload.get('input'), dict) and payload['input'].get('proposal'):
        from .formal import apply_knowledge
        return apply_knowledge(root, payload, owner='evolve-init')
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    require_effect(request, 'knowledge')
    store, run_id, operation_id = None, None, identifier()
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            run_id, previous = store.start(request, action='init', method='baseline.apply', owner='evolve-init')
            if previous is not None:
                return previous
            data = request['input']
            proposal = store.one('SELECT * FROM knowledge_proposals WHERE id=?', (data.get('proposal_id'),))
            if not proposal or proposal['owner_skill'] != 'evolve-init' or proposal['target_kind'] != 'baseline':
                raise EvolveError('KNOWLEDGE_OWNER', 'Only init-owned initial baseline proposals can use this path')
            from .knowledge_proposals import metadata
            if metadata(proposal) is not None:
                raise EvolveError('KNOWLEDGE_APPROVAL', 'Typed baseline requires its checked exact proposal reference and recorded decision')
            if proposal['state'] not in ('proposed', 'approved'):
                raise EvolveError('KNOWLEDGE_STATE', 'Proposal is rejected, deferred, superseded or already applied', exit_code=3)
            approval = data.get('approval')
            expected = {'proposal_version': proposal['version'], 'candidate_digest': proposal['candidate_digest'],
                        'expected_digest': proposal['expected_digest']}
            if not isinstance(approval, dict) or any(approval.get(k) != v for k, v in expected.items()) or not approval.get('source') or not approval.get('text'):
                raise EvolveError('KNOWLEDGE_APPROVAL', 'Approval must identify this exact candidate version and target baseline')
            if proposal['target_path'] not in request['authorization'].get('paths', []):
                raise EvolveError('AUTHORIZATION', 'Knowledge application target is outside explicit authorization')
            path = baseline_path(root, proposal['target_path'])
            if proposal['applied_operation_id'] is not None:
                return store.finish(run_id, {'committed': True, 'outcome': 'already_applied',
                                    'proposal_id': proposal['id'], 'operation_id': proposal['applied_operation_id'],
                                    'actual_digest': current_digest(path),
                                    'current_matches': current_digest(path) == proposal['candidate_digest']})
            if store.one("SELECT id FROM artifacts WHERE path=? AND kind='knowledge'", (proposal['target_path'],)):
                raise EvolveError('BASELINE_EXISTS', 'Another initial application already established this formal authority', exit_code=3)
            if current_digest(path) != proposal['expected_digest']:
                raise EvolveError('FILE_CONFLICT', 'Formal target changed after candidate presentation', exit_code=3)
            content = store.one('SELECT content FROM blobs WHERE digest=?', (proposal['candidate_digest'],))[0]
            claim_resources(store, run_id, operation_id, generation, None, [proposal['target_path']], 'knowledge')
            with store.transaction() as connection:
                approval_id = store.event(run_id, 'knowledge_approved', {'proposal_id': proposal['id'], **expected,
                                          'approval': approval})
                connection.execute("UPDATE knowledge_proposals SET state='approved',approved_event_id=? WHERE id=?",
                                   (approval_id, proposal['id']))
            gate_identity(store, request, run_id)
            journal = prepare_files(root, operation_id, [{'path': proposal['target_path'],
                                    'expected_digest': proposal['expected_digest'], 'content': content.decode('utf-8')}])
            with store.transaction() as connection:
                connection.execute('UPDATE operations SET journal_path=? WHERE id=?',
                                   ('.evolve-local/control/operations/' + operation_id + '.json', operation_id))
            def application_gate():
                gate_identity(store, request, run_id)
                require_bound_targets(store, operation_id, [proposal['target_path']])
            application_gate()
            install_files(root, journal, before_write=application_gate)
            if current_digest(path) != proposal['candidate_digest']:
                raise EvolveError('NEEDS_RECOVERY', 'Actual formal file does not match approved candidate', exit_code=4)
            with store.transaction() as connection:
                actual = store.artifact(proposal['target_path'], 'knowledge', path.read_bytes(), run_id, 'evolve-init:approved-baseline')
                connection.execute('UPDATE knowledge_proposals SET applied_operation_id=? WHERE id=?', (operation_id, proposal['id']))
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?",
                                   (canonical({'proposal_id': proposal['id'], 'artifact': actual}).decode(), operation_id))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'knowledge_applied', {'proposal_id': proposal['id'], 'artifact': actual,
                                                         'approved_event_id': approval_id})
            finish_journal(root, journal)
            return store.finish(run_id, {'committed': True, 'outcome': 'baseline_applied', 'proposal_id': proposal['id'],
                                'operation_id': operation_id, 'artifact': actual, 'actual_digest': current_digest(path)})
    except (EvolveError, OSError) as error:
        if store is not None and run_id is not None:
            if not store.run_started(run_id):
                if isinstance(error, EvolveError):
                    error.committed = True
                    raise
                raise EvolveError('NEEDS_RECOVERY', 'Knowledge facts are saved but their receipt failed', exit_code=4, committed=True)
            with writer_lock(root):
                path = inside(root, '.evolve-local/control/operations/' + operation_id + '.json')
                pending = path.exists() and json.loads(path.read_text()).get('state') != 'committed'
                with store.transaction() as connection:
                    connection.execute('UPDATE operations SET state=? WHERE id=?', ('needs_recovery' if pending else 'failed', operation_id))
                    if not pending:
                        connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    store.event(run_id, 'knowledge_application_interrupted', {'writer_stopped': True, 'message': str(error)})
                if not pending:
                    store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                if isinstance(error, EvolveError):
                    error.committed = True
                    raise
                raise EvolveError('NEEDS_RECOVERY', 'Knowledge file application requires reconciliation', exit_code=4, committed=True)
        raise
    finally:
        if store is not None:
            store.close()
