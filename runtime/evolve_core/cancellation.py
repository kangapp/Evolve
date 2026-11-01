"""Record safe local cancellation; physical effects and original evidence remain."""
import json
from pathlib import Path

from .errors import EvolveError
from .package import canonical
from .requests import normalize, require_effect
from .store import Store, identifier
from .work import change_context, claim_resources, gate_identity
from .workspace import writer_lock


def cancel_change(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    if request['input'].get('external_operation_id'):
        from .external_actions import cancel
        return cancel(root, request)
    reason = request['input'].get('reason')
    if not isinstance(reason, str) or not reason.strip():
        raise EvolveError('INPUT', 'Cancellation requires the actual reason for stopping this work')
    with writer_lock(root) as generation:
        store = Store(root)
        run_id, operation_id = None, identifier()
        try:
            previous = store.lookup(request, action='maintain', method='cancel', owner='evolve-maintain')
            if previous is not None:
                return previous[1]
            change, revision, task, definition = change_context(store, request)
            # An active or unknown local/external action must finish or be reconciled.
            for run in store.connection.execute("SELECT input_json FROM phase_runs WHERE status='started'"):
                data = json.loads(run['input_json'])['request']['input']
                if data.get('change_id') == change['id']:
                    raise EvolveError('CLAIM', 'This work has an unfinished action; preserve its claims and inspect the original execution', exit_code=3)
            run_id, _ = store.start(request, action='maintain', method='cancel', owner='evolve-maintain')
            claim_resources(store, run_id, operation_id, generation, change, [], 'project_records')
            result = {'committed': True, 'outcome': 'cancelled', 'change_id': change['id'],
                      'revision_id': revision['id'], 'reason': reason,
                      'business_files_changed': False, 'business_commands_run': False,
                      'completed_results_preserved': True, 'knowledge_approval': 'not_implied'}
            gate_identity(store, request, run_id)
            with store.transaction() as connection:
                connection.execute("UPDATE changes SET state='cancelled',row_version=row_version+1 WHERE id=?", (change['id'],))
                connection.execute("UPDATE tasks SET state='cancelled',row_version=row_version+1 "
                                   "WHERE change_id=? AND revision_id=? AND state NOT IN ('done','cancelled')",
                                   (change['id'], revision['id']))
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?",
                                   (canonical(result).decode(), operation_id))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'change_cancelled', result)
            return store.finish(run_id, result)
        except EvolveError as error:
            operation = store.one('SELECT state FROM operations WHERE id=?', (operation_id,))
            if operation and operation['state'] == 'committed':
                error.committed = True
                raise
            if run_id is not None and store.run_started(run_id):
                with store.transaction() as connection:
                    connection.execute("UPDATE operations SET state='failed' WHERE id=?", (operation_id,))
                    connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                error.committed = True
            raise
        finally:
            store.close()
