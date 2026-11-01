#!/usr/bin/env python3
"""Exercise native package lifecycle in disposable profiles, without model requests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys

from verify_hosts import NAMES, claude_skills, codex_skills
from workflow_smoke import run_workflow

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_files(project):
    # Native managers may edit their own settings; every business/control byte counts.
    return {p.relative_to(project).as_posix(): digest(p) for p in sorted(project.rglob('*'))
            if p.is_file() and p.relative_to(project).parts[0] not in ('.codex', '.claude')}



def history_facts(project):
    """Hashes of existing rows; reconnect may append facts but cannot rewrite them."""
    connection = sqlite3.connect(project / 'evolve/history.db')
    try:
        facts = {}
        for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            rows = {}
            for row in connection.execute('SELECT rowid,* FROM "' + table + '"'):
                if table == 'project_meta' and row[1] == 'checkpoint':
                    continue
                values = [hashlib.sha256(value).hexdigest() if isinstance(value, bytes) else value for value in row[1:]]
                rows[str(row[0])] = hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()
            facts[table] = rows
        return facts
    finally:
        connection.close()



def reconnect_protection_current(project):
    """Independently check that the changed protection still describes current facts."""
    control = project / '.evolve-local/control'
    encoded = (control / 'managed.json').read_bytes()
    managed = json.loads(encoded)
    guard = json.loads((control / 'guard.json').read_text())
    connection = sqlite3.connect((project / 'evolve/history.db').as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        meta = dict(connection.execute('SELECT key,value FROM project_meta'))
        files = [dict(r) for r in connection.execute("SELECT a.path,a.kind,v.blob_digest AS digest FROM artifacts a JOIN artifact_versions v ON v.id=a.current_version WHERE a.kind IN ('config','knowledge') AND a.path IS NOT NULL ORDER BY a.path")]
        return (hashlib.sha256(encoded).hexdigest() == guard.get('managed_index_digest')
                and all(guard.get(k) == managed.get(k) == meta[k] for k in ('project_id', 'workspace_epoch', 'checkpoint'))
                and managed.get('protocol_version') == meta['protocol_version']
                and managed.get('files') == files and managed.get('executions') == []
                and connection.execute("SELECT COUNT(*) FROM phase_runs WHERE status='started'").fetchone()[0] == 0)
    finally:
        connection.close()

def compatible_fixture(source, destination):
    """A complete test-only package, same code/schema/protocol, distinct version/digest."""
    shutil.copytree(source, destination)
    manifest_path = destination / 'evolve-package.json'
    manifest = json.loads(manifest_path.read_text())
    old_version = manifest['package_version']
    version = old_version + ('.lifecycle.1' if '-' in old_version else '-lifecycle.1')
    path = destination / 'runtime/evolve_core/__init__.py'
    text = path.read_text()
    before = 'VERSION = "' + old_version + '"'
    if text.count(before) != 1:
        raise ValueError('Unexpected fixture version declaration')
    path.write_text(text.replace(before, 'VERSION = "' + version + '"'))
    for host in ('codex', 'claude'):
        path = destination / ('.' + host + '-plugin/plugin.json')
        metadata = json.loads(path.read_text())
        metadata['version'] = version
        save(path, metadata)
    path = destination / 'CHANGELOG.md'
    path.write_text('# Controlled compatible lifecycle fixture ' + version + '\n\n'
                    'Test-only derivative; identical runtime semantics, schema and protocol. Not a public release.\n\n' + path.read_text())
    manifest['package_version'] = version
    manifest['files'] = {name: digest(destination / name) for name in manifest['files']}
    canonical = json.dumps(manifest['files'], sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    manifest['content_digest'] = hashlib.sha256(canonical).hexdigest()
    save(manifest_path, manifest)
    return manifest



def interrupted_workflow(runtime, project, env, run):
    """Actual stopped child in each installed runtime, then recovery and real closure."""
    auth = {'source': 'controlled lifecycle fixture',
            'text': 'In this disposable project, repair the externally reverted arithmetic implementation, preserve the original tests, recover the local interruption, run checks and close the new work item.',
            'effect_kinds': ['project_records', 'business_files', 'checks'],
            'paths': ['arithmetic.py', 'test_arithmetic.py']}

    def rows(sql, values=()):
        connection = sqlite3.connect(project / 'evolve/history.db')
        try:
            return connection.execute(sql, values).fetchall()
        finally:
            connection.close()

    def call(action, data, method=None):
        argv = [sys.executable, str(runtime), '--project', str(project), action, '--request', '-']
        if method:
            argv += ['--method', method]
        return json.loads(run(argv, env, payload={'authorization': auth, 'input': data}))['data']

    old_facts = {table: rows('SELECT * FROM ' + table) for table in ('changes', 'tasks', 'verifications')}
    test_before = (project / 'test_arithmetic.py').read_bytes()
    source = project / 'arithmetic.py'
    source.write_text('def total(values):\n    return len(values)  # controlled external regression\n')
    run([sys.executable, '-B', '-m', 'unittest', 'discover', '-v'], env, project, expected=1)
    text = 'Restore sum(values) after the controlled external regression; keep the original literal assertions and run the registered checks.'
    plan = call('propose', {'title': 'Repair external regression with interrupted local write', 'plan': text,
                'completion': 'Original independent examples and actual verification pass.',
                'scope': auth['paths'], 'required_checks': ['arithmetic-unit'],
                'acceptance': ['Original independent arithmetic assertions pass'],
                'presentation': {'source': 'controlled fixture plan presentation', 'text': text}})
    data = {'change_id': plan['change_id'], 'files': [{'path': 'arithmetic.py',
            'expected_digest': digest(source), 'content': 'def total(values):\n    return sum(values)\n'}]}
    child = '''
import importlib,os,sys
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
app=importlib.import_module('evolve_core.apply')
from evolve_core.cli import main
with patch.object(app,'fingerprint',side_effect=lambda *a,**k:os._exit(35)):
    sys.exit(main(['--project',sys.argv[2],'apply','--request','-']))
'''
    run([sys.executable, '-B', '-c', child, str(runtime.parent), str(project)], env,
        expected=35, payload={'authorization': auth, 'input': data})
    state = json.loads(run([sys.executable, str(runtime), '--project', str(project), 'status'], env))['data']['project']
    if len(state['pending_runs']) != 1 or len(state['pending_runs'][0]['operations']) != 1:
        raise AssertionError('Interrupted installed runtime did not retain the actual operation')
    original = state['pending_runs'][0]
    operation_id = original['operations'][0]['id']
    evidence_before = rows('SELECT * FROM evidence')
    recovered = call('maintain', {'operation_id': operation_id}, 'recover')
    if (recovered['outcome'] != 'recovered_local' or recovered['checks'] != 'not_run'
            or recovered['business_commands_run'] or rows('SELECT * FROM evidence') != evidence_before
            or rows('SELECT state FROM tasks WHERE id=?', (plan['task_id'],))[0][0] != 'in_progress'):
        raise AssertionError('Recovery erased facts or invented completed checks')
    data['files'][0]['expected_digest'] = digest(source)
    applied = call('apply', data)
    reviews = [{'axis': axis, 'observer': 'controlled fixture self-inspection',
                'summary': 'Inspected the one-line sum and unchanged original literal assertions; fixture input, not an independent model review.',
                'fingerprint_digest': applied['fingerprint']['digest'], 'findings': []}
               for axis in ('spec', 'standards')]
    reviews[0]['acceptance_results'] = [{'ac_id': ac['id'], 'status': 'passed',
                'basis': 'Actual registered unittest ran the unchanged three original literal assertions.'} for ac in plan['acceptance']]
    verified = call('verify', {'change_id': plan['change_id'], 'reviews': reviews})
    archived = call('archive', {'change_id': plan['change_id'], 'verification_id': verified['verification_id']})
    if verified['status'] != 'passed' or archived['outcome'] != 'archived' or (project / 'test_arithmetic.py').read_bytes() != test_before:
        raise AssertionError('Post-recovery real checks/closure or original tests failed')
    for table, old in old_facts.items():
        actual = rows('SELECT * FROM ' + table)
        if any(row not in actual for row in old):
            raise AssertionError('Fault workflow rewrote earlier ' + table)
    protection = json.loads((project / recovered['protection'] / 'manifest.json').read_text())
    return {'actual_child_exit_code': 35, 'original_run_id': original['id'], 'recovery_run_id': recovered['run_id'],
            'recovery_outcome': recovered['outcome'], 'recovery_checks': recovered['checks'],
            'recovery_business_commands_run': recovered['business_commands_run'],
            'protection_consistent_restore_package': protection['consistent_restore_package'],
            'prior_change_task_verification_rows_unchanged': True, 'literal_tests_unchanged': True,
            'post_recovery_verification': verified['status'], 'new_change_closed': archived['outcome']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='New directory; disposable owned fixtures only')
    args = parser.parse_args()
    lab = args.out.resolve()
    lab.mkdir(mode=0o700, parents=True, exist_ok=False)
    commands, summary = [], {'status': 'in_progress', 'model_requests_sent': False, 'checks': {},
        'limitations': ['macOS native execution only; Windows remains not_run',
                        'Compatible update uses a complete controlled derivative, not an actual published release',
                        'Review inputs in the arithmetic workflow are fixture observations, not independent model reviews',
                        'This lifecycle exercise does not cover migration/full archive restore; those have their own actual controlled acceptance']}

    def run(argv, env=None, cwd=lab, *, expected=0, payload=None):
        process = subprocess.run(argv, env=env, cwd=cwd, input=json.dumps(payload) if payload is not None else None,
                                 text=True, capture_output=True, timeout=60)
        commands.append({'argv': list(map(str, argv)), 'cwd': str(cwd), 'exit_code': process.returncode,
                         'stdout': process.stdout, 'stderr': process.stderr})
        save(lab / 'commands.json', commands)
        if process.returncode != expected:
            raise AssertionError('Unexpected exit: ' + ' '.join(map(str, argv)))
        return process.stdout

    def observe(name, condition):
        summary['checks'][name] = bool(condition)
        save(lab / 'summary.json', summary)
        if not condition:
            raise AssertionError(name)
        print(json.dumps({'check': name, 'passed': True}), flush=True)

    package = lab / '安装 space 中文'
    try:
        download = lab / 'download'
        run([sys.executable, str(ROOT / 'scripts/build_package.py'), '--out', str(download)])
        download.rename(package)
        old = json.loads((package / 'evolve-package.json').read_text())
        update = lab / 'compatible-update'
        new = compatible_fixture(package, update)
        summary.update(package_before=old['package_version'], digest_before=old['content_digest'],
                       package_after=new['package_version'], digest_after=new['content_digest'])
        other = lab / 'other-project'
        other.mkdir()
        projects, envs, caches, baselines = {}, {}, {}, {}
        for host in ('codex', 'claude'):
            project, profile = lab / (host + '-business'), lab / (host + '-profile')
            project.mkdir()
            profile.mkdir(mode=0o700)
            projects[host] = project
            env = {**os.environ, ('CODEX_HOME' if host == 'codex' else 'CLAUDE_CONFIG_DIR'): str(profile)}
            envs[host] = env
            summary[host + '_version'] = run([host, '--version']).strip()
            command = [host, 'plugin', 'marketplace', 'add', str(package)]
            command += ['--json'] if host == 'codex' else ['--scope', 'project']
            run(command, env, project)
            install = run([host, 'plugin', 'add' if host == 'codex' else 'install', 'evolve@evolve-local',
                           *(['--json'] if host == 'codex' else ['--scope', 'project'])], env, project)
            if host == 'codex':
                caches[host] = Path(json.loads(install)['installedPath'])
                config = profile / 'config.toml'
                config.write_text(config.read_text().replace('enabled = true', 'enabled = false') +
                                  '\n[projects.' + json.dumps(str(project)) + ']\ntrust_level="trusted"\n')
                (project / '.codex').mkdir()
                (project / '.codex/config.toml').write_text('[plugins."evolve@evolve-local"]\nenabled=true\n')
                discovery = codex_skills(env, project, other)
                observe('codex_initial_discovery', len(discovery[0]['skills']) == 8 and not discovery[1]['skills'])
            else:
                installed = json.loads(run(['claude', 'plugin', 'list', '--json'], env, project))
                caches[host] = Path(next(p['installPath'] for p in installed if p['id'] == 'evolve@evolve-local'))
                discovery = claude_skills(env, project)
                observe('claude_initial_discovery', discovery['complete'])
            save(lab / (host + '-initial-discovery.json'), discovery)
            # Claude native directory markets load in place; its cache is a distinct artifact.
            runtime = (caches[host] if host == 'codex' else package) / 'runtime/evolve.py'
            flow = run_workflow(runtime, project, lab / (host + '-workflow'))
            summary[host + '_project_id'] = flow['project_id']
            fault = interrupted_workflow(runtime, project, env, run)
            save(lab / (host + '-interrupted-workflow.json'), fault)
            observe(host + '_interrupted_workflow', fault['post_recovery_verification'] == 'passed')
            baselines[host] = project_files(project)
            save(lab / (host + '-project-baseline.json'), baselines[host])

        def preserved(host, step):
            observe(host + '_' + step + '_data_preserved', project_files(projects[host]) == baselines[host])

        # Stop all runtime calls before changing installation files. No live run is updated.
        for host in ('codex', 'claude'):
            project, env = projects[host], envs[host]
            if host == 'codex':
                (project / '.codex/config.toml').write_text('[plugins."evolve@evolve-local"]\nenabled=false\n')
                discovery = codex_skills(env, project, other)
                observe('codex_disabled_discovery', all(not row['skills'] for row in discovery))
            else:
                run(['claude', 'plugin', 'disable', 'evolve@evolve-local', '--scope', 'project'], env, project)
                installed = json.loads(run(['claude', 'plugin', 'list', '--json'], env, project))
                observe('claude_disabled_registration', not next(p for p in installed if p['id'] == 'evolve@evolve-local')['enabled'])
                discovery = claude_skills(env, project)
                observe('claude_disabled_discovery', not discovery['observed_skill_names'] and
                        bool(re.search(r'No\s*skills\s*found', discovery['local_ui_excerpt'], re.I)))
            save(lab / (host + '-disabled-discovery.json'), discovery)
            preserved(host, 'disabled')

        package.rename(lab / 'previous-complete-package')
        update.rename(package)
        # Codex 0.154.0 has no plugin update verb; use its supported remove/add pair.
        env, project = envs['codex'], projects['codex']
        run(['codex', 'plugin', 'remove', 'evolve@evolve-local', '--json'], env, project)
        preserved('codex', 'removed_for_update')
        installed = json.loads(run(['codex', 'plugin', 'add', 'evolve@evolve-local', '--json'], env, project))
        caches['codex'] = Path(installed['installedPath'])
        profile_config = lab / 'codex-profile/config.toml'
        profile_config.write_text(profile_config.read_text().replace('enabled = true', 'enabled = false'))
        (project / '.codex/config.toml').write_text('[plugins."evolve@evolve-local"]\nenabled=true\n')
        env, project = envs['claude'], projects['claude']
        run(['claude', 'plugin', 'marketplace', 'update', 'evolve-local'], env, project)
        run(['claude', 'plugin', 'update', 'evolve@evolve-local', '--scope', 'project'], env, project)
        run(['claude', 'plugin', 'enable', 'evolve@evolve-local', '--scope', 'project'], env, project)

        for host in ('codex', 'claude'):
            project, env = projects[host], envs[host]
            if host == 'claude':
                installed = json.loads(run(['claude', 'plugin', 'list', '--json'], env, project))
                caches[host] = Path(next(p['installPath'] for p in installed if p['id'] == 'evolve@evolve-local'))
            cache_manifest = json.loads((caches[host] / 'evolve-package.json').read_text())
            observe(host + '_compatible_update_cache', cache_manifest['content_digest'] == new['content_digest'])
            runtime = (caches[host] if host == 'codex' else package) / 'runtime/evolve.py'
            result = json.loads(run([sys.executable, str(runtime), '--project', str(project), 'status'], env))
            observe(host + '_updated_identity', result['data']['project']['project_id'] == summary[host + '_project_id'])
            preserved(host, 'updated')
            discovery = codex_skills(env, project, other) if host == 'codex' else claude_skills(env, project)
            save(lab / (host + '-updated-discovery.json'), discovery)
            observe(host + '_updated_discovery', len(discovery[0]['skills']) == 8 if host == 'codex' else discovery['complete'])
            # Keep an independent complete copy, then prove resource lookup after relocation.
            portable = lab / (host + ' 缓存 space 中文')
            shutil.copytree(caches[host], portable)
            doctor = json.loads(run([sys.executable, str(portable / 'runtime/evolve.py'), '--project', str(project),
                                     'maintain', '--method', 'doctor'], env))
            observe(host + '_relocated_runtime', Path(doctor['data']['package_root']).resolve() == portable)
            preserved(host, 'relocated_query')
            run([host, 'plugin', 'remove' if host == 'codex' else 'uninstall', 'evolve@evolve-local',
                 *(['--json'] if host == 'codex' else ['--scope', 'project'])], env, project)
            preserved(host, 'uninstalled')
            installed = run([host, 'plugin', 'add' if host == 'codex' else 'install', 'evolve@evolve-local',
                             *(['--json'] if host == 'codex' else ['--scope', 'project'])], env, project)
            if host == 'codex':
                config = lab / 'codex-profile/config.toml'
                config.write_text(config.read_text().replace('enabled = true', 'enabled = false'))
                runtime = Path(json.loads(installed)['installedPath']) / 'runtime/evolve.py'
            else:
                runtime = package / 'runtime/evolve.py'
            discovery = codex_skills(env, project, other) if host == 'codex' else claude_skills(env, project)
            save(lab / (host + '-reinstalled-discovery.json'), discovery)
            observe(host + '_reinstalled_discovery', len(discovery[0]['skills']) == 8 if host == 'codex' else discovery['complete'])
            preserved(host, 'reinstalled')
            facts_before = history_facts(project)
            reconnected = json.loads(run([sys.executable, str(runtime), '--project', str(project), 'init', '--request', '-'], env,
                payload={'authorization': {'source': 'controlled lifecycle fixture', 'text': 'Reconnect the same disposable project without configuration changes',
                                          'effect_kinds': ['project_records']}, 'input': {}}))
            observe(host + '_reconnected_identity', reconnected['data']['project_id'] == summary[host + '_project_id'])
            observe(host + '_reconnect_configuration_unchanged', reconnected['data']['configuration_changed'] is False)
            facts_after = history_facts(project)
            observe(host + '_reconnect_prior_facts_preserved', all(
                facts_after.get(table, {}).get(key) == value
                for table, rows in facts_before.items() for key, value in rows.items()))
            current = project_files(project)
            changed = sorted(k for k in baselines[host].keys() | current.keys() if baselines[host].get(k) != current.get(k))
            summary[host + '_explicit_reconnect_changed_paths'] = changed
            observe(host + '_reconnect_protection_is_current', reconnect_protection_current(project))
            observe(host + '_reconnect_only_records_receipt', set(changed) == {'evolve/history.db', '.evolve-local/control/guard.json', '.evolve-local/control/managed.json'})
            save(lab / (host + '-facts-before-reconnect.json'), facts_before)
            save(lab / (host + '-facts-after-reconnect.json'), facts_after)
        summary['status'] = 'automated_checks_passed_manual_review_pending'
    except Exception as error:
        summary.update(status='failed', error=str(error))
    finally:
        save(lab / 'summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary['status'].startswith('automated_checks_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
