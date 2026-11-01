"""Incremental init-owned configuration with an exact presented candidate."""
import json
from pathlib import Path
import tomllib

from .config_edit import edit_configuration
from .errors import EvolveError
from .package import canonical, digest
from .store import Store, identifier
from .work import claim_resources, gate_identity, require_bound_targets
from .workspace import (current_digest, finish_journal, inside, install_files,
                        prepare_files, writer_lock)


def reconnect(root, request):
    root = Path(root).resolve()
    if not request.get('project_id') or not request.get('expected_workspace_epoch'):
        raise EvolveError('INPUT', 'Incremental init must preserve its prepared project identity and epoch')
    store, run_id, operation_id = None, None, identifier()
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            previous = store.lookup(request, action='init', method='connect', owner='evolve-init')
            if previous is not None:
                return previous[1]
            path = inside(root, 'evolve/config.toml')
            original = path.read_bytes()
            settings = tomllib.loads(original.decode('utf-8'))
            if settings.get('project', {}).get('id') != store.meta['project_id']:
                raise EvolveError('PROJECT_IDENTITY', 'Existing configuration identity must be reconciled first')
            if settings.get('history') != {'backend': 'sqlite', 'database': 'evolve/history.db'}:
                raise EvolveError('CONFIG_PATH', 'Existing history location/backend is not supported')
            candidate = edit_configuration(original, request['input'])
            run_id, previous = store.start(request, action='init', method='connect', owner='evolve-init')
            if previous is not None:
                return previous
            if candidate == original:
                return store.finish(run_id, {'committed': True, 'outcome': 'already_connected',
                                    'project_id': store.meta['project_id'], 'workspace_epoch': store.meta['workspace_epoch'],
                                    'configuration_changed': False})
            presentation = request['input'].get('presentation')
            if presentation is None:
                with store.transaction():
                    content_digest = store.blob(candidate)
                    store.event(run_id, 'config_candidate', {'expected_digest': digest(original), 'candidate_digest': content_digest})
                return store.finish(run_id, {'committed': True, 'outcome': 'config_candidate',
                                    'project_id': store.meta['project_id'], 'workspace_epoch': store.meta['workspace_epoch'],
                                    'candidate': candidate.decode('utf-8'), 'candidate_digest': content_digest,
                                    'expected_config_digest': digest(original), 'configuration_changed': False})
            if (not isinstance(presentation, dict) or not presentation.get('source')
                    or presentation.get('text') != candidate.decode('utf-8')
                    or request['input'].get('expected_config_digest') != digest(original)):
                raise EvolveError('CONFIG_PRESENTATION', 'Configuration application must bind the exact presented diff and original bytes', exit_code=3)
            claim_resources(store, run_id, operation_id, generation, None, ['evolve/config.toml'], 'config')
            gate_identity(store, request, run_id)
            journal = prepare_files(root, operation_id, [{'path': 'evolve/config.toml', 'expected_digest': digest(original),
                                                         'content': candidate.decode('utf-8')}])
            with store.transaction() as connection:
                connection.execute('UPDATE operations SET journal_path=? WHERE id=?',
                                   ('.evolve-local/control/operations/' + operation_id + '.json', operation_id))
            def configuration_gate():
                gate_identity(store, request, run_id)
                require_bound_targets(store, operation_id, ['evolve/config.toml'])
            configuration_gate()
            install_files(root, journal, before_write=configuration_gate)
            if current_digest(path) != digest(candidate):
                raise EvolveError('NEEDS_RECOVERY', 'Configuration changed before registration', exit_code=4)
            with store.transaction() as connection:
                artifact = store.artifact('evolve/config.toml', 'config', path.read_bytes(), run_id, 'evolve-init:configuration')
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?",
                                   (canonical({'artifact': artifact}).decode(), operation_id))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'configuration_applied', {'artifact': artifact,
                                                            'presentation_source': presentation['source'], 'checks_run': False})
            finish_journal(root, journal)
            return store.finish(run_id, {'committed': True, 'outcome': 'configuration_updated', 'artifact': artifact,
                                'operation_id': operation_id, 'project_id': store.meta['project_id'],
                                'workspace_epoch': store.meta['workspace_epoch'], 'configuration_changed': True, 'checks_run': False})
    except (EvolveError, OSError) as error:
        if store is not None and run_id is not None:
            if not store.run_started(run_id):
                if isinstance(error, EvolveError):
                    error.committed = True
                    raise
                raise EvolveError('NEEDS_RECOVERY', 'Configuration facts were saved; receipt failed', exit_code=4, committed=True)
            with writer_lock(root):
                path = inside(root, '.evolve-local/control/operations/' + operation_id + '.json')
                pending = path.exists() and json.loads(path.read_text()).get('state') != 'committed'
                with store.transaction() as connection:
                    connection.execute('UPDATE operations SET state=? WHERE id=?', ('needs_recovery' if pending else 'failed', operation_id))
                    if not pending:
                        connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    store.event(run_id, 'configuration_interrupted', {'writer_stopped': True, 'message': str(error)})
                if not pending:
                    store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                if isinstance(error, EvolveError):
                    error.committed = True
                    raise
                raise EvolveError('NEEDS_RECOVERY', 'Configuration file commit needs reconciliation', exit_code=4, committed=True)
        raise
    finally:
        if store is not None:
            store.close()
