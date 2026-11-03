"""Independent acceptance of applied results, including two-axis review evidence."""
import json
from pathlib import Path

from .checks import pending_checks
from .check_reuse import execute as execute_check, fresh_checks, receipt as check_receipt
from .analysis import symptom_reverification
from .errors import EvolveError
from .package import canonical
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .work import change_context, check_basis, claim_resources, fingerprint, gate, record_check, require_workspace, versions, workspace_change
from .workspace import writer_lock


def policy_fields(data):
    if 'review_policy' not in data:
        return {}
    if data['review_policy'] not in ('self_allowed', 'independent'):
        raise EvolveError('REVIEW_POLICY', 'review_policy must be self_allowed or independent')
    return {'review_policy': data['review_policy']}


def review_items(store, change, revision, definition, snapshot, reviews):
    if not isinstance(reviews, list) or len(reviews) != 2 or any(not isinstance(r, dict) for r in reviews):
        raise EvolveError('REVIEW_REQUIRED', 'Provide separate actual spec and standards review observations')
    if {r.get('axis') for r in reviews} != {'spec', 'standards'}:
        raise EvolveError('REVIEW_REQUIRED', 'Review must cover exactly spec and standards')
    active = {}
    known = {}
    previous = store.connection.execute('SELECT id,items_json FROM verifications WHERE change_id=? '
                                        'ORDER BY observed_at,id', (change['id'],)).fetchall()
    for result in previous:
        saved = json.loads(result['items_json'])
        task_id = definition.get('_task_id')
        for review in saved.get('reviews', []):
            for finding in review['findings']:
                if task_id is not None and finding['path'] not in (set(definition['scope']) | set(definition.get('context', {})) | set(definition.get('dependency_inputs', []))):
                    continue
                key = (result['id'], review['axis'], finding['id'])
                known[key] = finding
                if finding['blocking']:
                    active[key] = finding
            for resolution in review.get('resolutions', []):
                active.pop((resolution['verification_id'], review['axis'], resolution['finding_id']), None)
    required = {a['id'] for a in definition['acceptance'] if a['required']}
    provenance = []
    for review in reviews:
        if any(not isinstance(review.get(field), str) or not review[field].strip() for field in ('observer', 'summary')):
            raise EvolveError('REVIEW_REQUIRED', 'Each review requires its actual observer and assessment')
        if review.get('fingerprint_digest') != snapshot['digest']:
            raise EvolveError('STALE_REVIEW', 'Review is not bound to the currently inspected workspace', exit_code=3)
        mode = review.get('mode', 'not_recorded')
        if mode not in ('self', 'independent', 'human', 'not_recorded'):
            raise EvolveError('REVIEW_REQUIRED', 'State the actual self, independent or human review mode')
        if 'independent' in review and type(review['independent']) is not bool:
            raise EvolveError('REVIEW_REQUIRED', 'Human independence must be an explicit boolean observation')
        independent = mode == 'independent' or mode == 'human' and review.get('independent') is True
        if independent and any(not isinstance(review.get(field), str) or not review[field].strip() for field in ('source', 'independence_basis')):
            raise EvolveError('REVIEW_REQUIRED', 'Independent review needs its actual source and separation basis')
        if mode == 'human' and (not isinstance(review.get('source'), str) or not review['source'].strip()):
            raise EvolveError('REVIEW_REQUIRED', 'Human review needs its actual source')
        if definition.get('review_policy') == 'independent' and not independent:
            raise EvolveError('REVIEW_INDEPENDENCE_REQUIRED', 'The accepted plan requires independent observations on both review axes')
        provenance.append({'axis': review['axis'], 'observer': review['observer'], 'mode': mode,
            'independent': independent, 'source': review.get('source'),
            'independence_basis': review.get('independence_basis'), 'identity_attestation': 'observer_supplied'})
        findings = review.get('findings')
        if not isinstance(findings, list) or any(not isinstance(f, dict) for f in findings):
            raise EvolveError('REVIEW_REQUIRED', 'Review findings must be an explicit array')
        seen = set()
        for finding in findings:
            if any(not isinstance(finding.get(k), str) or not finding[k] for k in ('id', 'basis', 'path', 'impact')):
                raise EvolveError('FINDING', 'Findings require stable local identity, location, basis and impact')
            if finding['id'] in seen or type(finding.get('blocking')) is not bool:
                raise EvolveError('FINDING', 'Finding identities must be distinct and blocking must be explicit')
            if finding['path'] not in snapshot['files'] and finding['path'] not in snapshot.get('context', {}) and finding['path'] not in snapshot['scope']:
                raise EvolveError('FINDING', 'Finding location was not part of the inspected workspace')
            if definition.get('_task_id') is not None and finding['path'] not in (
                    set(definition['scope']) | set(definition.get('context', {})) | set(definition.get('dependency_inputs', []))):
                raise EvolveError('FINDING', 'Task review findings must belong to its actual scope or declared inputs')
            seen.add(finding['id'])
        resolutions = review.get('resolutions', [])
        if not isinstance(resolutions, list):
            raise EvolveError('FINDING', 'Resolutions must be explicit observations')
        for resolution in resolutions:
            if not isinstance(resolution, dict) or not resolution.get('basis'):
                raise EvolveError('FINDING', 'Resolution requires current reinspection evidence')
            key = (resolution.get('verification_id'), review['axis'], resolution.get('finding_id'))
            if key not in known:
                raise EvolveError('FINDING', 'Resolution must refer to an actual prior same-axis finding')
            active.pop(key, None)
        if review['axis'] == 'spec':
            results = review.get('acceptance_results')
            if not isinstance(results, list) or any(not isinstance(a, dict) for a in results):
                raise EvolveError('ACCEPTANCE', 'Spec review requires observations for every required acceptance condition')
            if any(not isinstance(a.get('ac_id'), str) for a in results):
                raise EvolveError('ACCEPTANCE', 'Acceptance identities must be strings')
            if len(results) != len(required) or {a.get('ac_id') for a in results} != required:
                raise EvolveError('ACCEPTANCE', 'Spec review omitted or duplicated required acceptance conditions')
            for item in results:
                if (item.get('status') not in ('passed', 'failed', 'blocked')
                        or not isinstance(item.get('basis'), str) or not item['basis'].strip()):
                    raise EvolveError('ACCEPTANCE', 'Acceptance observation requires status and its actual basis')
                if 'check_ids' in item:
                    checks = item['check_ids']
                    if (not isinstance(checks, list) or any(not isinstance(key, str) for key in checks)
                            or len(checks) != len(set(checks)) or not set(checks).issubset(definition['required_checks'])):
                        raise EvolveError('ACCEPTANCE', 'Acceptance check_ids must identify distinct declared checks; an empty list means semantic review only')
    return {'unresolved_prior_findings': [{'verification_id': key[0], 'axis': key[1], 'finding_id': key[2]}
                                         for key in active], 'reviews': reviews, 'review_provenance': provenance}


