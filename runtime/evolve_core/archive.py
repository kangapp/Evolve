"""Seal completion at a verified workspace cutoff; never approves knowledge."""
import json
from pathlib import Path

from .errors import EvolveError
from .package import canonical
from .requests import normalize, require_effect
from .store import Store, identifier
from .work import change_context, claim_resources, fingerprint, gate, verification_source, versions
from .workspace import writer_lock


def archive(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    store, run_id, operation_id = None, None, identifier()
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            run_id, previous = store.start(request, action='archive', method='close', owner='evolve-archive')
            if previous is not None:
                return previous
            change, revision, task, definition = change_context(store, request)
            from .revisions import require_accepted
            require_accepted(store.connection, revision)
            if definition.get('structured') and not definition.get('whole_change'):
                raise EvolveError('WHOLE_CHANGE_REQUIRED', 'Archive requires whole-change verification, not one task')
            from .structured import implementation_state
            complete, implementation = implementation_state(store.connection, root, change, revision, task, definition)
            if not complete or not implementation:
                raise EvolveError('INCOMPLETE_TASK', 'Required implementation is not complete', exit_code=3)
            from .formal import verification_applications
            _, documents = verification_applications(store.connection, root, change, revision, task, definition)
            for application_id in documents.values():
                observed = store.one('SELECT v.* FROM spec_applications a JOIN verifications v ON v.id=a.verification_id WHERE a.id=?', (application_id,))
                if not observed or observed['status'] != 'passed' or verification_source(store.connection, observed) is None:
                    raise EvolveError('KNOWLEDGE_VERIFICATION', 'Required document lacks finalized actual target acceptance', exit_code=3)
            from .revisions import eligible_verifications
            observed = eligible_verifications(store.connection, change['id'], revision['id'])
            latest = next((row for row in observed if json.loads(row['items_json']).get('task_id') is None), None)
            if not latest or latest['status'] != 'passed' or request['input'].get('verification_id') != latest['id']:
                raise EvolveError('VERIFICATION', 'Only the latest required passing verification can authorize closure', exit_code=3)
            if any(row['status'] != 'passed' for row in observed
                   if (row['observed_at'], row['id']) > (latest['observed_at'], latest['id'])):
                raise EvolveError('VERIFICATION', 'A newer required task verification is not passing; recheck the whole change', exit_code=3)
            source = verification_source(store.connection, latest)
            if source is None:
                raise EvolveError('VERIFICATION', 'Verification run has not been safely finalized', exit_code=4)
            snapshot = fingerprint(root, definition)
            if snapshot['digest'] != json.loads(latest['fingerprint_json'])['digest']:
                raise EvolveError('STALE_VERIFICATION', 'Workspace or check configuration changed after verification', exit_code=3)
            if implementation['fingerprint']['scope'] != snapshot['scope']:
                raise EvolveError('STALE_IMPLEMENTATION', 'Current outputs no longer match the recorded task results', exit_code=3)
            if json.loads(latest['items_json']).get('unresolved_prior_findings'):
                raise EvolveError('REVIEW_FINDINGS', 'Required review findings remain unresolved', exit_code=3)
            pending = [dict(row) for row in store.connection.execute(
                "SELECT id,target_path,state,version FROM knowledge_proposals WHERE state IN ('proposed','approved','deferred') "
                "AND applied_operation_id IS NULL ORDER BY id")]
            claim_resources(store, run_id, operation_id, generation, change, definition['scope'], 'project_records')
            expected = versions(store, change['id'], task['id'])
            gate(store, request, run_id, operation_id, expected)
            if fingerprint(root, definition)['digest'] != snapshot['digest']:
                raise EvolveError('WORKSPACE_CHANGED', 'Workspace changed at completion cutoff', exit_code=3)
            from .external_work import archive_basis
            archive_basis(store.connection, root, change, revision, task, definition, latest)
            from .knowledge_impact import closure_gate as knowledge_closure_gate
            knowledge_closure_gate(store.connection, root, change, revision)
            with store.transaction() as connection:
                connection.execute("UPDATE changes SET state='archived',row_version=row_version+1 WHERE id=?", (change['id'],))
                store.link_source(run_id, latest['source_run_id'], source['result_digest'], 'completion_basis')
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?",
                                   (canonical({'verification_id': latest['id'], 'fingerprint': snapshot['digest']}).decode(), operation_id))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'change_archived', {'change_id': change['id'], 'verification_id': latest['id'],
                                                      'fingerprint_digest': snapshot['digest'], 'knowledge_approval': 'not_implied'})
            return store.finish(run_id, {'committed': True, 'outcome': 'archived', 'change_id': change['id'],
                                'verification_id': latest['id'], 'completion_fingerprint': snapshot['digest'],
                                'knowledge': 'pending_project_proposals' if pending else 'not_proposed',
                                'knowledge_scope': 'project', 'pending_knowledge': pending,
                                'versions': versions(store, change['id'], task['id'])})
    except EvolveError as error:
        if store is not None and run_id is not None:
            if not store.run_started(run_id):
                error.committed = True
                raise
            with writer_lock(root):
                with store.transaction() as connection:
                    connection.execute("UPDATE operations SET state='failed' WHERE id=?", (operation_id,))
                    connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                error.committed = True
        raise
    finally:
        if store is not None:
            store.close()
