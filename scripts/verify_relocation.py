#!/usr/bin/env python3
"""Exercise a complete relocated runtime; host discovery and model calls are separate."""
import argparse
import hashlib
import json
import locale
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from workflow_smoke import run_workflow
from continuation_smoke import run_continuation


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True, help='Complete existing distribution; never changed')
    parser.add_argument('--out', type=Path, required=True, help='New disposable lab directory; must not exist')
    parser.add_argument('--require-windows', action='store_true', help='Reject other platforms before creating a lab')
    args = parser.parse_args()
    if args.require_windows and (os.name != 'nt' or platform.system() != 'Windows'):
        parser.error('Native Windows is required; this execution cannot close the Windows gate')
    if locale.getpreferredencoding(False).lower().replace('-', '') != 'utf8':
        parser.error('Run Python with -X utf8 so fixture helpers and CLI logs use UTF-8')
    package, lab = args.package.resolve(), args.out.resolve()
    if not (package / 'evolve-package.json').is_file():
        parser.error('Supply a complete package containing evolve-package.json')
    if lab.is_relative_to(package) or package.is_relative_to(lab):
        parser.error('The disposable lab and supplied installation must be separate')
    if lab.exists() or lab.is_symlink():
        parser.error('Output already exists; refusing to modify it')
    # -X utf8 selects this controller's codec; child CLI/check processes inherit
    # the equivalent setting without changing any user or host configuration.
    os.environ['PYTHONUTF8'] = '1'
    original = snapshot(package)
    lab.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'in_progress', 'platform': {'system': platform.system(), 'release': platform.release(),
        'os_name': os.name, 'python': sys.version.split()[0], 'encoding': locale.getpreferredencoding(False), 'child_python_utf8': True},
        'native_windows_observed': os.name == 'nt' and platform.system() == 'Windows',
        'model_requests_sent': False, 'host_discovery': 'not_run', 'checks': {},
        'limitations': ['Runtime CLI fixtures only; no native host install or Skill discovery in this runner',
                        'Review inputs are controlled observations, not independent model judgments',
                        'Only the observed platform is tested; this result alone does not complete V-137 or M1']}
    logs = []

    def observe(name, value):
        summary['checks'][name] = bool(value)
        if not value:
            raise AssertionError(name)

    def query(runtime, action, method=None):
        argv = [sys.executable, '-B', str(runtime), '--project', str(project), action]
        if method:
            argv += ['--method', method]
        process = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding='utf-8', timeout=60)
        logs.append({'argv': argv, 'cwd': str(cwd), 'exit_code': process.returncode,
                     'stdout': process.stdout, 'stderr': process.stderr})
        save(lab / 'commands.json', logs)
        if process.returncode:
            raise AssertionError('Runtime query failed; inspect commands.json')
        result = json.loads(process.stdout)
        if not result['ok']:
            raise AssertionError('Runtime query reported failure')
        return result['data']

    try:
        download = lab / '下载 副本'
        installation = lab / '安装 整包'
        relocated = lab / '移动 整包'
        project, cwd = lab / '业务 项目', lab / '独立 cwd'
        project.mkdir()
        cwd.mkdir()
        shutil.copytree(package, download)
        shutil.copytree(download, installation)
        shutil.rmtree(download)
        observe('download_removed', not download.exists())
        doctor = query(installation / 'runtime/evolve.py', 'maintain', 'doctor')
        summary['content_digest'] = doctor['content_digest']
        summary['package_version'] = doctor['package_version']
        observe('installed_root_used', Path(doctor['package_root']).resolve() == installation)
        observe('project_initially_not_connected', doctor['project']['state'] == 'not_connected')
        baseline = run_workflow(installation / 'runtime/evolve.py', project, lab / 'workflow-evidence', diagnostic=True)
        summary['workflow'] = baseline
        observe('actual_repair_and_closure', baseline['passed'])
        prior = snapshot(project)
        installation.rename(relocated)
        observe('old_installation_removed', not installation.exists())
        doctor = query(relocated / 'runtime/evolve.py', 'maintain', 'doctor')
        observe('relocated_root_used', Path(doctor['package_root']).resolve() == relocated)
        observe('relocated_package_unchanged', doctor['content_digest'] == summary['content_digest'])
        restored = query(relocated / 'runtime/evolve.py', 'resume')['context']
        observe('original_project_identity', restored['project']['project_id'] == baseline['project_id'])
        observe('relocation_queries_are_pure', snapshot(project) == prior)
        summary['continuation'] = run_continuation(relocated / 'runtime/evolve.py', project, lab / 'continuation-evidence', baseline)
        observe('actual_pause_continuation_and_learning', summary['continuation']['passed'])
        observe('supplied_package_unchanged', snapshot(package) == original)
        summary['status'] = 'passed_for_observed_runtime_platform'
    except Exception as error:
        summary['status'] = 'failed'
        summary['error'] = str(error)
    save(lab / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['status'] == 'passed_for_observed_runtime_platform' else 1


if __name__ == '__main__':
    raise SystemExit(main())