def coverage(reviewed, results, evidence_ids):
    actual = {item['check_id']: check_receipt(item, evidence)
              for item, evidence in zip(results, evidence_ids)}
    spec = next(review for review in reviewed['reviews'] if review['axis'] == 'spec')
    return [{'ac_id': item['ac_id'], 'observed_status': item['status'], 'basis': item['basis'],
             'check_mapping': 'declared' if 'check_ids' in item else 'not_recorded',
             'checks': [actual.get(key, {'check_id': key, 'status': 'not_run', 'evidence_id': None})
                        for key in item.get('check_ids', [])],
             'review_observers': reviewed['review_provenance']} for item in spec['acceptance_results']]


def verify(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    operation_id, run_id, store, verification_id = identifier(), None, None, None
    try:
        with writer_lock(root) as generation:
            store = Store(root)
            run_id, previous = store.start(request, action='verify', method='run', owner='evolve-verify')
            if previous is not None:
                return previous
            change, revision, task, definition = change_context(store, request, allow_archived=True)
            fresh_checks(request['input'], definition)
            if definition['required_checks']:
                require_effect(request, 'checks')
            if revision['accepted_event_id'] is None:
                raise EvolveError('PLAN_ACCEPTANCE', 'An unaccepted candidate cannot be verified as applied work')
            snapshot = fingerprint(root, definition)
            reviewed = review_items(store, change, revision, definition, snapshot, request['input'].get('reviews'))
            from .work import workspace_work
            from .cross_dependencies import snapshot as dependency_snapshot, proofs
            verification_context = {'workspace_work': workspace_work(store.connection, snapshot, change['id']),
                'required_dependency_basis': dependency_snapshot(store.connection, change['id'], request['input']),
                'required_dependency_proofs': proofs(store.connection, change['id'], request['input']),
                'scope': 'actual_whole_working_directory_including_untracked_inputs',
                'independent_isolation': 'not_asserted', 'observed_at': now()}
            reviewed['verification_context'] = verification_context
            if definition.get('structured'):
                reviewed.update({'task_id': definition.get('_task_id'),
                                 'verification_scope': 'change' if definition.get('whole_change') else 'task'})
            symptom = symptom_reverification(store, task, definition, snapshot, request['input'].get('symptom_result'))
            expected = versions(store, change['id'], task['id'])
            claim_resources(store, run_id, operation_id, generation, change, definition['scope'], 'project_records')
            verification_id = identifier()
            with store.transaction() as connection:
                connection.execute("UPDATE operations SET state='running' WHERE id=?", (operation_id,))
                connection.execute('INSERT INTO verifications VALUES (?,?,?,?,?,?,?,?,?)',
                                   (verification_id, change['id'], revision['id'], run_id, 'applied', 'not_run',
                                    canonical(snapshot).decode(), canonical(reviewed).decode(), now()))
        results, evidence_ids = [], []
        for check in check_basis(root, definition):
            with writer_lock(root):
                gate(store, request, run_id, operation_id, expected)
                require_workspace(root, definition, snapshot, 'Workspace changed before acceptance check', check_id=check['id'])
            result = execute_check(store, request, run_id, operation_id, expected, definition, snapshot, check)
            with writer_lock(root):
                gate(store, request, run_id, operation_id, expected)
                observed = fingerprint(root, definition)
                if observed['digest'] != snapshot['digest']:
                    result['workspace_change'] = workspace_change(snapshot, observed, check_id=check['id'])
                with store.transaction():
                    evidence_ids.append(record_check(store, run_id, result, verification_id=verification_id))
            results.append(result)
            if result['unfinished_processes']:
                raise EvolveError('CHECK_RUNNING', 'A check process group is still present; verification is not complete', exit_code=4, committed=True)
            if result.get('workspace_change'):
                break
        from .external_work import verification_basis
        external_goals = verification_basis(store.connection, root, change, revision, task, definition, request)
        with writer_lock(root):
            gate(store, request, run_id, operation_id, expected)
            current = fingerprint(root, definition)
            from .structured import implementation_state
            complete, implementation = implementation_state(store.connection, root, change, revision, task, definition)
            from .formal import verification_applications
            _, documents = verification_applications(store.connection, root, change, revision, task, definition)
            changed = current['digest'] != snapshot['digest']
            missing = [p for p, value in current['scope'].items() if value is None]
            blocked = any(g['status'] != 'passed' for g in external_goals.values()) or changed or bool(missing) or not complete or not implementation or any(
                result['status'] == 'blocked' for result in results)
            if implementation and implementation['fingerprint']['scope'] != current['scope']:
                blocked = True
            failed = any(result['status'] == 'failed' for result in results) or bool(reviewed['unresolved_prior_findings'])
            if symptom:
                failed |= symptom['status'] == 'failed'
                blocked |= symptom['status'] == 'blocked'
            for review in reviewed['reviews']:
                failed |= any(finding['blocking'] for finding in review['findings'])
                if review['axis'] == 'spec':
                    failed |= any(a['status'] == 'failed' for a in review['acceptance_results'])
                    blocked |= any(a['status'] == 'blocked' for a in review['acceptance_results'])
            status = 'blocked' if blocked else 'failed' if failed else 'passed'
            items = {**reviewed, 'document_applications': documents, 'checks': [check_receipt(result, evidence_ids[i]) for i, result in enumerate(results)],
                     'workspace_changed': changed, 'missing': missing,
                     'workspace_change': workspace_change(snapshot, current),
                     'changes_during_checks': [result['workspace_change'] for result in results if result.get('workspace_change')],
                     'change_state': change['state'],
                     'required_tasks_complete': complete,
                     'implementation_scope_matches': bool(implementation and implementation['fingerprint']['scope'] == current['scope'])}
            items['coverage'] = coverage(reviewed, results, evidence_ids)
            if external_goals:
                items['external_goal_observations'] = external_goals
            if symptom:
                items['symptom_result'] = symptom
            with store.transaction() as connection:
                connection.execute('UPDATE verifications SET status=?,items_json=?,observed_at=? WHERE id=?',
                                   (status, canonical(items).decode(), now(), verification_id))
                for application_id in documents.values():
                    connection.execute('UPDATE spec_applications SET verification_id=? WHERE id=?', (verification_id, application_id))
                for review in reviewed['reviews']:
                    evidence_id = identifier()
                    blob = store.blob(canonical(review))
                    connection.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)',
                                       (evidence_id, run_id, verification_id, 'applied', review['observer'],
                                        'review:' + review['axis'], blob, now(), 'Semantic assessment by the named observer'))
                if symptom:
                    blob = store.blob(canonical(symptom))
                    connection.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)',
                        (identifier(), run_id, verification_id, 'applied', symptom['observer'],
                         'symptom_reverification', blob, symptom['observed_at'], canonical(symptom['limitations']).decode()))
                connection.execute("UPDATE operations SET state='committed',result_json=? WHERE id=?",
                                   (canonical({'verification_id': verification_id, 'status': status}).decode(), operation_id))
                connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                store.event(run_id, 'verification_observed', {'verification_id': verification_id, 'status': status,
                                                            'fingerprint_digest': snapshot['digest']})
            return store.finish(run_id, {'committed': True, 'outcome': 'verified', 'status': status,
                                'verification_id': verification_id, 'fingerprint_digest': snapshot['digest'],
                                'change_id': change['id'], 'revision_id': revision['id'],
                                'change_state': change['state'],
                                'task_id': definition.get('_task_id'),
                                'verification_scope': 'task' if definition.get('_task_id') else 'change',
                                'versions': expected, 'checks': items['checks'],
                                'coverage': items['coverage'], 'review_provenance': reviewed['review_provenance'],
                                'workspace_change': items['workspace_change'], 'changes_during_checks': items['changes_during_checks'],
                                'verification_context': verification_context,
                                'unresolved_prior_findings': reviewed['unresolved_prior_findings']})
    except EvolveError as error:
        if store is not None and run_id is not None:
            if not store.run_started(run_id):
                error.committed = True
                raise
            with writer_lock(root):
                unresolved = pending_checks(store.connection, run_id)
                with store.transaction() as connection:
                    if verification_id is not None:
                        connection.execute("UPDATE verifications SET status='blocked' WHERE id=?", (verification_id,))
                    if not unresolved:
                        connection.execute("UPDATE operations SET state='failed' WHERE id=?", (operation_id,))
                        connection.execute('DELETE FROM resource_claims WHERE operation_id=?', (operation_id,))
                    store.event(run_id, 'verification_blocked', {'message': str(error)})
                if not unresolved:
                    store.finish(run_id, {'committed': True, 'outcome': 'blocked', 'message': str(error)}, status='blocked')
                error.committed = True
        raise
    finally:
        if store is not None:
            store.close()
