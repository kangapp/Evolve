"""Reconcile an interrupted local file operation without rerunning business commands."""
import base64
import json
from pathlib import Path
import socket
import sqlite3

from .errors import EvolveError
from .checks import pending_checks, validate_stop_observations
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .work import change_context, fingerprint, gate_identity, require_bound_targets, versions
from .workspace import (current_digest, durable_write, finish_journal, inside,
                        install_files, process_alive, writer_lock)


def protect_recovery(store, operation, journal, recovery_id):
    folder = inside(store.root, '.evolve-local/control/recoveries/' + recovery_id)
    folder.mkdir(parents=True, exist_ok=False)
    backup = sqlite3.connect(folder / 'history.db')
    try:
        store.connection.backup(backup)
    finally:
        backup.close()
    durable_write(folder / 'operation.json', canonical(dict(operation)), new=True)
    durable_write(folder / 'journal.json', canonical(journal), new=True)
    observations = []
    for item in journal.get('files', []):
        path = inside(store.root, item['path'])
        content = path.read_bytes() if path.is_file() else None
        content_digest = digest(content) if content is not None else None
        observations.append({'path': item['path'], 'digest': content_digest})
        if content is not None:
            durable_write(folder / ('observed-' + content_digest), content)
    manifest = {'kind': 'interrupted-local-protection', 'consistent_restore_package': False,
                'project_id': store.meta['project_id'], 'workspace_epoch': store.meta['workspace_epoch'],
                'observed_at': now(), 'observations': observations,
                'files': {p.name: digest(p.read_bytes()) for p in folder.iterdir() if p.is_file()}}
    durable_write(folder / 'manifest.json', canonical(manifest), new=True)
    return folder.relative_to(store.root).as_posix()


def require_checks_stopped(store, run_id, request):
    pending = pending_checks(store.connection, run_id)
    return validate_stop_observations(pending, request['input'].get('check_observations', []))


def record_check_observations(store, run_id, original_id, observations):
    for observation in observations:
        store.event(run_id, 'check_execution_observed', {'original_run_id': original_id, 'observation': observation,
                                                       'test_result': 'not_inferred'})


def seal_unexecuted(store, request, original, operation=None):
    check_observations = require_checks_stopped(store, original['id'], request)
    owner = json.loads(original['execution_instance'])
    if owner['host'] != socket.gethostname() or process_alive(owner['pid']):
        raise EvolveError('WRITER_ACTIVE', 'Run without a file journal is not known to have stopped', exit_code=3)
    source = json.loads(original['input_json'])['request']
    if source['project_id'] != request['project_id'] or source['expected_workspace_epoch'] != request['expected_workspace_epoch']:
        raise EvolveError('WORKSPACE_EPOCH', 'Interrupted run belongs to another project or epoch', exit_code=3)
    paths = source['input'].get('scope', [])
    if source['input'].get('change_id'):
        tasks = store.connection.execute('SELECT id,definition_json FROM tasks WHERE change_id=? AND revision_id=?',
            (source['input']['change_id'], source['input'].get('revision_id'))).fetchall()
        selected = [t for t in tasks if source['input'].get('task_id') in (None, t['id'])]
        if selected:
            paths = sorted({name for t in selected for name in json.loads(t['definition_json'])['scope']})
    observations = {'state': 'observation-only-no-file-dispatch', 'files': [{'path': p} for p in paths]}
    protection = protect_recovery(store, dict(operation) if operation else {'run_id': original['id'], 'registered_operation': None},
                                  observations, identifier())
    run_id, previous = store.start(request, action='maintain', method='recover', owner='evolve-maintain')
    if previous is not None:
        return previous
    with store.transaction() as connection:
        record_check_observations(store, run_id, original['id'], check_observations)
        if operation:
            connection.execute("UPDATE operations SET state='failed',result_json=? WHERE id=?",
                               (canonical({'recovered_by': run_id, 'file_dispatch': 'not_started'}).decode(), operation['id']))
            connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation['id'],))
        store.event(run_id, 'interrupted_run_observed', {'original_run_id': original['id'], 'protection': protection,
                                                        'business_attribution': 'not_inferred'})
    export = {}
    if (original['action'], original['method']) == ('maintain', 'export'):
        from .exporting import interrupted_export
        export = interrupted_export(store, original['id'])
    store.finish(original['id'], {'committed': True, 'outcome': 'partial', 'finalized_by': run_id,
                                  'remaining': ['review saved facts and continue in a new run'], **export}, status='interrupted')
    return store.finish(run_id, {'committed': True, 'outcome': 'recovered_registration', 'original_run_id': original['id'],
                                'protection': protection, 'business_commands_run': False, 'implementation_completed': False})


