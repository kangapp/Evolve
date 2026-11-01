#!/usr/bin/env python3
"""Replay controlled cross-work fixtures through an independent public CLI.

Fixture assertions supply literal expectations and explicitly controlled reviews;
no model is called and no review is labelled independent-model validation.
"""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def run(package, output, *, learning_cycle=False, daily_cycle=False, recovery_cycle=False):
    package, output = Path(package).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(package / 'runtime'))
    from evolve_core.package import OWNERS, canonical, digest, check_package
    from evolve_core.errors import EvolveError
    manifest = check_package(package)
    sys.path.insert(0, str(ROOT / 'tests'))
    import test_cross_dependencies as cross
    import test_cross_formal_dependencies as formal
    import test_structured_diagnostics as diagnostic
    commands, cases = [], []
    actions = {
        ('evolve_core.connect', 'connect'): ('init', 'connect'),
        ('evolve_core.plans', 'propose'): ('propose', 'create'),
        ('evolve_core.apply', 'implement'): ('apply', 'implement'),
        ('evolve_core.verify', 'verify'): ('verify', 'run'),
        ('evolve_core.archive', 'archive'): ('archive', 'close'),
        ('evolve_core.cancellation', 'cancel_change'): ('maintain', 'cancel'),
        ('evolve_core.maintenance', 'backup'): ('maintain', 'backup'),
        ('evolve_core.maintenance', 'restore'): ('maintain', 'restore'),
        ('evolve_core.maintenance', 'upgrade'): ('maintain', 'upgrade'),
        ('evolve_core.revisions', 'revise'): ('update', 'revise'),
        ('evolve_core.knowledge', 'propose_baseline'): ('init', 'baseline.propose'),
        ('evolve_core.knowledge', 'apply_baseline'): ('init', 'baseline.apply'),
        ('evolve_core.knowledge_proposals', 'propose_knowledge'): ('sync', 'propose'),
        ('evolve_core.knowledge_proposals', 'check_candidate'): ('sync', 'check'),
        ('evolve_core.knowledge_proposals', 'review_candidates'): ('sync', 'review'),
        ('evolve_core.formal', 'apply_knowledge'): ('sync', 'apply'),
        ('evolve_core.formal', 'verify_knowledge'): ('verify', 'knowledge'),
        ('evolve_core.learning', 'learn'): ('learn', None),
        ('evolve_core.learning', 'search'): ('learn', 'search'),
        ('evolve_core.analysis', 'investigate'): ('analyze', 'investigate'),
        ('evolve_core.reading', 'current_state'): ('status', 'show'),
        ('evolve_core.resume', 'resume_view'): ('resume', 'show'),
        ('evolve_core.exporting', 'export_analysis'): ('maintain', 'export'),
    }

    def call(root, payload=None, *, action, method, target=None):
        argv = [sys.executable, '-B', str(package / 'runtime/evolve.py'), '--project', str(root), action]
        if target:
            argv.append(target)
        argv += ['--owner', 'evolve-' + OWNERS[action], '--method', method]
        if payload is not None:
            argv += ['--request', '-']
        result = subprocess.run(argv, input=json.dumps(payload) if payload is not None else None,
            cwd=output, capture_output=True, text=True, timeout=60)
        response = json.loads(result.stdout)
        commands.append({'argv': argv, 'request': payload, 'exit_code': result.returncode,
                         'response': response, 'stderr': result.stderr})
        (output / 'commands.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2))
        if not response['ok']:
            raise EvolveError(response['error']['code'], response['error']['message'],
                              exit_code=result.returncode, committed=response['data'].get('committed'))
        assert result.returncode == 0
        saved = {key: value for key, value in response['data'].items() if key not in ('request_context', 'input_bindings')}
        if action == 'analyze':
            receipt_digest = saved.pop('result_digest')
            assert receipt_digest == digest(canonical(saved))
        return saved

    def wrapper(action, original_method):
        def invoke(root, payload=None, *args, **kwargs):
            method = kwargs.pop('method', original_method)
            if action == 'status':
                return call(root, action=action, method='show', target=payload)['project']
            if action == 'resume':
                return call(root, action=action, method='show', target=payload)['context']
            if (action, method) == ('learn', 'search'):
                return call(root, action=action, method=method, target=payload)
            # The selected fixtures use explicit owning entry points; no owner
            # override is used to turn a Sync request into another write action.
            assert not args and not kwargs, (args, kwargs)
            return call(root, payload, action=action, method=method)
        return invoke

    selected = [
        (cross.CrossDependencyTests, 'test_done_is_not_verified_and_produced_inputs_are_not_frozen_as_old_context'),
        (cross.CrossDependencyTests, 'test_upstream_cancellation_invalidates_only_real_downstream_and_preserves_old_results'),
        (cross.CrossDependencyTests, 'test_real_upstream_revision_requires_rebinding_instead_of_silently_following_latest'),
        (formal.CrossFormalTests, 'test_verified_formal_dependency_retains_both_owner_meanings'),
        (formal.CrossFormalTests, 'test_external_formal_edit_stops_only_related_b_and_keeps_approval'),
        (formal.CrossFormalTests, 'test_known_conflicting_approved_successor_is_rejected_before_file_write'),
        (formal.CrossFormalTests, 'test_whole_acceptance_retains_first_owner_after_other_change_composes'),
        (diagnostic.StructuredDiagnosticTests, 'test_single_task_root_binding_requires_original_post_repair_observation'),
    ]
    if learning_cycle:
        import test_learning_cycle as learning
        selected = [(learning.LearningCycleTests, 'test_actual_counterexample_to_check_fix_and_scoped_feedback')]
    if daily_cycle:
        import test_daily_workflows as daily
        selected = [(daily.DailyWorkflowTests, 'test_four_cases_keep_shared_integration_deferral_and_later_negative_truthful'),
                    (daily.DailyWorkflowTests, 'test_missing_environment_does_not_succeed_or_create_replacement_tests')]
    if recovery_cycle:
        import test_maintenance as recovery
        # Fault children must load this exact frozen package, rather than source HEAD.
        recovery.ROOT = package
        selected = [(recovery.MaintenanceTests, name) for name in (
            'test_corrupt_restore_protects_raw_database_sidecar_extra_managed_and_unknown_files',
            'test_plan_binds_bytes_selected_package_and_preserves_unregistered_collision',
            'test_held_old_sqlite_connection_and_real_old_writer_block_swap',
            'test_unknown_check_launch_needs_specific_observation_and_real_group_must_end',
            'test_external_running_reference_survives_older_archive_as_unknown',
            'test_missing_external_index_remains_unverified_not_empty_safe',
            'test_explicit_protocol_upgrade_changes_epoch_and_preserves_history',
            'test_actual_abrupt_exit_at_every_swap_boundary_resumes_same_request',
            'test_third_party_value_after_partial_swap_is_preserved_with_barrier',
            'test_changed_swap_journal_cannot_expand_the_presented_restore_collection',
            'test_unknown_launch_observation_is_bound_and_missing_check_index_is_not_safe',
            'test_actual_divergent_archives_keep_both_branches_and_restore_only_the_selected_one',
            'test_manual_backup_does_not_trigger_another_full_daily_backup',
            'test_manual_backup_retry_and_next_write_after_restore_keep_old_daily_points')]
    with ExitStack() as stack:
        if recovery_cycle:
            # Module-qualified calls use the same public seam as imported owner functions.
            import evolve_core.maintenance as maintenance
            for name in ('backup', 'restore', 'upgrade'):
                stack.enter_context(patch.object(maintenance, name, wrapper('maintain', name)))
        for module_name, module in list(sys.modules.items()):
            if module is None or not (module_name.startswith('test_') or module_name.endswith('_fixture')):
                continue
            for name, value in list(vars(module).items()):
                spec = actions.get((getattr(value, '__module__', None), getattr(value, '__name__', None)))
                if spec:
                    stack.enter_context(patch.object(module, name, wrapper(*spec)))
        for cls, name in selected:
            case = cls(name)
            start = len(commands)
            try:
                case.setUp()
                getattr(case, name)()
                project = case.f.root if hasattr(case, 'f') else case.root
                destination = output / ('project-' + str(len(cases) + 1))
                shutil.copytree(project, destination)
                cases.append({'case': cls.__name__ + '.' + name, 'commands': len(commands) - start, 'passed': True,
                              'project_snapshot': destination.name})
            finally:
                case.doCleanups()
    summary = {'passed': True, 'package_version': manifest['package_version'], 'content_digest': manifest['content_digest'],
        'commands': len(commands), 'cases': cases, 'model_requests_sent': False,
        'review_inputs': 'Controlled actual fixture observations; not independent model review'}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.package, args.out), ensure_ascii=False, indent=2))
