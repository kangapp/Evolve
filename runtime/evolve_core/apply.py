"""Apply a bound short plan, preserve file facts, then perform task-level checks."""
import json
from pathlib import Path

from .checks import pending_checks, run_check
from .errors import EvolveError
from .package import canonical, digest
from .plans import business_path
from .requests import normalize, require_effect
from .store import Store, identifier
from .work import change_context, check_basis, check_event_sink, claim_resources, fingerprint, gate, record_check, versions
from .workspace import (current_digest, finish_journal, inside, install_files,
                        prepare_files, writer_lock)


def implement(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    require_effect(request, 'business_files')
    data = request['input']
    pause = data.get('pause')
    preservation_only = data.get('preservation_only', False)
    if type(preservation_only) is not bool or (preservation_only and pause is not None):
        raise EvolveError('INPUT', 'preservation_only is an explicit preparation step, separate from a no-check pause')
    if pause is not None:
        if not isinstance(pause, dict) or not isinstance(pause.get('reason'), str) or not pause['reason'].strip():
            raise EvolveError('INPUT', 'Normal pause requires its actual reason and progress')
        for key in ('completed', 'remaining', 'next_steps'):
            value = pause.get(key)
            if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise EvolveError('INPUT', 'Pause progress requires explicit string arrays')
        if not pause['remaining'] or not pause['next_steps']:
            raise EvolveError('INPUT', 'Partial work must retain remaining work and a next step')
    files = data.get('files')
    if not isinstance(data.get('observations', {}), dict):
        raise EvolveError('INPUT', 'External observations must map explicit paths to observed digests')
    if not isinstance(files, list) or any(not isinstance(f, dict) for f in files):
        raise EvolveError('INPUT', 'Implementation requires an explicit files array')
    for item in files:
        if not isinstance(item.get('path'), str) or not isinstance(item.get('content'), str) or 'expected_digest' not in item:
            raise EvolveError('INPUT', 'Each file requires path, expected digest, and candidate text')
        business_path(root, item['path'])
    if len({f['path'] for f in files}) != len(files):
        raise EvolveError('INPUT', 'Duplicate implementation targets')
    if preservation_only and files:
        raise EvolveError('INPUT', 'Behavior preparation cannot contain candidate files')
    operation_id, run_id = identifier(), None
    store = None
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            run_id, previous = store.start(request, action='apply', method='implement', owner='evolve-apply')
            if previous is not None:
                return previous
            from .continuation import bind_continuation
            change, revision, task, definition = change_context(store, request, require_task=True)
            with store.transaction():
                continuation = bind_continuation(store, request, run_id, task=task)
            if definition.get('execution_kind') == 'external_write':
                raise EvolveError('EXTERNAL_METHOD_REQUIRED', 'Use the exact external candidate/target approval; ordinary file apply cannot complete a data task')
            if definition.get('responsible_action') != 'apply':
                raise EvolveError('KNOWLEDGE_OWNER', 'Use the declared formal-document owner to produce this task output')
            if revision['ordinal'] > 1 and revision['accepted_event_id'] is None:
                from .revisions import require_ready
                presented = require_ready(store.connection, revision)
                if presented and presented['requires_acceptance']:
                    raise EvolveError('PLAN_ACCEPTANCE', 'Accept the concrete changed revision before implementing it', exit_code=3)
            bound_dependencies = None
            if definition.get('structured'):
                if definition.get('whole_change'):
                    raise EvolveError('TASK_TARGET', 'Implementation must bind an actual task in the current revision')
                from .structured import current_tasks, dependency_basis, readiness
                peers = current_tasks(store.connection, change['id'], revision['id'])
                ready = readiness(store.connection, root, task, peers)
                if ready['unmet']:
                    raise EvolveError('DEPENDENCY_NOT_READY', 'Task conditions are not met: ' + json.dumps(ready['unmet']), exit_code=3)
                bound_dependencies = dependency_basis(store.connection, task, peers)
            check_basis(root, definition)
            if definition['required_checks'] and pause is None:
                require_effect(request, 'checks')
            if data.get('accepted_plan_digest') != revision['plan_digest']:
                raise EvolveError('PLAN_ACCEPTANCE', 'Acceptance must bind the actual presented plan text', exit_code=3)
            authorized = request['authorization'].get('paths')
            if not isinstance(authorized, list) or not all(isinstance(p, str) for p in authorized):
                raise EvolveError('AUTHORIZATION', 'Business modification authorization requires explicit paths')
            if not set(f['path'] for f in files).issubset(set(definition['scope']) & set(authorized)):
                raise EvolveError('SCOPE', 'Candidate exceeds accepted plan or authorized file scope')
            formal = {inside(root, row['path']).resolve() for row in store.connection.execute(
                "SELECT path FROM artifacts WHERE kind='knowledge' AND path IS NOT NULL")}
            for item in files:
                if business_path(root, item['path']).resolve() in formal:
                    raise EvolveError('KNOWLEDGE_OWNER', 'Formal mapped documents require their knowledge owner, not apply')
            old_result = json.loads(task['result_json']) if task['result_json'] else None
            from .work import implementation_baseline
            baseline = implementation_baseline(store, change, definition, old_result)
            observed = data.get('observations', {})
            for name in definition['scope']:
                actual = current_digest(business_path(root, name))
                if actual != baseline[name] and observed.get(name) != actual:
                    raise EvolveError('FILE_CONFLICT', 'Unregistered workspace change requires an explicit observation: ' + name,
                                      exit_code=3)
            if task['state'] == 'done':
                from .revisions import eligible_verifications, origin_tasks
                origins = {old['id'] for old in origin_tasks(store.connection, task)}
                related = [row for row in eligible_verifications(store.connection, change['id'], revision['id'])
                    if not definition.get('structured') or json.loads(row['items_json']).get('task_id') in origins | {None}]
                failure = next((row for row in related if row['status'] in ('failed', 'blocked')), None)
                revalidation = bool(definition.get('structured') and ready['revalidation_required'])
                if not revalidation and (not failure or data.get('reopen_verification_id') != failure['id']):
                    raise EvolveError('TASK_DONE', 'Reopening the same task requires its failure evidence', exit_code=3)
            pre_refactor = definition.get('pre_refactor', False)
            before = None
            if preservation_only and not pre_refactor:
                raise EvolveError('INPUT', 'Behavior preparation belongs only to a declared pre-refactor task')
            if pre_refactor:
                from .preservation import protected_inputs, select_before
                protected_inputs(root, definition)
                before = select_before(store.connection, root, task, definition, bound_dependencies)
                if before is None and pause is not None:
                    raise EvolveError('PRESERVATION_REQUIRED', 'Run preservation_only first; a no-check pause cannot invent the original behavior proof')
                if before is None:
                    require_effect(request, 'checks')
            claim_resources(store, run_id, operation_id, generation, change, definition['scope'], 'business_files')
            with store.transaction() as connection:
                accepted = revision['accepted_event_id']
                if accepted is None:
                    accepted = store.event(run_id, 'plan_accepted', {'revision_id': revision['id'],
                                          'plan_digest': revision['plan_digest'], 'authorization': request['authorization']})
                    connection.execute('UPDATE plan_revisions SET accepted_event_id=? WHERE id=?', (accepted, revision['id']))
                connection.execute("UPDATE changes SET state='active',row_version=row_version+1 WHERE id=?", (change['id'],))
                connection.execute("UPDATE tasks SET state='in_progress',row_version=row_version+1 WHERE id=?", (task['id'],))
                for name, content_digest in observed.items():
                    if name not in definition['scope'] or current_digest(business_path(root, name)) != content_digest:
                        raise EvolveError('OBSERVATION', 'External observation is not current or in scope', exit_code=3)
                    store.event(run_id, 'external_observation', {'path': name, 'digest': content_digest,
                                                               'source': 'external_or_unknown'})
            expected = versions(store, change['id'], task['id'])
            gate(store, request, run_id, operation_id, expected)
            segment = fingerprint(root, definition) if pre_refactor else None
        if pre_refactor and before is None:
            from .preservation import run_before
            before, before_status, before_results = run_before(store, request, run_id, operation_id, expected,
                task, definition, bound_dependencies, segment)
            if before_status != 'passed':
                with writer_lock(root):
                    gate(store, request, run_id, operation_id, expected)
                    proof = {'status': 'before_' + before_status, 'before': before, 'after_evidence_ids': []}
                    result = {'fingerprint': segment, 'definition_digest': task['definition_digest'], 'artifacts': [],
                              'check_evidence': [], 'dependency_basis': bound_dependencies, 'preservation': proof}
                    with store.transaction() as connection:
                        connection.execute('UPDATE tasks SET result_json=?,row_version=row_version+1 WHERE id=?',
                                           (canonical(result).decode(), task['id']))
                        from .structured import invalidate_dependents
                        invalidate_dependents(store, run_id, change['id'], revision['id'])
                        connection.execute("UPDATE operations SET state='failed',result_json=? WHERE id=?", (canonical(proof).decode(), operation_id))
                        connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    return store.finish(run_id, {'committed': True, 'outcome': 'checks_not_passed', 'operation_id': operation_id,
                        'change_id': change['id'], 'revision_id': revision['id'], 'task_id': task['id'],
                        'definition_digest': task['definition_digest'], 'fingerprint': segment, 'preservation': proof,
                        'check_stage': 'preservation_before', 'task_checks': before_results, 'business_files_dispatched': False,
                        'versions': versions(store, change['id'], task['id']), 'overall_verification': 'not_run'})
        with writer_lock(root):
            gate(store, request, run_id, operation_id, expected)
            if pre_refactor:
                from .preservation import before_fact
                before_fact(store.connection, root, task, definition, before, bound_dependencies, active_run=run_id)
                if fingerprint(root, definition)['digest'] != segment['digest']:
                    raise EvolveError('WORKSPACE_CHANGED', 'Workspace changed between behavior preparation and file dispatch', exit_code=3)
                if before['run_id'] != run_id:
                    source = store.one('SELECT result_digest FROM phase_runs WHERE id=?', (before['run_id'],))
                    with store.transaction():
                        store.link_source(run_id, before['run_id'], source['result_digest'], 'behavior_preservation_basis')
            journal = prepare_files(root, operation_id, files)
            with store.transaction() as connection:
                connection.execute('UPDATE operations SET journal_path=? WHERE id=?',
                                   ('.evolve-local/control/operations/' + operation_id + '.json', operation_id))
            gate(store, request, run_id, operation_id, expected)
            def write_gate():
                gate(store, request, run_id, operation_id, expected)
                if pre_refactor:
                    before_fact(store.connection, root, task, definition, before, bound_dependencies, active_run=run_id)
            install_files(root, journal, before_write=write_gate)
            snapshot = fingerprint(root, definition)
            if pre_refactor:
                before_fact(store.connection, root, task, definition, before, bound_dependencies, active_run=run_id)
            with store.transaction() as connection:
                artifacts = [store.artifact(item['path'], 'source_result', business_path(root, item['path']).read_bytes(),
                                            run_id, 'evolve-apply') for item in files]
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?",
                                   (canonical({'artifacts': artifacts, 'fingerprint': snapshot,
                                               **({'preservation_before': before} if pre_refactor else {})}).decode(), operation_id))
                store.event(run_id, 'files_applied', {'operation_id': operation_id, 'artifacts': artifacts})
            finish_journal(root, journal)
            progress = pause or ({'reason': 'Original behavior was prepared; implementation and post-checks remain.',
                'completed': ['Recorded the original behavior check evidence.'], 'remaining': ['Implement the refactor and run unchanged checks.'],
                'next_steps': ['Continue the same task using its recorded original proof.']} if preservation_only else None)
            if progress is not None:
                gate(store, request, run_id, operation_id, expected)
                current = fingerprint(root, definition)
                if current['digest'] != snapshot['digest']:
                    raise EvolveError('WORKSPACE_CHANGED', 'Workspace changed before the safe pause', exit_code=3)
                result = {'fingerprint': current, 'definition_digest': task['definition_digest'],
                          'artifacts': artifacts, 'check_evidence': [], 'progress': progress,
                          'checks': 'before_only' if preservation_only else 'not_run', 'learning': 'pending'}
                if pre_refactor:
                    result['preservation'] = {'status': 'before_passed' if preservation_only else 'pending_after',
                                              'before': before, 'after_evidence_ids': []}
                if bound_dependencies is not None:
                    result['dependency_basis'] = bound_dependencies
                with store.transaction() as connection:
                    connection.execute('UPDATE tasks SET state=?,row_version=row_version+1,result_json=? WHERE id=?',
                                       ('in_progress', canonical(result).decode(), task['id']))
                    if definition.get('structured'):
                        from .structured import invalidate_dependents
                        invalidate_dependents(store, run_id, change['id'], revision['id'])
                    connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    store.event(run_id, 'implementation_paused', {'task_id': task['id'], 'progress': progress,
                                                                'checks': result['checks']})
                return store.finish(run_id, {'committed': True, 'outcome': 'partial', 'operation_id': operation_id,
                    'change_id': change['id'], 'revision_id': revision['id'], 'task_id': task['id'],
                    'definition_digest': task['definition_digest'], 'fingerprint': current, 'progress': progress,
                    'continuation': continuation, 'checks': result['checks'], 'learning': 'pending',
                    **({'preservation': result['preservation']} if pre_refactor else {}),
                    'versions': versions(store, change['id'], task['id']), 'overall_verification': 'not_run'})
        # All long commands run outside the writer lock and SQLite transaction.
        results, evidence_ids = [], []
        for check in check_basis(root, definition):
            with writer_lock(root):
                gate(store, request, run_id, operation_id, expected)
                if fingerprint(root, definition)['digest'] != snapshot['digest']:
                    raise EvolveError('WORKSPACE_CHANGED', 'Workspace changed before task check', exit_code=3)
            result = run_check(root, check, event_sink=check_event_sink(store, request, run_id, operation_id, expected))
            with writer_lock(root):
                gate(store, request, run_id, operation_id, expected)
                with store.transaction():
                    evidence_ids.append(record_check(store, run_id, result))
                    store.event(run_id, 'task_check', {'check_id': check['id'], 'status': result['status'],
                                                     'evidence_id': evidence_ids[-1]})
            results.append(result)
            if result['unfinished_processes']:
                raise EvolveError('CHECK_RUNNING', 'A check process group is still present; inspect before continuing', exit_code=4, committed=True)
        with writer_lock(root):
            gate(store, request, run_id, operation_id, expected)
            current = fingerprint(root, definition)
            if current['digest'] != snapshot['digest']:
                raise EvolveError('WORKSPACE_CHANGED', 'Workspace changed during task checks; source was preserved', exit_code=3)
            missing = [p for p in definition['required_deliverables'] if current['scope'][p] is None]
            passed = not missing and all(item['status'] == 'passed' for item in results)
            comparison = None
            if pre_refactor:
                from .preservation import after_summary
                comparison = after_summary(store.connection, root, task, definition, before, bound_dependencies,
                                           results, evidence_ids, run_id)
                passed &= comparison['status'] == 'passed'
            outcome = 'implemented' if passed else 'checks_not_passed'
            task_result = {'fingerprint': current, 'definition_digest': task['definition_digest'],
                           'artifacts': artifacts, 'check_evidence': evidence_ids, 'missing': missing,
                           'implementation_source': 'evolve-apply' if files else 'observed_existing_files'}
            if comparison:
                task_result['preservation'] = comparison
            if bound_dependencies is not None:
                task_result['dependency_basis'] = bound_dependencies
            with store.transaction() as connection:
                connection.execute('UPDATE tasks SET state=?,row_version=row_version+1,result_json=? WHERE id=?',
                                   ('done' if passed else 'in_progress', canonical(task_result).decode(), task['id']))
                if definition.get('structured'):
                    from .structured import invalidate_dependents
                    invalidate_dependents(store, run_id, change['id'], revision['id'])
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'task_result', {'task_id': task['id'], 'outcome': outcome,
                                                   'definition_digest': task['definition_digest']})
            return store.finish(run_id, {'committed': True, 'outcome': outcome, 'operation_id': operation_id,
                                'change_id': change['id'], 'revision_id': revision['id'], 'task_id': task['id'],
                                'definition_digest': task['definition_digest'], 'fingerprint': current,
                                'continuation': continuation,
                                **({'preservation': comparison} if comparison else {}),
                                'versions': versions(store, change['id'], task['id']),
                                'task_checks': [{**{key: item[key] for key in ('check_id', 'status', 'returncode')},
                                                'evidence_id': evidence_ids[i]} for i, item in enumerate(results)],
                                'overall_verification': 'not_run'})
    except (EvolveError, OSError) as error:
        if store is not None and run_id is not None:
            if not store.run_started(run_id):
                if isinstance(error, EvolveError):
                    error.committed = True
                    raise
                raise EvolveError('NEEDS_RECOVERY', 'Completed facts are saved but their receipt failed', exit_code=4, committed=True)
            with writer_lock(root):
                operation = store.one('SELECT * FROM operations WHERE id=?', (operation_id,))
                journal_path = inside(root, '.evolve-local/control/operations/' + operation_id + '.json')
                pending_files = journal_path.exists() and json.loads(journal_path.read_text()).get('state') != 'committed'
                pending_processes = pending_checks(store.connection, run_id)
                with store.transaction() as connection:
                    if isinstance(error, EvolveError) and hasattr(error, 'input_check_reference'):
                        store.rejected_source(run_id, error.input_check_reference, 'normal_continuation', error)
                    if pending_files:
                        connection.execute("UPDATE operations SET state='needs_recovery' WHERE id=?", (operation_id,))
                    elif not pending_processes:
                        connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                        if operation and operation['state'] == 'prepared':
                            connection.execute("UPDATE operations SET state='failed' WHERE id=?", (operation_id,))
                    store.event(run_id, 'implementation_interrupted' if pending_files else 'implementation_blocked',
                                {'message': str(error), 'operation_id': operation_id, 'writer_stopped': True})
                if not pending_files and not pending_processes:
                    store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                if isinstance(error, EvolveError):
                    error.committed = True
                    raise
                raise EvolveError('NEEDS_RECOVERY', 'Local write did not finish: ' + str(error), exit_code=4, committed=True)
        raise
    finally:
        if store is not None:
            store.close()