def recover_initial(root, request, journal):
    from .connect import connect
    if request.get('project_id') != journal['project_id'] or request.get('expected_workspace_epoch') != journal['workspace_epoch']:
        raise EvolveError('WORKSPACE_EPOCH', 'Initialization recovery must preserve its original identity', exit_code=3)
    result = connect(root, journal['request'], recover=True)
    with writer_lock(root):
        store = Store(root)
        try:
            run_id, previous = store.start(request, action='maintain', method='recover', owner='evolve-maintain')
            if previous is not None:
                return previous
            return store.finish(run_id, {'committed': True, 'outcome': 'initialization_reconciled',
                                'original_run_id': result['run_id'], 'project_id': result['project_id'],
                                'workspace_epoch': result['workspace_epoch'], 'business_commands_run': False})
        finally:
            store.close()


def recover_metadata(store, request, original, operation, check_observations):
    execution = json.loads(original['execution_instance'])
    if execution['host'] != socket.gethostname() or process_alive(execution['pid']):
        raise EvolveError('WRITER_ACTIVE', 'Metadata execution is not known to have stopped', exit_code=3)
    committed = operation['state'] == 'committed'
    verification = store.one('SELECT * FROM verifications WHERE source_run_id=?', (original['id'],))
    saved = json.loads(operation['result_json']) if operation['result_json'] else {}
    if committed:
        if original['action'] == 'verify':
            if (not verification or verification['status'] not in ('passed', 'failed', 'blocked')
                    or saved.get('verification_id') != verification['id'] or saved.get('status') != verification['status']):
                raise EvolveError('RECOVERY_INVALID', 'Committed verification facts are inconsistent', exit_code=4)
        elif original['action'] == 'update':
            events = store.connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind='revision_committed'", (original['id'],)).fetchall()
            if not any(json.loads(row[0]).get('revision_id') == saved.get('revision_id') for row in events):
                raise EvolveError('RECOVERY_INVALID', 'Committed revision has no matching saved event', exit_code=4)
        elif original['action'] == 'sync' or (original['action'], original['method']) in (('init', 'baseline.propose'), ('init', 'survey'), ('init', 'complete'), ('learn', 'promote')):
            if not any(json.loads(row[0]).get('result_digest') == digest(canonical(saved)) for row in store.connection.execute(
                    "SELECT payload_json FROM events WHERE run_id=? AND kind='knowledge_metadata_committed'", (original['id'],))):
                raise EvolveError('RECOVERY_INVALID', 'Committed knowledge metadata has no matching saved event', exit_code=4)
        elif original['action'] == 'apply' and original['method'] in ('external.execute', 'external.compensate'):
            task = store.one('SELECT result_json FROM tasks WHERE id=?', (saved.get('task_id'),))
            if (not task or not task[0] or digest(canonical(json.loads(task[0]))) != saved.get('task_result_digest')
                    or not any(json.loads(row[0]) == saved for row in store.connection.execute(
                        "SELECT payload_json FROM events WHERE run_id=? AND kind='external_task_checks_committed'", (original['id'],)))):
                raise EvolveError('RECOVERY_INVALID', 'Committed external task checks lack their exact task result and matching event', exit_code=4)
        elif (original['action'], original['method']) == ('maintain', 'cancel'):
            events = store.connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind='change_cancelled'", (original['id'],)).fetchall()
            change = store.one('SELECT state FROM changes WHERE id=?', (saved.get('change_id'),))
            if not change or change['state'] != 'cancelled' or not any(json.loads(row[0]) == saved for row in events):
                raise EvolveError('RECOVERY_INVALID', 'Committed cancellation lacks consistent saved facts', exit_code=4)
        elif not store.one("SELECT id FROM events WHERE run_id=? AND kind='change_archived'", (original['id'],)):
            raise EvolveError('RECOVERY_INVALID', 'Committed closure has no saved completion event', exit_code=4)
    protection = protect_recovery(store, operation, {'kind': 'metadata-only-observation', 'files': []}, identifier())
    run_id, previous = store.start(request, action='maintain', method='recover', owner='evolve-maintain')
    if previous is not None:
        return previous
    with store.transaction() as connection:
        record_check_observations(store, run_id, original['id'], check_observations)
        if not committed:
            if verification:
                connection.execute("UPDATE verifications SET status='blocked' WHERE id=? AND status='not_run'", (verification['id'],))
            connection.execute("UPDATE operations SET state='failed',result_json=? WHERE id=?",
                               (canonical({'recovered_by': run_id, 'business_commands_run': False}).decode(), operation['id']))
        connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation['id'],))
        store.event(run_id, 'metadata_reconciled', {'original_run_id': original['id'], 'protection': protection,
                    'original_facts_committed': committed, 'business_commands_run': False})
    store.finish(original['id'], {'committed': True, 'outcome': 'reconciled_committed_metadata' if committed else 'partial',
                 'saved_operation_result': saved, 'finalized_by': run_id, 'business_commands_run': False},
                 status='interrupted')
    return store.finish(run_id, {'committed': True, 'outcome': 'recovered_metadata', 'original_run_id': original['id'],
                        'operation_id': operation['id'], 'original_facts_committed': committed,
                        'protection': protection, 'business_commands_run': False})


