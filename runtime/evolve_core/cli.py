"""JSON CLI; read-only commands do not initialize or repair projects."""
import argparse
import json
from pathlib import Path
import sys
import sqlite3
from .errors import EvolveError
from .package import OWNERS, METHODS, AVAILABLE, ROOT, check_package
from .reading import current_state
from .requests import normalize


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise EvolveError("INPUT", message)


def project_status(root, target=None):
    try:
        return current_state(root, target)
    except EvolveError as error:
        if error.code == 'PATH':
            raise EvolveError('PROJECT_PATH', str(error), exit_code=error.exit_code)
        raise


def execute_request(args, method):
    if not args.request:
        raise EvolveError('REQUEST_REQUIRED', 'The host must supply an explicit JSON request with the actual authorization source')
    try:
        raw = json.loads(sys.stdin.read() if args.request == '-' else Path(args.request).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise EvolveError('INPUT', 'Cannot read the explicit JSON request: ' + str(error))
    fresh = isinstance(raw, dict) and 'request_id' not in raw
    request = normalize(raw)
    data = request['input']
    root = Path(args.project).resolve()
    external_observation = args.action == 'apply' and method in ('external.reconcile', 'external.record')
    external_cancellation = (args.action, method) == ('maintain', 'cancel') and bool(data.get('external_operation_id'))
    cancelling = (args.action, method) == ('maintain', 'cancel') and not external_cancellation
    if args.target and args.action not in ('apply', 'verify', 'archive', 'update') and not cancelling:
        raise EvolveError('TARGET', 'This method takes typed targets in JSON input, not an extra positional target')
    answer_only = args.action == 'analyze' and data.get('record_intent') == 'answer_only'
    existing_connection = (root / 'evolve/config.toml').is_file() and (root / 'evolve/history.db').is_file()
    initial_path = root / '.evolve-local/control/init.json'
    incomplete_init = not answer_only and initial_path.is_file() and json.loads(initial_path.read_text()).get('state') != 'committed'
    offline_maintenance = args.action == 'maintain' and method in ('restore', 'upgrade')
    if offline_maintenance:
        # A corrupt or old-protocol DB cannot supply normal status. Apply retries
        # keep the old identity from their immutable plan, even after epoch swap.
        from .maintenance import stage_path, raw_history
        from .protection import protected_identity
        if data.get('stage', 'plan') == 'apply':
            plan = json.loads((stage_path(root, data.get('plan_id')) / 'plan.json').read_text())
            identity = {'project_id': plan['project_id'], 'expected_workspace_epoch': plan['old_epoch']}
        elif method == 'restore':
            guard, _ = protected_identity(root)
            identity = {'project_id': guard['project_id'], 'expected_workspace_epoch': guard['workspace_epoch']}
        else:
            meta = raw_history(root)[0]
            identity = {'project_id': meta['project_id'], 'expected_workspace_epoch': meta['workspace_epoch']}
        for key, value in identity.items():
            if key not in request:
                if not fresh:
                    raise EvolveError('INPUT', 'Maintenance retries preserve their original project identity')
                request[key] = value
    if not offline_maintenance and not answer_only and ((args.action, method) != ('init', 'connect') or (existing_connection and not incomplete_init)):
        initial = root / '.evolve-local/control/init.json'
        if args.action == 'maintain' and method == 'recover' and initial.is_file() and json.loads(initial.read_text()).get('state') != 'committed':
            journal = json.loads(initial.read_text())
            state = {'project_id': journal['project_id'], 'workspace_epoch': journal['workspace_epoch'], 'changes': []}
        else:
            if (args.action, method) == ('maintain', 'export'):
                from .reading import history_snapshot
                from .store import schema_compatible
                with history_snapshot(root) as (connection, meta):
                    state = {'state': 'connected', 'project_id': meta['project_id'],
                             'workspace_epoch': meta['workspace_epoch'], 'write_compatible': schema_compatible(connection)}
            else:
                state = project_status(root)
            if state['state'] == 'maintenance':
                raise EvolveError('MAINTENANCE_ACTIVE', 'Resume the exact original maintenance request before managed work', exit_code=4)
            if state['state'] != 'connected':
                raise EvolveError('NOT_CONNECTED', 'Explicit init is required before this action')
            if not state.get('write_compatible'):
                raise EvolveError('SCHEMA_VERSION', 'Existing history is readable but requires an explicit supported migration before writes')
        for key in ('project_id', 'expected_workspace_epoch'):
            observed = state['project_id' if key == 'project_id' else 'workspace_epoch']
            if key not in request:
                if not fresh:
                    raise EvolveError('INPUT', 'Retries must preserve their complete prepared identity and epoch')
                request[key] = observed
        if not request.get('project_id') or not request.get('expected_workspace_epoch'):
            raise EvolveError('PROJECT_INVALID', 'History does not expose a supported writable project identity')
        if (cancelling or (args.action == 'apply' and not external_observation) or args.action in ('archive', 'update') or (args.action == 'verify' and method == 'run')
                or (args.action == 'sync' and method == 'apply' and data.get('change_id'))
                or (args.action == 'init' and method == 'baseline.apply' and data.get('change_id'))
                or (args.action == 'learn' and method == 'promote' and data.get('stage') == 'apply' and data.get('change_id'))):
            target = data.get('change_id') or args.target
            if not target:
                raise EvolveError('TARGET', 'An explicit or uniquely resolved work item is required')
            selected = [c for c in state['changes'] if target in (c['id'], c['code'], c['title'])]
            if len(selected) != 1:
                raise EvolveError('TARGET', 'Work item is missing or ambiguous')
            selected = selected[0]
            complex_work = selected['complexity'] == 'complex'
            task = None
            if not fresh:
                required = ['change_id', 'revision_id', 'definition_digest'] + (['task_id'] if 'tasks' in request.get('expected_versions', {}) else [])
                if args.action in ('apply', 'sync', 'init', 'learn'): required.append('accepted_plan_digest')
                if any(key not in data for key in required) or 'expected_versions' not in request:
                    raise EvolveError('INPUT', 'Retry omitted its original prepared revision/task bindings')
                bindings = {key: data[key] for key in required}
                expected = request['expected_versions']
            elif args.action == 'update' or cancelling:
                if data.get('task_id') is not None or data.get('task_key') is not None:
                    raise EvolveError('WHOLE_CHANGE_REQUIRED', 'Update revises the whole plan')
                expected = ({'change': selected['row_version'], 'tasks': {t['id']: t['row_version'] for t in selected['tasks']}}
                            if complex_work else {'change': selected['row_version'], 'task': selected['tasks'][0]['row_version']})
                bindings = {'change_id': selected['id'], 'revision_id': selected['current_revision'],
                            'definition_digest': selected['definition_digest']}
                if complex_work: bindings['task_id'] = None
            elif complex_work:
                target_task = data.get('task_id') or data.get('task_key')
                if args.action == 'archive' and target_task:
                    raise EvolveError('WHOLE_CHANGE_REQUIRED', 'Archive closes the whole change, never one task')
                if target_task:
                    matches = [t for t in selected['tasks'] if target_task in (t['id'], t['local_key'], t['task_code'])]
                    if len(matches) != 1:
                        raise EvolveError('TASK_TARGET', 'Task is missing or ambiguous in the current revision')
                    task = matches[0]
                elif args.action in ('apply', 'sync', 'init', 'learn'):
                    ready = [t for t in selected['tasks'] if t['readiness']['ready']]
                    if not ready:
                        raise EvolveError('DEPENDENCY_NOT_READY', 'No task is ready; inspect task conditions or select the task requiring a failure-backed fix')
                    task = ready[0]
                expected = {'change': selected['row_version'], 'tasks': {t['id']: t['row_version'] for t in selected['tasks']}}
            else:
                if len(selected['tasks']) != 1:
                    raise EvolveError('TARGET', 'Simple work requires exactly one task')
                task = selected['tasks'][0]
                expected = {'change': selected['row_version'], 'task': task['row_version']}
            if fresh and args.action != 'update':
                bindings = {'change_id': selected['id'], 'revision_id': selected['current_revision'],
                            'definition_digest': task['definition_digest'] if task else selected['definition_digest']}
                if complex_work: bindings['task_id'] = task['id'] if task else None
                if args.action in ('apply', 'sync', 'init', 'learn'): bindings['accepted_plan_digest'] = selected['plan_digest']
            for key, value in bindings.items():
                if key not in data:
                    if not fresh:
                        raise EvolveError('INPUT', 'Retry omitted its original binding: ' + key)
                    data[key] = value
            if 'expected_versions' not in request:
                if not fresh:
                    raise EvolveError('INPUT', 'Retry omitted its original expected versions')
                request['expected_versions'] = expected
    from .connect import connect
    from .plans import propose
    from .apply import implement
    from .verify import verify
    from .archive import archive
    from .knowledge import propose_baseline, apply_baseline
    from .recover import recover
    from .analysis import investigate
    from .learning import learn
    from .revisions import revise
    from .knowledge_proposals import propose_knowledge, check_candidate, review_candidates
    from .formal import apply_knowledge, verify_knowledge
    from .exporting import export_analysis
    from .cancellation import cancel_change
    from .maintenance import backup, restore, upgrade
    from .external import execute as external_execute, reconcile as external_reconcile
    from .external_actions import record as external_record, compensate as external_compensate
    from .project_knowledge import survey as knowledge_survey, complete as knowledge_complete
    from .knowledge_facts import maintain as maintain_facts
    from .knowledge_impact import assess as assess_knowledge
    handlers = {('apply', 'external.execute'): external_execute, ('apply', 'external.reconcile'): external_reconcile,
                ('apply', 'external.record'): external_record, ('apply', 'external.compensate'): external_compensate,
                ('init', 'connect'): connect, ('init', 'survey'): knowledge_survey, ('init', 'complete'): knowledge_complete,
                ('init', 'baseline.propose'): propose_baseline,
                ('init', 'baseline.apply'): apply_baseline, ('propose', 'create'): propose,
                ('apply', 'implement'): implement, ('verify', 'run'): verify,
                ('archive', 'close'): archive, ('maintain', 'recover'): recover,
                ('analyze', 'investigate'): investigate, ('update', 'revise'): revise,
                ('sync', 'propose'): propose_knowledge, ('sync', 'check'): check_candidate, ('sync', 'review'): review_candidates,
                ('sync', 'apply'): apply_knowledge, ('sync', 'facts'): maintain_facts, ('sync', 'assess'): assess_knowledge,
                ('verify', 'knowledge'): verify_knowledge,
                ('maintain', 'export'): export_analysis, ('maintain', 'cancel'): cancel_change, ('maintain', 'backup'): backup,
                ('maintain', 'restore'): restore, ('maintain', 'upgrade'): upgrade}
    result = (learn(root, request, method=method) if args.action == 'learn' else handlers[(args.action, method)](root, request))
    receipt = {}
    if args.action == 'analyze' or (args.action == 'apply' and method.startswith('external.')):
        from .package import canonical, digest
        receipt['result_digest'] = digest(canonical(result))
    context = {**{key: result[key] for key in ('project_id', 'workspace_epoch') if key in result}, **request}
    if 'expected_workspace_epoch' not in context and 'workspace_epoch' in context:
        context['expected_workspace_epoch'] = context['workspace_epoch']
    return {**result, **receipt, 'request_context': {key: context[key] for key in
            ('request_id', 'project_id', 'expected_workspace_epoch', 'expected_versions') if key in context},
            'input_bindings': {key: data[key] for key in ('change_id', 'revision_id', 'task_id', 'definition_digest', 'accepted_plan_digest') if key in data}}


def dispatch(args):
    action = args.action
    if action not in OWNERS:
        raise EvolveError("UNKNOWN_ACTION", "Unknown action: " + action)
    owner = "evolve-" + OWNERS[action]
    if args.owner and args.owner != owner:
        raise EvolveError("OWNER", f"Action belongs to {owner}")
    manifest = check_package()
    if action == "learn" and args.method is None:
        return {"committed": False, "methods": METHODS[action], "outcome": "usage"}
    method = args.method or METHODS[action][0]
    if method not in METHODS[action]:
        raise EvolveError("UNKNOWN_METHOD", f"Unknown method for {action}: {method}")
    if action + "." + method not in AVAILABLE:
        raise EvolveError("UNAVAILABLE", f"{action}.{method} is not implemented in this package",
                          next_steps=["Use status or maintain --method doctor to see actual capabilities"])
    duplicates = []
    for base in {Path(args.project).resolve(), Path.home()}:
        for channel in (".agents/skills", ".claude/skills", ".codex/skills"):
            for name in set(OWNERS.values()):
                path = base / channel / ("evolve-" + name) / "SKILL.md"
                if path.is_file():
                    duplicates.append(str(path))
    if duplicates:
        raise EvolveError("DUPLICATE_INSTALLATION", "Same-name standalone skills need source verification: "
                          + ", ".join(sorted(duplicates)), exit_code=3,
                          next_steps=["Choose one installation channel; preserve existing files until verified"])
    if (action, method) == ('init', 'templates'):
        if args.request:
            raise EvolveError('INPUT', 'Template discovery is a pure query')
        from .project_knowledge import templates
        return templates(args.target)
    if (action, method) == ('learn', 'search'):
        if args.request:
            raise EvolveError('INPUT', 'Experience search is a pure query without mutation requests')
        from .learning import search
        return search(Path(args.project), args.target)
    if (action, method) not in {('status', 'show'), ('next', 'show'), ('resume', 'show'), ('history', 'show'), ('maintain', 'doctor')}:
        return execute_request(args, method)
    if args.request:
        raise EvolveError('INPUT', 'Pure queries do not accept mutation requests')
    if action == 'history':
        from .resume import history_view
        return {'committed': False, 'run_id': None, 'outcome': 'observed', 'owner_skill': owner,
                'history': history_view(Path(args.project), args.target), 'package_root': str(ROOT),
                'package_version': manifest['package_version'], 'content_digest': manifest['content_digest']}
    if action in ('resume', 'next'):
        from .resume import resume_view
        return {'committed': False, 'run_id': None, 'outcome': 'observed', 'owner_skill': owner,
                'context': resume_view(Path(args.project), args.target), 'package_root': str(ROOT),
                'package_version': manifest['package_version'], 'content_digest': manifest['content_digest']}
    if args.target and action != 'status':
        raise EvolveError('INPUT', 'Doctor does not take a business target')
    return {"committed": False, "run_id": None, "outcome": "observed", "owner_skill": owner,
            "project": project_status(Path(args.project), args.target), "package_root": str(ROOT),
            "package_version": manifest["package_version"], "content_digest": manifest["content_digest"],
            "available_methods": manifest["available_methods"],
            "unavailable_methods": sorted(a + "." + m for a, ms in METHODS.items() for m in ms
                                          if a + "." + m not in AVAILABLE),
            "host_enablement": "not_observed", "warnings": []}


def main(argv=None):
    action = "status"
    try:
        parser = Parser(description="Evolve deterministic runtime (Python 3.11+)")
        parser.add_argument("--project", default=str(Path.cwd()), help="Explicit existing project root")
        parser.add_argument("action", nargs="?", default="status")
        parser.add_argument("target", nargs="?")
        parser.add_argument("--method")
        parser.add_argument("--request", help="Explicit host request JSON file, or - for stdin")
        parser.add_argument("--owner", help="Calling skill; checked against the owner map")
        args = parser.parse_args(argv)
        action = args.action
        data = dispatch(args)
        response = {"ok": True, "action": action, "operation_id": data.get("operation_id"), "data": data, "warnings": []}
        code = 0
    except EvolveError as error:
        response = {"ok": False, "action": action, "operation_id": None,
                    "data": {"committed": error.committed}, "warnings": [],
                    "error": {"code": error.code, "message": str(error), "next_steps": error.next_steps}}
        code = error.exit_code
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        response = {"ok": False, "action": action, "operation_id": None, "data": {"committed": None}, "warnings": [],
                    "error": {"code": "OBSERVATION_REQUIRED", "message": "Execution did not return a reliable result: " + type(error).__name__,
                              "next_steps": ["Inspect status and pending operations before retrying effects"]}}
        code = 1
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return code
