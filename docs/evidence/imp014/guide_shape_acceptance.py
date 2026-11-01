"""One-session, no-business-write recheck of the documented reviews array shape."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--controller', required=True, type=Path)
    parser.add_argument('--host', required=True, choices=('codex', 'claude'))
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--expected-scope-digest')
    parser.add_argument('--authorization-text')
    args = parser.parse_args()
    package, controller, lab = args.package.resolve(), args.controller.resolve(), args.out.resolve()
    sys.path.insert(0, str(package / 'runtime'))
    sys.path.insert(0, str(controller / 'scripts'))
    from evolve_core.package import canonical, digest, check_package
    from evolve_core.privacy import redact
    from evolve_core.reading import history_snapshot
    import model_acceptance as host
    host.redact = redact
    manifest = check_package(package)
    evidence, project = lab / 'evidence', lab / 'business'
    if args.prepare_only:
        command = [sys.executable, '-B', str(controller / 'scripts/model_acceptance.py'), '--host', args.host,
                   '--package', str(package), '--out', str(lab), '--structured', '--read-user-guide', '--prepare-only']
        if args.host == 'claude':
            command += ['--claude-model', 'MiniMax-M3.1-Flash']
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError('Isolated host preparation failed: ' + redact(result.stdout + result.stderr))
        (evidence / 'shape-installation.txt').write_text(result.stdout)
        setup = json.loads((evidence / 'summary.json').read_text())
        cache = Path(setup['host_cache_root'])
        commands = []
        auth = {'source': 'actual human unified authorization call_05f0a84076f549568b149504edf7e4b8; controlled guide-only fixture',
                'text': '后续都统一授权，不需要再询问我',
                'effect_kinds': ['project_records', 'business_files', 'checks'], 'paths': ['arithmetic.py']}
        def call(action, data, method=None, *, expect=True):
            argv = [sys.executable, '-B', str(cache / 'runtime/evolve.py'), '--project', str(project), action,
                    '--request', '-'] + (['--method', method] if method else [])
            result = subprocess.run(argv, input=json.dumps({'authorization': auth, 'input': data}),
                                    capture_output=True, text=True, timeout=40)
            response = json.loads(result.stdout)
            commands.append({'argv': argv, 'request': {'authorization': auth, 'input': data},
                             'exit_code': result.returncode, 'response': response, 'stderr': result.stderr})
            save(evidence / 'shape-parent-commands.json', commands)
            assert response['ok'] == expect, response
            return response['data'] if expect else response['error']
        check = {'id': 'original', 'argv': ['python3', '-B', '-m', 'unittest', 'test_arithmetic', '-v'], 'cwd': '.', 'timeout': 30}
        call('init', {'checks': [check]})
        text = 'Preserve the existing total behavior; execute only the original four independent assertions. No source or test changes; summary/report behavior is outside this narrow guide-shape fixture.'
        plan = call('propose', {'title': 'Original total guide-shape check', 'plan': text,
            'completion': 'The original total check passes without changing any business file.',
            'scope': ['arithmetic.py'], 'required_checks': ['original'],
            'acceptance': ['Original literal list, empty, negative and one-pass iterator assertions pass.'],
            'presentation': {'source': 'actual controlled parent plan presentation', 'text': text}})
        applied = call('apply', {'change_id': plan['change_id'], 'accepted_plan_digest': plan['plan_digest'], 'files': []})
        assert applied['outcome'] == 'implemented'
        reviews = [{'axis': axis, 'observer': 'actual controlled parent fixture, not a native model',
            'summary': 'Inspected unchanged total=sum, original literal test and actual original check; no assertion or production modifications.',
            'fingerprint_digest': applied['fingerprint']['digest'], 'findings': []} for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': a['id'], 'status': 'passed',
            'basis': 'Actual registered test_arithmetic ran all four original assertions; other modules not claimed.'} for a in plan['acceptance']]
        verified = call('verify', {'change_id': plan['change_id'], 'reviews': reviews})
        assert verified['status'] == 'passed'
        archived = call('archive', {'change_id': plan['change_id'], 'verification_id': verified['verification_id']})
        assert archived['outcome'] == 'archived'
        rejected = call('verify', {'change_id': plan['change_id'], 'reviews': {r['axis']: r for r in reviews}}, expect=False)
        assert rejected['code'] == 'REVIEW_REQUIRED'
        prepared = {'setup': setup, 'change_id': plan['change_id'], 'change_code': plan['change_code'],
                    'negative_object_code': rejected['code'], 'parent_plan': text}
        save(evidence / 'shape-prepared.json', prepared)
    prepared = json.loads((evidence / 'shape-prepared.json').read_text())
    setup = prepared['setup']; cache = Path(setup['host_cache_root'])
    prompt = ('先读取本次实际插件根的README.md、docs/installation.md、docs/usage.md相关步骤及shared/protocol.md中verify/run。'
        '本次是reviews容器说明的定向复验：控制侧按指南已完成隔离安装和首次接入，并用真实CLI将“' + prepared['change_code'] + '”'
        '的原total四项独立断言检查、两维夹具审查和封存准备好；这些控制侧观察不能冒充你的自测或审查。'
        '控制侧的reviews对象负例被REVIEW_REQUIRED拒绝并安全封存为blocked run，不是待恢复运行。'
        '本轮仅以你实际读取、原original检查和两维实际自审，按新指南的reviews数组追加该已封存工作项的当前verify；'
        '保留历史、Change/Task终态和全部六份业务／测试字节，不改源码、测试、配置或知识，不新增/重开任务，不登记经验。'
        '只覆盖原total，summary/report和其余测试不在本轮通过范围。说明当前检查结果和原历史的区别。'
        '完整安装由控制侧按指南准备，不重新安装或改宿主；遇权限、额度或传输问题立即停止，不换模型/重试。')
    scope = {'slice': 'IMP-014-targeted-reviews-container-guide', 'host': args.host,
        'package_digest': manifest['content_digest'], 'package_version': manifest['package_version'],
        'model': 'model/list isDefault' if args.host == 'codex' else 'MiniMax-M3.1-Flash',
        'maximum_sessions': 1, 'business_write_paths': [], 'readonly_business_files': sorted(__import__('model_complex_checks').FIRST_FILES),
        'parent_plan': prepared['parent_plan'], 'target': prepared['change_id'], 'prompt': prompt,
        'guide_paths': ['README.md', 'docs/installation.md', 'docs/usage.md', 'shared/protocol.md'],
        'controller_sha256': digest(Path(__file__).read_bytes()),
        'transport_sha256': digest((controller / 'scripts/model_acceptance.py').read_bytes())}
    scope['scope_digest'] = digest(canonical(scope))
    if args.prepare_only:
        save(evidence / 'shape-scope.json', scope)
        print(json.dumps({'prepared': True, 'scope_digest': scope['scope_digest'], 'model_requests_sent': False}));return
    if args.expected_scope_digest != scope['scope_digest'] or args.authorization_text != '后续都统一授权，不需要再询问我':
        raise ValueError('Exact prepared scope and actual uniform human authorization required')
    assert json.loads((evidence / 'shape-scope.json').read_text()) == scope
    from model_session_checks import SessionChecks
    boundary = SessionChecks.__new__(SessionChecks)
    boundary.project, boundary.project_installation = project, True
    business = boundary.files()
    files = {name: ((project / name).read_bytes(), (project / name).stat().st_mtime_ns) for name in scope['readonly_business_files']}
    settings = {str(p.relative_to(project)): p.read_bytes() for folder in ('.claude', '.codex') for p in (project / folder).rglob('*') if p.is_file()}
    with history_snapshot(project) as (c, _):
        before = {t: {r['id']: dict(r) for r in c.execute('SELECT * FROM ' + t)} for t in ('changes','tasks','verifications','phase_runs')}
    outcome = {'host': args.host, 'package_digest': manifest['content_digest'], 'scope_digest': scope['scope_digest'],
               'authorization': args.authorization_text, 'model_requests_sent': True, 'automated_checks_passed': False, 'review_status': 'pending'}
    save(evidence / 'shape-summary.json', outcome)
    client = None
    try:
        if args.host == 'codex':
            client = host.CodexSession(project, evidence)
            outcome['model_result'] = client.run(prompt, cache)
        else:
            argv = ['claude','--print','--verbose','--output-format','stream-json','--no-session-persistence',
                '--setting-sources','project','--permission-mode','acceptEdits','--strict-mcp-config','--mcp-config',str(evidence/'empty-mcp.json'),
                '--disallowedTools','Agent,Task','--allowedTools','Read,Write,Edit,Glob,Grep,Skill,Bash(python3:*),Bash(ls:*),Bash(cat:*),Bash(rg:*)',
                '--model','MiniMax-M3.1-Flash']
            outcome['model_result'] = host.claude_case(argv, host.claude_input(prompt,project,cache),
                env={**os.environ,'CLAUDE_CONFIG_DIR':str(project/'.agents/evolve-acceptance/profile'),'CLAUDE_CODE_DISABLE_AUTO_MEMORY':'1'},
                project=project,log=evidence/'shape-model.json')
        assert files == {name: ((project/name).read_bytes(), (project/name).stat().st_mtime_ns) for name in files}
        assert business == boundary.files()
        assert settings == {str(p.relative_to(project)):p.read_bytes() for folder in ('.claude','.codex') for p in (project/folder).rglob('*') if p.is_file()}
        for base in (cache,Path(setup['registered_installation_root'])):assert check_package(base)['content_digest']==manifest['content_digest']
        with history_snapshot(project) as (c,_):
            after={t:{r['id']:dict(r) for r in c.execute('SELECT * FROM '+t)} for t in before}
            assert c.execute("SELECT COUNT(*) FROM phase_runs WHERE status='started'").fetchone()[0]==0
            assert c.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0]==0
        assert after['changes']==before['changes'] and after['tasks']==before['tasks']
        for table in ('verifications','phase_runs'):
            assert all(after[table].get(k)==v for k,v in before[table].items())
        fresh=[v for k,v in after['verifications'].items() if k not in before['verifications']]
        assert fresh and all(v['status']=='passed' for v in fresh)
        assert all(v['action']=='verify' for k,v in after['phase_runs'].items() if k not in before['phase_runs'])
        outcome.update(automated_checks_passed=True,new_verifications=[{'id':v['id'],'status':v['status']} for v in fresh],
                       six_business_files_and_mtimes_preserved=True,old_rows_preserved=True)
    except Exception as error:
        outcome['error']=redact(str(error))
    finally:
        if client:client.close()
        save(evidence/'shape-summary.json',outcome)
    print(json.dumps(outcome,ensure_ascii=False))
    if not outcome['automated_checks_passed']:raise SystemExit(1)

if __name__=='__main__':main()
