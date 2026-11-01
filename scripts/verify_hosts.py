#!/usr/bin/env python3
"""Install an independent build into isolated host profiles; never calls a model."""
import argparse
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NAMES = sorted('evolve:evolve-' + name for name in
               ('workflow', 'init', 'propose', 'apply', 'verify', 'archive', 'learn', 'maintain'))


def codex_skills(env, project, other):
    process = subprocess.Popen(['codex', 'app-server', '--stdio'], env=env, cwd=project,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)

    def rpc(identifier, method, params):
        process.stdin.write(json.dumps({'id': identifier, 'method': method, 'params': params}) + '\n')
        process.stdin.flush()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if selector.select(1):
                line = process.stdout.readline()
                if not line:
                    raise RuntimeError('Codex app-server exited during ' + method)
                result = json.loads(line)
                if result.get('id') == identifier:
                    if 'error' in result:
                        raise RuntimeError(result['error'])
                    return result['result']
        raise TimeoutError(method)

    try:
        rpc(1, 'initialize', {'clientInfo': {'name': 'evolve-acceptance', 'version': '1'},
                              'capabilities': {'experimentalApi': True}})
        process.stdin.write('{"method":"initialized"}\n')
        process.stdin.flush()
        result = rpc(2, 'skills/list', {'cwds': [str(project), str(other)], 'forceReload': True})
        return [{'cwd': row['cwd'], 'skills': [s for s in row['skills']
                 if s.get('pluginId') == 'evolve@evolve-local'], 'errors': row.get('errors', [])}
                for row in result['data']]
    finally:
        process.terminate()
        try:
            process.wait(3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        selector.close()
        process.stdin.close()
        process.stdout.close()


def claude_skills(env, project):
    # /skills is a local interactive command. No user prompt or model request is sent.
    import fcntl
    import pty
    import select
    import struct
    import termios

    config = Path(env['CLAUDE_CONFIG_DIR']) / '.claude.json'
    settings = json.loads(config.read_text()) if config.exists() else {}
    settings.update(hasCompletedOnboarding=True, theme='dark')
    config.write_text(json.dumps(settings))
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 60, 160, 0, 0))
    process = subprocess.Popen(['claude', '--setting-sources', 'project', '--permission-mode', 'plan'],
                               cwd=project, env={**env, 'TERM': 'xterm-256color'},
                               stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    output = b''
    start = time.monotonic()
    trusted = sent = False
    names = []
    try:
        while time.monotonic() < start + 30:
            if select.select([master], [], [], .2)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
            clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', output.decode(errors='replace'))
            if not trusted and 'trustthisfolder' in re.sub(r'\s+', '', clean).lower():
                os.write(master, b'\r')  # This probe created this isolated project.
                trusted = True
            if not sent and time.monotonic() > start + 7:
                os.write(master, b'/skills\r')
                sent = True
            names = sorted(set(re.findall(r'evolve:evolve-[a-z]+', clean)))
            if names == NAMES:
                break
        return {'observed_skill_names': names, 'model_request_sent': False,
                'local_command': '/skills', 'complete': names == NAMES, 'local_ui_excerpt': clean[-6000:]}
    finally:
        process.terminate()
        try:
            process.wait(3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        os.close(master)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New directory for isolated profiles and evidence')
    parser.add_argument('--workflow', action='store_true', help='Also run a disposable small-change workflow through each installed cache')
    parser.add_argument('--diagnostic', action='store_true', help='Include answer-only and recorded investigation with original-criterion repair')
    parser.add_argument('--continuation', action='store_true', help='Also exercise normal pause, fresh CLI restoration and actual project experience consumption')
    args = parser.parse_args()
    if args.continuation:
        args.diagnostic = True
    if args.diagnostic:
        args.workflow = True
    lab = args.out.resolve()
    lab.mkdir(parents=True, exist_ok=False)
    project, other = lab / 'project', lab / 'other-project'
    for path in (project, other, lab / 'codex-profile', lab / 'claude-profile'):
        path.mkdir()
    logs = []

    def run(argv, env=None, cwd=project):
        process = subprocess.run(argv, env=env, cwd=cwd, capture_output=True, text=True, timeout=45)
        logs.append({'argv': argv, 'cwd': str(cwd), 'exit_code': process.returncode,
                     'stdout': process.stdout, 'stderr': process.stderr})
        (lab / 'commands.json').write_text(json.dumps(logs, ensure_ascii=False, indent=2))
        if process.returncode:
            raise RuntimeError('Host command failed: ' + ' '.join(argv))
        return process.stdout

    download = lab / 'download'
    run([sys.executable, str(ROOT / 'scripts/build_package.py'), '--out', str(download)])
    package = lab / 'installed-source'
    shutil.copytree(download, package)
    manifest = json.loads((package / 'evolve-package.json').read_text())
    codex_env = {**os.environ, 'CODEX_HOME': str(lab / 'codex-profile')}
    claude_env = {**os.environ, 'CLAUDE_CONFIG_DIR': str(lab / 'claude-profile')}
    summary = {'package_version': manifest['package_version'], 'content_digest': manifest['content_digest'],
               'registered_installation_root': str(package), 'model_requests_sent': False, 'checks': {},
               'limitations': ['Native Windows execution not tested',
                              'Claude local-directory marketplace loads the registered installation root in place; its independent cache is checked separately']}
    try:
        summary['codex_version'] = run(['codex', '--version']).strip()
        summary['claude_version'] = run(['claude', '--version']).strip()
        run(['codex', 'plugin', 'marketplace', 'add', str(package), '--json'], codex_env)
        installed = json.loads(run(['codex', 'plugin', 'add', 'evolve@evolve-local', '--json'], codex_env))
        codex_cache = Path(installed['installedPath'])
        config = lab / 'codex-profile/config.toml'
        original = config.read_text()
        if original.count('enabled = true') != 1:
            raise RuntimeError('Unexpected isolated Codex installation configuration')
        config.write_text(original.replace('enabled = true', 'enabled = false') +
                          f'\n[projects.{json.dumps(str(project))}]\ntrust_level="trusted"\n')
        (project / '.codex').mkdir()
        (project / '.codex/config.toml').write_text('[plugins."evolve@evolve-local"]\nenabled=true\n')
        scopes = codex_skills(codex_env, project, other)
        (lab / 'codex-scopes.json').write_text(json.dumps(scopes, ensure_ascii=False, indent=2))
        summary['checks']['codex_discovery'] = sorted(s['name'] for s in scopes[0]['skills']) == NAMES
        summary['checks']['codex_project_scope'] = not scopes[1]['skills'] and all(not s['errors'] for s in scopes)
        run(['claude', 'plugin', 'validate', str(package)], claude_env)
        run(['claude', 'plugin', 'validate', str(package / '.claude-plugin/plugin.json')], claude_env)
        run(['claude', 'plugin', 'marketplace', 'add', str(package), '--scope', 'project'], claude_env)
        run(['claude', 'plugin', 'install', 'evolve@evolve-local', '--scope', 'project'], claude_env)
        installations = json.loads(run(['claude', 'plugin', 'list', '--json'], claude_env))
        installation = next(p for p in installations if p['id'] == 'evolve@evolve-local')
        claude_cache = Path(installation['installPath'])
        outside = json.loads(run(['claude', 'plugin', 'list', '--json'], claude_env, cwd=other))
        summary['checks']['claude_project_scope'] = installation['scope'] == 'project' and not any(
            p['id'] == 'evolve@evolve-local' and p.get('enabled') for p in outside)
        summary['claude_ui'] = claude_skills(claude_env, project)
        summary['checks']['claude_discovery'] = summary['claude_ui']['complete']
        workspaces = {}
        if args.workflow:
            for host in ('codex', 'claude'):
                business = lab / (host + '-business')
                business.mkdir()
                workspaces[host] = business
                if host == 'codex':
                    (business / '.codex').mkdir()
                    (business / '.codex/config.toml').write_text('[plugins."evolve@evolve-local"]\nenabled=true\n')
                    with config.open('a') as stream:
                        stream.write(f'\n[projects.{json.dumps(str(business))}]\ntrust_level="trusted"\n')
                    observed = codex_skills(codex_env, business, other)
                    (lab / 'codex-business-scopes.json').write_text(json.dumps(observed, ensure_ascii=False, indent=2))
                    summary['checks']['codex_business_project_discovery'] = sorted(s['name'] for s in observed[0]['skills']) == NAMES
                else:
                    run(['claude', 'plugin', 'marketplace', 'add', str(package), '--scope', 'project'], claude_env, cwd=business)
                    run(['claude', 'plugin', 'install', 'evolve@evolve-local', '--scope', 'project'], claude_env, cwd=business)
                    business_ui = claude_skills(claude_env, business)
                    summary['claude_business_ui'] = business_ui
                    summary['checks']['claude_business_project_discovery'] = business_ui['complete']
        shutil.rmtree(download)
        summary['checks']['original_download_removed'] = not download.exists()
        for host, cache in [('codex', codex_cache), ('claude', claude_cache)]:
            result = json.loads(run([sys.executable, str(cache / 'runtime/evolve.py'),
                                    '--project', str(project), 'maintain', '--method', 'doctor']))
            summary['checks'][host + '_cached_resources'] = (
                result['data']['content_digest'] == manifest['content_digest']
                and result['data']['project']['state'] == 'not_connected')
        summary['checks']['project_not_initialized'] = not (project / 'evolve').exists()
        registered = json.loads(run([sys.executable, str(package / 'runtime/evolve.py'),
                                    '--project', str(project), 'maintain', '--method', 'doctor']))
        summary['checks']['claude_registered_root_resources'] = (registered['data']['content_digest'] == manifest['content_digest']
                                                               and registered['data']['package_root'] == str(package))
        if args.workflow:
            from workflow_smoke import run_workflow
            summary['workflow'] = {}
            for host, cache in [('codex', codex_cache), ('claude', claude_cache)]:
                business = workspaces[host]
                summary['workflow'][host] = run_workflow(cache / 'runtime/evolve.py', business, lab / (host + '-workflow-evidence'), diagnostic=args.diagnostic)
                summary['checks'][host + '_cached_workflow'] = summary['workflow'][host]['passed']
                if args.continuation:
                    from continuation_smoke import run_continuation
                    summary.setdefault('continuation', {})[host] = run_continuation(cache / 'runtime/evolve.py', business,
                        lab / (host + '-continuation-evidence'), summary['workflow'][host])
                    summary['checks'][host + '_continuation_and_learning'] = summary['continuation'][host]['passed']
            summary['limitations'].append('Workflows use the actual installed runtime caches with controlled review inputs; no natural-language model orchestration was exercised')
        summary['passed'] = all(summary['checks'].values())
    except Exception as error:
        summary['passed'] = False
        summary['error'] = str(error)
    (lab / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
