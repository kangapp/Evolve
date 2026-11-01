#!/usr/bin/env python3
"""Prove explicit 14/15→16 upgrade using the actual preserved old complete runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def run(old, new, output):
    old, new, output = (Path(p).resolve() for p in (old, new, output))
    output.mkdir(parents=True, exist_ok=False)
    project = output / 'project'
    project.mkdir()
    commands = []
    auth = {'source': 'actual-uniform-human-authorization-controlled-compatibility-plan',
            'text': 'In this temporary project only, compare actual preserved protocol14 and current15, explicitly upgrade the archive; preserve all current bytes on incompatible requests.',
            'effect_kinds': ['project_records']}
    def call(package, action, method=None, request=None, *, ok=True):
        argv = [sys.executable, '-B', str(package / 'runtime/evolve.py'), '--project', str(project), action]
        if method:
            argv += ['--method', method]
        if request:
            argv += ['--request', '-']
        result = subprocess.run(argv, input=json.dumps(request) if request else None,
                                capture_output=True, text=True, timeout=40)
        response = json.loads(result.stdout)
        commands.append({'argv': argv, 'request': request, 'exit_code': result.returncode,
                         'response': response, 'stderr': result.stderr})
        (output / 'commands.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2))
        assert response['ok'] == ok, response
        return response['data'] if ok else response['error']
    def inventory():
        return {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in project.rglob('*') if p.is_file()}
    connected = call(old, 'init', 'connect', {'authorization': auth, 'input': {}})
    before = inventory()
    refused = call(new, 'init', 'connect', {'authorization': auth, 'input': {}}, ok=False)
    assert refused['code'] == 'SCHEMA_VERSION' and inventory() == before
    plan = call(new, 'maintain', 'upgrade', {'authorization': auth, 'input': {'stage': 'plan'}})
    identity = {'project_id': connected['project_id'], 'expected_workspace_epoch': connected['workspace_epoch']}
    request = {**identity, 'request_id': 'explicit-old-to-new-upgrade', 'authorization': auth,
               'input': {'stage': 'apply', 'plan_id': plan['plan']['plan_id'], 'plan_digest': plan['plan_digest']}}
    upgraded = call(new, 'maintain', 'upgrade', request)
    assert upgraded['outcome'] == 'upgraded' and upgraded['workspace_epoch'] != connected['workspace_epoch']
    after = inventory()
    for action, method in (('status', None), ('init', 'connect')):
        refused = call(old, action, method, {'authorization': auth, 'input': {}} if action == 'init' else None, ok=False)
        assert refused['code'] == 'SCHEMA_VERSION' and inventory() == after
    refused = call(new, 'maintain', 'backup', {**identity, 'request_id': 'old-epoch-cannot-replay',
                                             'authorization': auth, 'input': {}}, ok=False)
    assert refused['code'] == 'WORKSPACE_EPOCH' and inventory() == after
    state = call(new, 'status')['project']
    assert state['state'] == 'connected' and state['workspace_epoch'] == upgraded['workspace_epoch']
    summary = {'passed': True, 'old_package': str(old), 'new_package': str(new), 'commands': len(commands),
               'actual_old_protocol': json.loads((old / 'evolve-package.json').read_text())['protocol_version'],
               'actual_new_protocol': json.loads((new / 'evolve-package.json').read_text())['protocol_version'], 'explicit_upgrade': upgraded,
               'ordinary_init_no_migration': True, 'incompatible_requests_preserve_all_bytes': True,
               'model_requests_sent': False}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-package', required=True, type=Path)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.old_package, args.package, args.out), ensure_ascii=False, indent=2))
