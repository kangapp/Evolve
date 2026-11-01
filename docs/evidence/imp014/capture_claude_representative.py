"""Capture completed representative cases and the real quota stop, before continuation.

This collects facts only. The primary semantic review is a separate document.
"""
import collections
import hashlib
import json
from pathlib import Path
import sys
import zipfile


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    output = Path(__file__).resolve().parent
    frozen = json.loads(Path('/tmp/evolve-imp014-claude-safe-io-current.json').read_text())
    lab = Path(frozen['native_lab'])
    project, evidence = lab / 'business', lab / 'evidence'
    summary = json.loads((evidence / 'summary.json').read_text())
    assert not summary['automated_checks_passed'] and [c['case'] for c in summary['cases']] == [
        'propose', 'refactor_pause', 'cosmetic_revision', 'continue']
    interrupted = json.loads((evidence / 'local_revision-model.json').read_text())
    assert interrupted['transport_stop']['basis']['error_status'] == 429
    sys.path.insert(0, str(Path(frozen['package']) / 'runtime'))
    from evolve_core.continuation import sealed_result
    from evolve_core.package import canonical, check_package, digest
    from evolve_core.protection import managed_index
    from evolve_core.reading import history_snapshot
    trajectory = []
    for case in summary['cases']:
        name = case['case']
        raw = json.loads((evidence / (name + '-model.json')).read_text())
        events = [json.loads(line) for line in raw['stdout'].splitlines() if line.strip()]
        calls, messages = {}, []
        for event in events:
            content = event.get('message', {}).get('content', [])
            for item in content if isinstance(content, list) else []:
                if item['type'] == 'tool_use':
                    calls[item['id']] = {'id': item['id'], 'name': item['name'], 'input': item['input']}
                elif item['type'] == 'tool_result':
                    calls.setdefault(item['tool_use_id'], {'id': item['tool_use_id']})['result'] = item
                elif item['type'] == 'text' and event.get('type') == 'assistant':
                    messages.append(item['text'])
        results = [event for event in events if event.get('type') == 'result']
        assert raw['exit_code'] == 0 and len(results) == 1
        assert not results[0].get('is_error') and not results[0].get('permission_denials')
        trajectory.append({'case': name, 'tools': list(calls.values()), 'assistant_texts': messages,
                           'native_results': results, 'tool_counts': dict(collections.Counter(c['name'] for c in calls.values()))})
    save(output / 'claude-representative-trajectory-010-r4.json', {
        'status': 'four_completed_cases_for_primary_review_original_seven_case_batch_not_passed',
        'cases': trajectory, 'interrupted_local_revision': interrupted['transport_stop']})
    tables = ('changes', 'tasks', 'plan_revisions', 'verifications', 'phase_runs', 'events', 'evidence',
              'source_runs', 'input_checks', 'operations', 'artifacts', 'artifact_versions', 'rule_bindings', 'knowledge_proposals')
    with history_snapshot(project) as (connection, meta):
        rows = {table: [dict(row) for row in connection.execute('SELECT * FROM ' + table)] for table in tables}
        for row in rows['phase_runs']:
            sealed_result(connection, {'run_id': row['id'], 'result_digest': row['result_digest']})
        blobs = list(connection.execute('SELECT digest,content FROM blobs'))
        assert all(digest(row['content']) == row['digest'] for row in blobs)
        for source in rows['source_runs']:
            sealed_result(connection, {'run_id': source['source_run_id'], 'result_digest': source['result_digest']})
            assert any(check['run_id'] == source['run_id'] and check['target_id'] == source['source_run_id']
                       and check['expected_digest'] == source['result_digest'] and check['purpose'] == source['purpose']
                       and json.loads(check['result'])['status'] == 'passed' for check in rows['input_checks'])
        index_bytes = (project / '.evolve-local/control/managed.json').read_bytes()
        guard = json.loads((project / '.evolve-local/control/guard.json').read_text())
        assert json.loads(index_bytes) == managed_index(connection, meta)
        assert guard['managed_index_digest'] == digest(index_bytes)
        for item in json.loads(index_bytes)['files']:
            assert digest((project / item['path']).read_bytes()) == item['digest']
        assert connection.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0] == 0
        assert all(row['status'] != 'started' for row in rows['phase_runs'])
        facts = {'project_meta': meta, 'rows': rows, 'blob_count': len(blobs), 'integrity': {
            'all_saved_inputs_results_blobs_sources_valid': True, 'all_source_uses_have_actual_input_checks': True,
            'guard_matches_actual_sqlite_checkpoint_and_registered_files': True, 'live_runs': 0, 'resource_claims': 0}}
    facts['business_files'] = {p.name: {'content': p.read_text(), 'sha256': digest(p.read_bytes())}
                               for p in sorted(project.glob('*.py'))}
    facts['installed_roots'] = {}
    for key in ('registered_installation_root', 'host_cache_root'):
        actual = check_package(Path(summary[key]))['content_digest']
        assert actual == frozen['package_digest']
        facts['installed_roots'][key] = actual
    save(output / 'claude-representative-runtime-facts-010-r4.json', facts)
    archive = output / 'claude-representative-with-quota-stop-evidence.zip'
    skipped = []
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(lab.rglob('*')):
            relative = path.relative_to(lab)
            if path.is_symlink():
                skipped.append(str(relative))
                continue
            if not path.is_file() or '__pycache__' in relative.parts or path.suffix in ('.pyc', '.pyo'):
                continue
            assert path.name not in ('auth.json', '.credentials.json')
            bundle.write(path, relative)
    receipt = {'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
               'bytes': archive.stat().st_size, 'skipped_symlinks': skipped,
               'cases': [case['case'] for case in trajectory],
               'bash_commands': sum(case['tool_counts'].get('Bash', 0) for case in trajectory),
               'status': 'actual_facts_collected_primary_semantic_review_required'}
    receipt['original_seven_case_batch_passed'] = False
    receipt['quota_stop'] = interrupted['transport_stop']
    save(output / 'claude-representative-capture.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