def recover(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    initial = inside(root, '.evolve-local/control/init.json')
    if initial.is_file():
        journal = json.loads(initial.read_text())
        if journal['state'] != 'committed':
            return recover_initial(root, request, journal)
    store = None
    with writer_lock(root, recover_dead=True):
        try:
            store = Store(root)
            repeated = store.lookup(request, action='maintain', method='recover', owner='evolve-maintain')
            if repeated is not None:
                return repeated[1]
            target = request['input'].get('operation_id')
            if target:
                candidates = store.connection.execute('SELECT o.* FROM operations o JOIN phase_runs r ON r.id=o.run_id '
                                                      "WHERE o.id=? AND r.status='started'", (target,)).fetchall()
            else:
                candidates = store.connection.execute('SELECT o.* FROM operations o JOIN phase_runs r ON r.id=o.run_id '
                                                      "WHERE r.status='started' AND (r.action IN ('apply','verify','archive','update','sync') OR (r.action='learn' AND r.method='promote') OR "
                                                      "(r.action='init' AND r.method IN ('baseline.apply','baseline.propose','connect','survey','complete')) OR (r.action='maintain' AND r.method='cancel'))").fetchall()
                no_operations = store.connection.execute("SELECT r.* FROM phase_runs r LEFT JOIN operations o ON o.run_id=r.id "
                                                        "WHERE r.status='started' AND o.id IS NULL AND (r.action IN ('apply','propose','verify','archive','init','analyze','learn','update','sync') OR (r.action='maintain' AND r.method IN ('export','cancel')))").fetchall()
                run_target = request['input'].get('run_id')
                if run_target:
                    no_operations = [r for r in no_operations if r['id'] == run_target]
                    candidates = [o for o in candidates if o['run_id'] == run_target]
                if len(no_operations) == 1 and not candidates:
                    return seal_unexecuted(store, request, no_operations[0])
                if no_operations and candidates:
                    raise EvolveError('RECOVERY_TARGET', 'Multiple unfinished runs exist; select a run or operation explicitly')
            if len(candidates) != 1:
                raise EvolveError('RECOVERY_TARGET', 'Select one actual interrupted local operation')
            operation = candidates[0]
            original = store.one('SELECT * FROM phase_runs WHERE id=?', (operation['run_id'],))
            check_observations = require_checks_stopped(store, original['id'], request)
            business = original['action'] == 'apply' and original['method'] == 'implement' and operation['effect_kind'] == 'business_files'
            typed_initial = False
            if original['action'] == 'init' and original['method'] == 'baseline.apply':
                typed_initial = bool(json.loads(original['input_json'])['request']['input'].get('proposal'))
            baseline = original['action'] == 'init' and original['method'] == 'baseline.apply' and operation['effect_kind'] == 'knowledge' and not typed_initial
            configured = original['action'] == 'init' and original['method'] == 'connect' and operation['effect_kind'] == 'config'
            formal = ((original['action'] == 'sync' and original['method'] == 'apply') or typed_initial or (original['action'], original['method']) == ('learn', 'promote')) and operation['effect_kind'] == 'knowledge'
            metadata = (original['action'], original['method']) in (('verify', 'run'), ('verify', 'knowledge'), ('archive', 'close'), ('update', 'revise'), ('sync', 'propose'), ('sync', 'check'), ('sync', 'review'), ('sync', 'assess'), ('init', 'baseline.propose'), ('init', 'survey'), ('init', 'complete'), ('learn', 'promote'), ('maintain', 'cancel'), ('apply', 'external.execute'), ('apply', 'external.compensate')) and operation['effect_kind'] == 'project_records'
            if not business and not baseline and not configured and not metadata and not formal:
                raise EvolveError('RECOVERY_TARGET', 'This recovery path does not support the selected operation')
            original_request = json.loads(original['input_json'])['request']
            original_request['request_id'] = original['request_id']
            if original_request['project_id'] != request['project_id'] or original_request['expected_workspace_epoch'] != request['expected_workspace_epoch']:
                raise EvolveError('WORKSPACE_EPOCH', 'Recovery cannot reuse an old project or epoch', exit_code=3)
            if formal:
                from .formal import recover_application
                return recover_application(store, request, original, operation)
            if metadata:
                return recover_metadata(store, request, original, operation, check_observations)
            proposal = None
            if business:
                change, revision, task, definition = change_context(store, original_request, versions=False)
                expected = original_request['input']['files']
            elif baseline:
                proposal = store.one('SELECT * FROM knowledge_proposals WHERE id=?', (original_request['input']['proposal_id'],))
                approval = original_request['input']['approval']
                if (not proposal or proposal['state'] != 'approved' or proposal['owner_skill'] != 'evolve-init'
                        or not proposal['approved_event_id'] or proposal['version'] != approval['proposal_version']
                        or proposal['candidate_digest'] != approval['candidate_digest']
                        or proposal['expected_digest'] != approval['expected_digest']):
                    raise EvolveError('KNOWLEDGE_APPROVAL', 'Initial baseline approval is no longer applicable', exit_code=3)
                approved_text = store.one('SELECT content FROM blobs WHERE digest=?', (proposal['candidate_digest'],))[0]
                expected = [{'path': proposal['target_path'], 'expected_digest': proposal['expected_digest'],
                             'content': approved_text.decode('utf-8')}]
            else:
                presentation = original_request['input'].get('presentation')
                if not isinstance(presentation, dict) or not presentation.get('source') or not isinstance(presentation.get('text'), str):
                    raise EvolveError('CONFIG_PRESENTATION', 'Configuration recovery requires its exact presented candidate')
                expected = [{'path': 'evolve/config.toml', 'expected_digest': original_request['input']['expected_config_digest'],
                             'content': presentation['text']}]
            stopped = False
            for row in store.connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind IN "
                                                "('implementation_interrupted','knowledge_application_interrupted','configuration_interrupted')",
                                                (original['id'],)):
                stopped |= json.loads(row[0]).get('writer_stopped') is True
            claims = store.connection.execute('SELECT generation FROM resource_claims WHERE operation_id=?', (operation['id'],)).fetchall()
            if not claims:
                execution = json.loads(original['execution_instance'])
                if operation['state'] != 'committed' or execution['host'] != socket.gethostname() or process_alive(execution['pid']):
                    raise EvolveError('RECOVERY_TARGET', 'Interrupted operation has no verifiable stopped execution', exit_code=4)
            for claim in claims:
                owner = json.loads(claim['generation'])
                if owner['host'] != socket.gethostname() or (not stopped and process_alive(owner['pid'])):
                    raise EvolveError('WRITER_ACTIVE', 'Original execution is not known to have stopped', exit_code=3)
            for row in store.connection.execute("SELECT payload_json FROM events WHERE kind='authorization_revoked'"):
                revoked = json.loads(row[0])
                if revoked.get('request_id') == original['request_id'] or (business and revoked.get('change_id') == change['id']):
                    raise EvolveError('AUTHORIZATION', 'Original file-write authorization was revoked', exit_code=3)
            path = inside(root, '.evolve-local/control/operations/' + operation['id'] + '.json')
            if operation['journal_path'] is None and not path.exists():
                return seal_unexecuted(store, request, original, operation)
            if operation['journal_path'] not in (None, path.relative_to(root).as_posix()) or not path.is_file():
                raise EvolveError('JOURNAL_INVALID', 'Operation does not identify its own saved file journal', exit_code=4)
            journal = json.loads(path.read_text())
            if journal.get('operation_id') != operation['id']:
                raise EvolveError('JOURNAL_INVALID', 'Journal identity differs from the recorded operation', exit_code=4)
            if len(expected) != len(journal['files']):
                raise EvolveError('JOURNAL_INVALID', 'Journal does not match the originally authorized file set', exit_code=4)
            for item, approved in zip(journal['files'], expected):
                content = base64.b64decode(item['candidate_b64'], validate=True)
                if (item['path'] != approved['path'] or item['expected_digest'] != approved['expected_digest']
                        or digest(content) != item['candidate_digest'] or content != approved['content'].encode('utf-8')):
                    raise EvolveError('JOURNAL_INVALID', 'Journal candidate differs from immutable authorized input', exit_code=4)
            recovery_id = identifier()
            target_paths = definition['scope'] if business else [item['path'] for item in expected]
            require_bound_targets(store, operation['id'], target_paths)
            protection = protect_recovery(store, operation, journal, recovery_id)
            run_id, previous = store.start(request, action='maintain', method='recover', owner='evolve-maintain')
            if previous is not None:
                return previous
            with store.transaction():
                record_check_observations(store, run_id, original['id'], check_observations)
            conflicts = [item['path'] for item in journal['files']
                         if current_digest(inside(root, item['path'])) not in (
                             (item['candidate_digest'],) if operation['state'] == 'committed'
                             else (item['expected_digest'], item['candidate_digest']))]
            if conflicts:
                return store.finish(run_id, {'committed': True, 'outcome': 'needs_recovery',
                                    'conflicts': conflicts, 'protection': protection, 'business_commands_run': False}, status='blocked')
            def recovery_gate():
                gate_identity(store, request, run_id)
                require_bound_targets(store, operation['id'], target_paths)
                if business:
                    change_context(store, original_request, versions=False)
                    if definition.get('pre_refactor'):
                        from .preservation import select_before
                        from .structured import current_tasks, dependency_basis
                        peers = current_tasks(store.connection, change['id'], task['revision_id'])
                        before = select_before(store.connection, root, task, definition,
                            dependency_basis(store.connection, task, peers), active_run=original['id'])
                        if before is None:
                            raise EvolveError('PRESERVATION_REQUIRED', 'Recovery cannot dispatch a refactor without its original behavior proof')
                elif baseline:
                    current = store.one('SELECT state,approved_event_id FROM knowledge_proposals WHERE id=?', (proposal['id'],))
                    if current['state'] != 'approved' or current['approved_event_id'] != proposal['approved_event_id']:
                        raise EvolveError('KNOWLEDGE_APPROVAL', 'Knowledge approval changed during recovery', exit_code=3)
            install_files(root, journal, before_write=recovery_gate)
            snapshot = fingerprint(root, definition) if business else None
            with store.transaction() as connection:
                artifacts = [store.artifact(item['path'], 'source_result' if business else 'knowledge' if baseline else 'config',
                                            inside(root, item['path']).read_bytes(), run_id,
                                            'evolve-maintain:recovered-apply' if business else 'evolve-maintain:recovered-approved-init')
                             for item in journal['files']]
                if business:
                    result = {'fingerprint': snapshot, 'definition_digest': task['definition_digest'],
                              'artifacts': artifacts, 'check_evidence': [], 'missing': [],
                              'implementation_source': 'recovered-local-operation'}
                    if definition.get('pre_refactor'):
                        from .preservation import select_before
                        from .structured import current_tasks, dependency_basis
                        peers = current_tasks(store.connection, change['id'], task['revision_id'])
                        before = select_before(store.connection, root, task, definition,
                            dependency_basis(store.connection, task, peers), active_run=original['id'])
                        result['preservation'] = {'status': 'pending_after', 'before': before, 'after_evidence_ids': []}
                        result['dependency_basis'] = dependency_basis(store.connection, task, peers)
                    if task['state'] != 'done':
                        connection.execute('UPDATE tasks SET state=?,row_version=row_version+1,result_json=? WHERE id=?',
                                           ('in_progress', canonical(result).decode(), task['id']))
                elif baseline:
                    connection.execute('UPDATE knowledge_proposals SET applied_operation_id=? WHERE id=?',
                                       (operation['id'], proposal['id']))
                    store.event(run_id, 'knowledge_applied', {'proposal_id': proposal['id'],
                                'approved_event_id': proposal['approved_event_id'], 'artifact': artifacts[0],
                                'recovery_of': original['id']})
                else:
                    store.event(run_id, 'configuration_applied', {'artifact': artifacts[0], 'checks_run': False,
                                                                 'recovery_of': original['id']})
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?",
                                   (canonical({'recovered_by': run_id, 'artifacts': artifacts}).decode(), operation['id']))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation['id'],))
                store.event(run_id, 'local_operation_reconciled', {'original_run_id': original['id'],
                            'operation_id': operation['id'], 'protection': protection, 'checks': 'not_run'})
            finish_journal(root, journal)
            store.finish(original['id'], {'committed': True, 'outcome': 'partial', 'remaining': ['task checks', 'overall verification'],
                         'finalized_by': run_id, 'operation_id': operation['id']}, status='interrupted')
            return store.finish(run_id, {'committed': True, 'outcome': 'recovered_local', 'operation_id': operation['id'],
                                'original_run_id': original['id'], 'protection': protection,
                                'business_commands_run': False, 'checks': 'not_run',
                                'versions': versions(store, change['id'], task['id']) if business else {},
                                'knowledge_proposal_id': proposal['id'] if proposal else None})
        finally:
            if store is not None:
                store.close()
