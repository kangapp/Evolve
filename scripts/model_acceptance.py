#!/usr/bin/env python3
"""Prepare or run explicitly authorized, disposable host-model acceptance."""
import argparse
import ast
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True

PROMPTS = {
    'inspect': '使用 Evolve 看一下总计为什么不对，说明相关代码、实际症状和修复建议，暂不改业务代码。',
    'repair': '使用 Evolve 接入此项目。检查入口为 python3 -B -m unittest discover -v。先呈现具体短方案，再在 arithmetic.py 与 test_arithmetic.py 范围内修复总计错误，保留现有独立断言，完成相关检查、规格与规范审查及封存。授权在该范围内修正验收发现；不批准正式项目知识。请忠实记录实际用户来源和本次授权，不预填审查结论。',
    'verify': '使用 Evolve 仅验收这个工作项的当前现场；不要修复或修改测试。说明历史结果和当前结论的区别，以及必要的后续方案。原工作项若已封存，不得越过终态修改历史或强行重开。',
}
LIMITS = ('本次插件验收的操作边界：只操作当前临时业务项目及其 Evolve 记录，读取本次安装缓存内插件资料。'
          '不操作本插件源码工程、其他业务项目、个人配置、凭证或外部应用，不启动嵌套代理，不提交、发布或部署。'
          '遇到真实权限、认证或能力阻碍如实报告；不绕过限制。实际修改走 Evolve 的授权和工具协议。')

HEADLESS_BRIDGE = '''import json,subprocess,sys,uuid
from pathlib import Path
runtime=__RUNTIME__
project=__PROJECT__
folder=Path(project)/'.evolve-local/control/requests'
result=subprocess.run([sys.executable,'-B',runtime,'--project',project,*sys.argv[1:]],capture_output=True,text=True)
try:
    response=json.loads(result.stdout)
except ValueError:
    response={'ok':False,'error':{'code':'NON_JSON_RESULT','message':result.stdout[:400]}}
path=folder/('cli-receipt-'+str(uuid.uuid4())+'.json')
path.write_text(json.dumps({'exit_code':result.returncode,'response':response,'stdout':result.stdout,'stderr':result.stderr},ensure_ascii=False,indent=2))
data=response.get('data',{})
brief={key:value for key,value in data.items() if value is None or isinstance(value,(bool,int,float)) or isinstance(value,str) and len(value)<=180}
print(json.dumps({'exit_code':result.returncode,'ok':response.get('ok'),'receipt':str(path),'data':brief,'data_keys':list(data),'error':response.get('error'),'stderr':result.stderr[:500]},ensure_ascii=False))
sys.exit(result.returncode)
'''


def save(path, value):
    path.write_text(redact(json.dumps(value, ensure_ascii=False, indent=2)) + '\n')


def prepare_headless_bridge(project, cache, evidence):
    bridge = project / '.agents/evolve-acceptance/evolve_bridge.py'
    bridge.parent.mkdir(parents=True, exist_ok=True)
    staging = project / '.evolve-local/control/requests'
    staging.mkdir(parents=True, exist_ok=True)
    (staging / 'headless-staging.json').write_text('{"purpose":"controlled host JSON request and receipt staging"}')
    bridge.write_text(HEADLESS_BRIDGE.replace('__RUNTIME__', repr(str(cache / 'runtime/evolve.py'))).replace('__PROJECT__', repr(str(project))))
    bridge_digest = digest(bridge.read_bytes())
    save(evidence / 'headless-bridge.json', {'path': str(bridge), 'sha256': bridge_digest,
         'template_sha256': digest(HEADLESS_BRIDGE.encode()), 'permissions_changed': False})
    return bridge, bridge_digest


def shell(argv, *, env, cwd, log):
    result = subprocess.run(argv, env=env, cwd=cwd, capture_output=True, text=True, timeout=60)
    save(log, {'argv': argv, 'cwd': str(cwd), 'exit_code': result.returncode,
               'stdout': result.stdout, 'stderr': result.stderr})
    if result.returncode:
        raise RuntimeError('Setup command failed; see ' + str(log))
    return json.loads(result.stdout) if '--json' in argv else result.stdout


def claude_barrier(event):
    if event.get('permission_denials'):
        return {'kind': 'permission', 'basis': 'Native result reported permission_denials'}
    if (event.get('type') == 'system' and event.get('subtype') == 'api_retry'
            and event.get('error_status') == 429):
        return {'kind': 'native_error', 'basis': event}
    if event.get('type') == 'result' and (event.get('is_error') or event.get('subtype') != 'success'):
        return {'kind': 'native_error', 'basis': event.get('result', 'Native model result failed')}
    if event.get('type') == 'assistant' and event.get('error'):
        return {'kind': 'native_error', 'basis': event['error']}
    if event.get('type') == 'user':
        for item in event.get('message', {}).get('content', []):
            if isinstance(item, dict) and item.get('type') == 'tool_result' and item.get('is_error'):
                content = item.get('content', '')
                value = content.casefold() if isinstance(content, str) else json.dumps(content).casefold()
                if any(marker in value for marker in ('was blocked. for security, claude code',
                        'require approval', 'requires approval', 'permission denied', 'permission to use')):
                    return {'kind': 'permission', 'basis': content}
    return None


def claude_input(prompt, project, cache):
    return ('本次已知业务根：' + str(project) + '；插件根：' + str(cache) + '。\n'
            '本受控宿主明确允许的 Bash 命令只有 python3、ls、cat、rg；其他必要读取使用 Read／Glob／Grep。'
            '现场指纹与文件摘要采用 Evolve status／resume 的实际返回，不另行调用 shasum、sha256sum、wc、git 等辅助命令，'
            '也不用 Python 或其他工具重做被拒的摘要动作。\n'
            '宿主命令约定：插件资料使用 Read／Glob／Grep 读取，不对插件根执行 Bash ls 或 cd。'
            'Bash 每次只发一条直接命令；不使用 shell 变量（包括 $PWD）、循环、here-doc、重定向、管道或命令连接符。'
            'CLI 的 --project 使用上面业务根的绝对字面路径。JSON 请求和必要辅助脚本用 Write 保存在业务根下 '
            '.evolve-local/control/requests/ 的本次唯一文件；可用单条 python3 -B <脚本路径> 处理请求，'
            '业务和正式文件仍只经 Evolve 所属动作修改。检查也分别以单条 python3 -B -m unittest 命令执行。'
            '这些格式沿用已有宿主权限；任何权限拒绝、认证或额度错误均立即停止，不尝试换形式重发被拒动作。\n'
            + prompt + '\n' + LIMITS)


def claude_case(argv, prompt, *, env, project, log, timeout=600):
    process = subprocess.Popen(argv, env=env, cwd=project, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    selector = selectors.DefaultSelector()
    output = {'stdout': bytearray(), 'stderr': bytearray()}
    pending, stopped, timed_out = b'', None, False
    deadline = time.monotonic() + timeout
    try:
        process.stdin.write(prompt.encode()); process.stdin.close(); process.stdin = None
        for name in output:
            selector.register(getattr(process, name), selectors.EVENT_READ, name)
        while selector.get_map() and not stopped:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in selector.select(min(remaining, .2)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                output[key.data].extend(chunk)
                if key.data == 'stdout':
                    pending += chunk
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(event, dict):
                            stopped = claude_barrier(event)
                            if stopped:
                                break
                if stopped:
                    break
        if not stopped and pending.strip():
            try:
                event = json.loads(pending)
            except ValueError:
                event = None
            if isinstance(event, dict):
                stopped = claude_barrier(event)
        if not stopped and not timed_out:
            try:
                process.wait(timeout=max(.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        selector.close()
        if stopped or timed_out or process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        tail = process.communicate()
        for name, data in zip(output, tail):
            output[name].extend(data or b'')
        saved = {'argv': argv, 'exit_code': None if timed_out else process.returncode,
                 **{name: data.decode('utf-8', errors='replace') for name, data in output.items()}}
        if timed_out:
            saved.update({'timed_out': True, 'timeout_seconds': timeout})
        if stopped:
            saved['transport_stop'] = stopped
        save(log, saved)
    if timed_out:
        raise subprocess.TimeoutExpired(argv, timeout, output=saved['stdout'], stderr=saved['stderr'])
    if stopped:
        raise RuntimeError('Claude ' + stopped['kind'] + ' boundary stopped the native batch; inspect its saved result')
    if process.returncode:
        raise RuntimeError('Claude run failed; inspect its saved result')
    return {'exit_code': process.returncode}


class CodexSession:
    def __init__(self, project, evidence):
        self.project, self.evidence = project, evidence
        settings_path = Path.home() / '.codex/config.toml'
        settings = tomllib.loads(settings_path.read_text()) if settings_path.is_file() else {}
        overrides = []
        for key in ('mcp_servers', 'plugins'):
            value = '{' + ','.join(json.dumps(name) + '={enabled=false}' for name in settings.get(key, {})) + '}'
            overrides += ['-c', key + '=' + value]
        self.process = subprocess.Popen(['codex', 'app-server', '--stdio', *overrides,
            '-c', 'features.multi_agent=false', '-c', 'features.apps=false', '-c', 'features.memories=false'],
            cwd=project, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer, self.messages, self.counter = b'', [], 0
        self.log = (evidence / 'model-events.jsonl').open('w')
        try:
            self.rpc('initialize', {'clientInfo': {'name': 'evolve-model-acceptance', 'version': '1'},
                                    'capabilities': {'experimentalApi': True}})
            self.send({'method': 'initialized'})
            models = self.rpc('model/list', {})['data']
            defaults = [m for m in models if m.get('isDefault') and not m.get('hidden')]
            if len(defaults) != 1:
                raise RuntimeError('Account did not identify one default model; do not guess a replacement')
            self.model = defaults[0]['model']
            save(evidence / 'account-default-model.json', {'configured_model': settings.get('model'),
                 'account_default_model': self.model, 'selection_basis': 'model/list isDefault, not an arbitrary model override',
                 'credential_copy': False, 'personal_configuration_changed': False})
        except BaseException:
            self.close()
            raise

    def send(self, value):
        self.process.stdin.write((json.dumps(value) + '\n').encode())
        self.process.stdin.flush()

    def wait(self, predicate):
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            for index, message in enumerate(self.messages):
                if predicate(message):
                    return self.messages.pop(index)
            if self.process.poll() is not None:
                raise RuntimeError('Codex app-server exited: ' + str(self.process.returncode))
            if not self.selector.select(1):
                continue
            self.buffer += os.read(self.process.stdout.fileno(), 65536)
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                message = json.loads(line)
                self.log.write(redact(json.dumps(message, ensure_ascii=False)) + '\n')
                self.log.flush()
                if 'id' in message and 'method' in message:
                    # Unexpected approval and user-input requests are not silently granted.
                    self.send({'id': message['id'], 'error': {'code': -32601, 'message': 'This acceptance runner cannot grant additional permissions'}})
                    raise RuntimeError('Codex permission or user-input boundary stopped the native batch: ' + message['method'])
                self.messages.append(message)
        raise TimeoutError('Codex observation deadline; inspect the existing process before any restart')

    def rpc(self, method, params):
        self.counter += 1
        identifier = self.counter
        self.send({'id': identifier, 'method': method, 'params': params})
        response = self.wait(lambda m: m.get('id') == identifier and 'method' not in m)
        if 'error' in response:
            raise RuntimeError('Codex RPC failed: ' + redact(json.dumps(response['error'])))
        return response['result']

    def run(self, prompt, cache):
        thread = self.rpc('thread/start', {'cwd': str(self.project), 'ephemeral': True,
                          'approvalPolicy': 'never', 'sandbox': 'workspace-write', 'model': self.model})
        thread_id = thread['thread']['id']
        result = self.rpc('turn/start', {'threadId': thread_id, 'input': [
            {'type': 'text', 'text': '$evolve-workflow\n本次宿主选择的 Skill 实际路径：' + str(cache / 'skills/evolve-workflow/SKILL.md') + '\n' + prompt + '\n' + LIMITS},
            {'type': 'skill', 'name': 'evolve-workflow', 'path': str(cache / 'skills/evolve-workflow/SKILL.md')}]})
        turn_id = result['turn']['id']
        completed = self.wait(lambda m: m.get('method') == 'turn/completed'
                              and m['params'].get('threadId') == thread_id and m['params']['turn']['id'] == turn_id)
        turn = completed['params']['turn']
        if turn['status'] != 'completed':
            raise RuntimeError('Codex turn did not complete: ' + redact(json.dumps(turn)))
        return {'thread_id': thread_id, 'turn_id': turn_id, 'status': turn['status'], 'model': thread.get('model'),
                'skill_loading': 'explicit documented skill input from the actual isolated installation cache'}

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.selector.close()
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()



def original_fixture():
    return {'arithmetic.py': 'def total(values):\n    return len(values)\n',
            'test_arithmetic.py': ('import unittest\nfrom arithmetic import total\nclass Arithmetic(unittest.TestCase):\n'
                '    def test_independent_examples(self):\n'
                '        self.assertEqual(total([8,3]),11)\n'
                '        self.assertEqual(total([]),0)\n'
                '        self.assertEqual(total([-4,3]),-1)\n')}


def installation_roots(lab, *, knowledge=False):
    project, evidence = lab / 'business', lab / 'evidence'
    base = project / '.agents/evolve-acceptance' if knowledge else lab
    profile = base / 'profile' if knowledge else lab / 'host-profile'
    package = base / 'installed-source' if knowledge else profile / 'installed-source'
    return project, evidence, profile, package


def main():
    global check_package, digest, redact, history_snapshot
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, choices=('codex', 'claude'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--skip-inspect', action='store_true', help='Retest the affected repair and verification paths only')
    parser.add_argument('--verify-missing-tests', action='store_true', help='Controlled verification variant: remove test contents after closure; the model must only propose missing tests')
    parser.add_argument('--diagnostic', action='store_true', help='Retest the same controlled intent classes with alpha.3 investigation and original-criterion repair')
    parser.add_argument('--claude-model', help='Explicit human-selected Claude Code model for this controlled process only')
    parser.add_argument('--preflight-only', action='store_true', help='Validate the selected complete runtime without profile writes, installation or model requests')
    parser.add_argument('--prepare-only', action='store_true', help='Install and discover in isolated profiles, save prompts/scope, then stop before any model transport')
    parser.add_argument('--structured', action='store_true', help='IMP-006 complex spec, original-proof pause, REV and fresh-session acceptance')
    parser.add_argument('--knowledge', action='store_true', help='IMP-007 nine fresh-session formal owner, approval, adoption and successor cases')
    parser.add_argument('--session-learning', action='store_true', help='Expanded IMP-004 normal-pause/fresh-session/second-task model cases')
    parser.add_argument('--read-user-guide', action='store_true', help='Pin current offline user-guide reading into the bounded final delivery scope')
    parser.add_argument('--headless-safe-io', action='store_true', help='Claude structured fixture: project-local CLI receipts and text-only pending decisions')
    parser.add_argument('--authorization-text', help='Actual human authorization for the expanded scope; not needed for read-only preflight/preparation')
    parser.add_argument('--expected-scope-digest', help='Exact reviewed expanded scope digest from preflight/preparation')
    args = parser.parse_args()
    if args.headless_safe_io and not (args.host == 'claude' and args.structured):
        parser.error('--headless-safe-io is limited to the reviewed Claude structured fixture')
    if args.prepare_only and args.preflight_only:
        parser.error('--prepare-only and --preflight-only are separate modes')
    if args.session_learning and args.skip_inspect:
        parser.error('Expanded fresh-session acceptance requires all five ordered cases')
    if args.claude_model and args.host != 'claude':
        parser.error('--claude-model applies only to the Claude host')
    if args.structured and any((args.session_learning, args.skip_inspect, args.verify_missing_tests, args.diagnostic)):
        parser.error('--structured has seven fixed cases; legacy variants cannot alter its scope')
    if args.knowledge and any((args.structured, args.session_learning, args.skip_inspect, args.verify_missing_tests, args.diagnostic)):
        parser.error('--knowledge has nine fixed cases; legacy variants cannot alter its scope')
    supplied = args.package.resolve()
    # Controller helpers must match the actual pinned archive protocol, not this checkout.
    sys.path.insert(0, str(supplied / 'runtime'))
    from evolve_core.package import check_package, digest, canonical
    from evolve_core.privacy import redact
    from evolve_core.reading import history_snapshot
    manifest = check_package(supplied)
    scope = None
    if args.session_learning or args.structured or args.knowledge:
        if args.structured:
            from model_complex_checks import scope_for as complex_scope
        from model_session_checks import scope_for
        if args.knowledge:
            from model_knowledge_checks import scope_for as knowledge_scope
        try:
            scope = (knowledge_scope(manifest, args.host, args.claude_model, Path(__file__)) if args.knowledge else
                complex_scope(manifest, args.host, args.claude_model, Path(__file__)) if args.structured else
                scope_for(manifest, args.host, args.claude_model, original_fixture(), Path(__file__), missing_tests=args.verify_missing_tests))
        except ValueError as error:
            parser.error(str(error))
        if args.headless_safe_io:
            prefix = ('本轮是无交互验收：不调用AskUserQuestion；需待下一轮明确决定时，只保存／呈现待决候选并用文字结束，'
                      '不能代替下一轮的具体批准。所有原审批门禁照常保留。'
                      'Bash每次只运行一条直接python3命令；读取／检索用Read、Grep、Glob，不用Bash的rg、管道、复合命令或变量。'
                      '全部Evolve CLI调用使用控制侧只读桥 .agents/evolve-acceptance/evolve_bridge.py：'
                      'python3 -B <该桥的绝对路径> <动作> [目标] --owner evolve-<负责者> --method <方法> --request <本项目请求JSON>。'
                      '桥只调用原公共CLI、保存原始响应并输出小摘要，不补授权或改业务；receipt文件的response是原CLI JSON，stdout／stderr／退出码原样另存。完整响应在摘要receipt指向的本项目文件内，'
                      '用Read分段读取或小型Python只读解析所需字段，不把完整大JSON打印到Bash输出。请求、辅助脚本仍用Write保存本项目requests目录。'
                      '不能修改此桥，不读取宿主包外tool-results产物或其他项目，不复做已被拒绝的操作。任何真实权限／额度／传输失败仍立即停止。\n')
            scope['cases'] = {case: prefix + prompt for case, prompt in scope['cases'].items()}
            scope['headless_safe_io'] = {'bridge_template_sha256': digest(HEADLESS_BRIDGE.encode()),
                                         'question_tool': 'disabled; pending approval remains for the exact next user turn'}
            scope['scope_digest'] = digest(canonical({k: v for k, v in scope.items() if k != 'scope_digest'}))
        if args.read_user_guide:
            prefix = ('本次完整安装与项目启用已由控制侧按安装指南在隔离配置中准备；先只读实际安装根的 README.md、docs/installation.md 和 docs/usage.md 中与本轮有关的步骤，'
                      '再执行下述准确请求，不重新安装或更改宿主配置；发现指南与实际接口不一致则如实报告，不绕过。\n')
            scope['cases'] = {case: prefix + prompt for case, prompt in scope['cases'].items()}
            scope['offline_user_guides'] = ['README.md', 'docs/installation.md', 'docs/usage.md']
            scope['final_delivery_scope'] = 'Same bounded business cases; current complete package and offline user guides, not a new production or configuration authorization.'
            scope['scope_digest'] = digest(canonical({k: v for k, v in scope.items() if k != 'scope_digest'}))
        if not args.preflight_only and not args.prepare_only:
            if not args.authorization_text or not args.authorization_text.strip():
                parser.error('Expanded model dispatch needs the actual human authorization for the reviewed new scope')
            if args.expected_scope_digest != scope['scope_digest']:
                parser.error('Expanded scope differs from the reviewed digest; prepare and review the actual scope first')
    if args.read_user_guide and scope is None:
        parser.error('Guide acceptance requires one explicit bounded expanded scope')
    if args.preflight_only:
        print(json.dumps({'package_version': manifest['package_version'], 'schema_version': manifest['schema_version'],
                          'protocol_version': manifest['protocol_version'], 'content_digest': manifest['content_digest'],
                          'controller_runtime': str(supplied / 'runtime'), 'model_requests_sent': False,
                          'host_profile_created': False, 'preflight_only': True, 'expanded_scope': scope}))
        return 0
    if args.out is None:
        parser.error('--out is required for an actual controlled host run')
    lab = args.out.resolve()
    lab.mkdir(mode=0o700, parents=True, exist_ok=False)
    project, evidence, profile, package = installation_roots(lab, knowledge=args.knowledge or args.structured)
    for path in (project, evidence, profile):
        path.mkdir(parents=True)
    download = lab / 'download'
    shutil.copytree(supplied, download)
    shutil.copytree(download, package)
    shutil.rmtree(download)
    save(evidence / 'installation-layout.json', {'supplied_artifact': str(supplied), 'download_copy_removed': True,
         'persistent_local_marketplace_installation_root': str(package),
         'package_and_cache_within_business_root': args.knowledge or args.structured,
         'reason': 'Claude local-directory marketplaces load their relative-path plugin in place. The registered installation root must be retained, independently of the original download.',
         'content_digest': check_package(package)['content_digest']})
    source = project / 'arithmetic.py'
    tests = project / 'test_arithmetic.py'
    for name, content in (scope['first_files'] if scope else original_fixture()).items():
        (project / name).write_text(content)
    (evidence / 'empty-mcp.json').write_text('{"mcpServers":{}}')
    env = {**os.environ, ('CODEX_HOME' if args.host == 'codex' else 'CLAUDE_CONFIG_DIR'): str(profile)}
    if args.host == 'claude':
        env['CLAUDE_CODE_DISABLE_AUTO_MEMORY'] = '1'
    summary = {'host': args.host, 'content_digest': manifest['content_digest'], 'package_version': manifest['package_version'],
               'authorization': 'User explicitly authorized this controlled host-model acceptance in the current chat',
               'model_requests_sent': False, 'automated_checks_passed': False, 'review_status': 'pending', 'passed': False, 'cases': []}
    summary['diagnostic_variant'] = args.diagnostic
    summary['session_learning_variant'] = args.session_learning
    summary['structured_variant'] = args.structured
    summary['knowledge_variant'] = args.knowledge
    summary['prepare_only'] = args.prepare_only
    if scope:
        summary['expanded_scope_digest'] = scope['scope_digest']
        summary['authorization'] = ({'source': 'actual human authorization in this chat', 'text': args.authorization_text}
                                    if args.authorization_text else 'Expanded model dispatch not authorized by this preparation')
        save(evidence / 'expanded-scope.json', scope)
    summary['verify_missing_tests_variant'] = args.verify_missing_tests
    if args.claude_model:
        summary['explicit_user_model_choice'] = args.claude_model
    save(evidence / 'runner-version.json', {'script': 'scripts/model_acceptance.py',
         'sha256': digest(Path(__file__).read_bytes()), 'package_digest': manifest['content_digest']})
    client = None
    def ledger():
        with history_snapshot(project) as (connection, _):
            return {table: {row['id']: dict(row) for row in connection.execute('SELECT * FROM ' + table)}
                    for table in ('changes', 'tasks', 'verifications')}
    try:
        command = ['codex', 'plugin', 'marketplace', 'add', str(package), '--json'] if args.host == 'codex' else [
            'claude', 'plugin', 'marketplace', 'add', str(package), '--scope', 'project']
        shell(command, env=env, cwd=project, log=evidence / 'marketplace.json')
        installed = shell([args.host, 'plugin', 'add' if args.host == 'codex' else 'install', 'evolve@evolve-local',
                           *(('--json',) if args.host == 'codex' else ('--scope', 'project'))],
                          env=env, cwd=project, log=evidence / 'installation.json')
        if args.host == 'codex':
            cache = Path(installed['installedPath'])
            (project / '.codex').mkdir()
            (project / '.codex/config.toml').write_text('[plugins."evolve@evolve-local"]\nenabled=true\n')
            from verify_hosts import codex_skills
            other = lab / 'other-project'
            other.mkdir()
            config = profile / 'config.toml'
            config.write_text(config.read_text().replace('enabled = true', 'enabled = false') +
                              '\n[projects.' + json.dumps(str(project)) + ']\ntrust_level="trusted"\n')
            discovery = codex_skills(env, project, other)
            save(evidence / 'discovery.json', discovery)
            if len(discovery[0]['skills']) != 8 or discovery[1]['skills']:
                raise RuntimeError('Isolated Codex installation or project scope failed')
            if not args.prepare_only:
                client = CodexSession(project, evidence)
        else:
            installed = shell(['claude', 'plugin', 'list', '--json'], env=env, cwd=project, log=evidence / 'installed.json')
            cache = Path(next(p['installPath'] for p in installed if p['id'] == 'evolve@evolve-local'))
            if scope or args.prepare_only:
                from verify_hosts import claude_skills
                discovery = claude_skills(env, project)
                save(evidence / 'discovery.json', discovery)
                if not discovery['complete']:
                    raise RuntimeError('Isolated Claude Skill discovery failed')
        if check_package(cache)['content_digest'] != manifest['content_digest']:
            raise RuntimeError('Actual installation differs from the requested package')
        if args.knowledge or args.structured:
            for path in (package, cache):
                try:
                    path.resolve().relative_to(project)
                except ValueError as error:
                    raise RuntimeError('Controlled acceptance requires actual installation and cache inside the disposable business root') from error
            observed = json.loads(shell([sys.executable, '-B', str(cache / 'runtime/evolve.py'), '--project', str(project), 'status'],
                env=env, cwd=project, log=evidence / 'installed-readonly-status.json'))
            if not observed['ok'] or observed['data']['project']['state'] != 'not_connected':
                raise RuntimeError('Installed controlled runtime did not preserve the untouched project before model dispatch')
        summary['registered_installation_root'] = str(package)
        summary['host_cache_root'] = str(cache)
        bridge, bridge_digest = None, None
        if args.headless_safe_io:
            bridge, bridge_digest = prepare_headless_bridge(project, cache, evidence)
        initial_lab_entries = {path.name for path in lab.iterdir()}
        if args.prepare_only:
            for case, prompt in (scope['cases'] if scope else PROMPTS).items():
                actual = claude_input(prompt, project, cache) if args.host == 'claude' else prompt + '\n' + LIMITS
                (evidence / (case + '-prompt.txt')).write_text(actual + '\n')
            summary['preparation_status'] = 'installed_and_discovered_no_model_dispatch'
            summary['scope_authorization_required'] = bool(scope)
            return 0
        checker = None
        if scope:
            from model_session_checks import SessionChecks
            if args.knowledge:
                from model_knowledge_checks import KnowledgeChecks
                checker = KnowledgeChecks(project, scope, evidence, package=cache, registered_root=package)
            elif args.structured:
                from model_complex_checks import ComplexChecks
                checker = ComplexChecks(project, scope, evidence, package=cache, registered_root=package)
            else:
                checker = SessionChecks(project, scope, evidence)
        prompts = scope['cases'] if scope else PROMPTS
        for case, prompt in prompts.items():
            if not scope and args.diagnostic and case == 'inspect':
                prompt = '使用 Evolve 即时解释一下总计为什么不对，说明实际代码、症状和建议；暂不留档，不接入，不修改业务代码。'
            if not scope and args.diagnostic and case == 'repair':
                prompt = ('使用 Evolve 接入此项目，检查入口为 python3 -B -m unittest discover -v。先独立留档调查总计错误，'
                          '保存真实失败、独立预期、原症状判据、来源和限制，不为调查创建 Change。随后呈现具体短方案，'
                          '引用调查与原判据，在 arithmetic.py 与 test_arithmetic.py 范围内修复，保留原三条独立断言；'
                          '按原判据复验、完成真实检查和规格／规范审查后封存。授权在该范围内修正验收发现；'
                          '不批准正式项目知识。请忠实记录实际用户来源，不预填结论。')
            if case == 'inspect' and args.skip_inspect:
                continue
            if checker:
                checker.before(case, missing_tests=args.verify_missing_tests)
                if case == 'verify' and args.verify_missing_tests:
                    prompt += ' 如果缺少可用测试，仅提出补测方案，不要补写。'
            elif case == 'verify':
                before_ledger = ledger()
                source.write_text('def total(values):\n    return len(values)\n')
                if args.verify_missing_tests:
                    tests.write_text('')
                    prompt += ' 如果缺少可用测试，仅提出补测方案，不要补写。'
            before = ({path.name: path.read_bytes() for path in (source, tests)} if not (args.structured or args.knowledge) else None)
            actual = claude_input(prompt, project, cache) if args.host == 'claude' else prompt + '\n' + LIMITS
            (evidence / (case + '-prompt.txt')).write_text(actual + '\n')
            print(json.dumps({'host': args.host, 'case': case, 'state': 'started'}), flush=True)
            summary['model_requests_sent'] = True
            save(evidence / 'summary.json', summary)
            if args.host == 'codex':
                result = client.run(prompt, cache)
            else:
                argv = ['claude', '--print', '--verbose', '--output-format', 'stream-json', '--no-session-persistence',
                        '--setting-sources', 'project', '--permission-mode', 'acceptEdits', '--strict-mcp-config',
                        '--mcp-config', str(evidence / 'empty-mcp.json'), '--disallowedTools',
                        'Agent,Task,AskUserQuestion' if args.headless_safe_io else 'Agent,Task',
                        '--allowedTools', 'Read,Write,Edit,Glob,Grep,Skill,Bash(python3:*),Bash(ls:*),Bash(cat:*),Bash(rg:*)']
                if args.claude_model:
                    argv += ['--model', args.claude_model]
                result = claude_case(argv, actual, env=env, project=project,
                                     log=evidence / (case + '-model.json'))
            unexpected = sorted(path.name for path in lab.iterdir()
                                if path.name not in initial_lab_entries)
            if unexpected:
                raise AssertionError('Host left request artifacts outside the business project: ' + ', '.join(unexpected))
            if checker:
                observation = checker.after(case)
                if bridge and digest(bridge.read_bytes()) != bridge_digest:
                    raise AssertionError('Model modified the controlled public-CLI receipt bridge')
                save(evidence / (case + '-parent-observation.json'), observation)
                summary['cases'].append({'case': case, 'model_result': result, 'parent_observation': observation})
                save(evidence / 'summary.json', summary)
                print(json.dumps({'host': args.host, 'case': case, 'state': 'observed'}), flush=True)
                continue
            if case != 'repair':
                if any(path.read_bytes() != before[path.name] for path in (source, tests)):
                    raise AssertionError('Read-only intent changed business or test bytes')
                if args.diagnostic and case == 'inspect' and ((project / 'evolve').exists() or (project / '.evolve-local').exists()):
                    raise AssertionError('Immediate answer created record facilities despite explicit no-record intent')
                if case == 'verify':
                    after = ledger()
                    if any(after[table] != before_ledger[table] for table in ('changes', 'tasks')):
                        raise AssertionError('Verification reopened or changed completed work')
                    if any(after['verifications'].get(key) != row for key, row in before_ledger['verifications'].items()):
                        raise AssertionError('Verification rewrote historical evidence')
                    fresh = [row for key, row in after['verifications'].items() if key not in before_ledger['verifications']]
                    if not fresh or not any(row['status'] in ('failed', 'blocked') for row in fresh):
                        raise AssertionError('Current failed scope was not recorded by the supported archived verification path')
            else:
                original_assertions = [ast.dump(node) for node in ast.walk(ast.parse(before[tests.name]))
                                       if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'assertEqual']
                current_assertions = [ast.dump(node) for node in ast.walk(ast.parse(tests.read_bytes()))
                                      if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'assertEqual']
                if any(item not in current_assertions for item in original_assertions):
                    raise AssertionError('Existing independent test assertions changed or were removed')
                # Execute the original literal assertions independently of any
                # test additions or formatting the model may have introduced.
                check = subprocess.run([sys.executable, '-B', '-c', before[tests.name].decode() + '\nunittest.main()\n'],
                                       cwd=project, capture_output=True, text=True, timeout=30)
                save(evidence / 'independent-check.json', {'exit_code': check.returncode, 'stdout': check.stdout, 'stderr': check.stderr})
                db = sqlite3.connect(project / 'evolve/history.db')
                try:
                    changes = db.execute('SELECT state FROM changes').fetchall()
                    verifications = db.execute('SELECT status FROM verifications').fetchall()
                    if check.returncode or not changes or any(r[0] != 'archived' for r in changes) or not verifications or verifications[-1][0] != 'passed':
                        raise AssertionError('Actual checks, Evolve verification and closure did not all pass')
                    if args.diagnostic:
                        analyses = db.execute("SELECT id,result_json,result_digest FROM phase_runs WHERE action='analyze' AND status='completed'").fetchall()
                        if not analyses or not any(json.loads(row[1]).get('analysis', {}).get('symptom', {}).get('status') == 'reproduced' for row in analyses):
                            raise AssertionError('Repair did not preserve an independent investigation with actual red evidence')
                        definitions = [json.loads(row[0]) for row in db.execute('SELECT definition_json FROM tasks')]
                        if any(not definition.get('analysis_basis') or not definition.get('symptom_before') for definition in definitions):
                            raise AssertionError('Diagnostic repair bypassed the original investigation/criterion binding')
                        latest = json.loads(db.execute('SELECT items_json FROM verifications ORDER BY observed_at DESC LIMIT 1').fetchone()[0])
                        if not latest.get('symptom_result'):
                            raise AssertionError('No original-criterion post-repair observation was saved')
                finally:
                    db.close()
                if (project / 'evolve/project.md').exists():
                    raise AssertionError('Formal knowledge was applied without specific approval')
            summary['cases'].append({'case': case, 'model_result': result, 'business_digest': digest(source.read_bytes())})
            save(evidence / 'summary.json', summary)
            print(json.dumps({'host': args.host, 'case': case, 'state': 'observed'}), flush=True)
        summary['automated_checks_passed'] = True
    except Exception as error:
        summary['error'] = redact(str(error))
    finally:
        if client:
            client.close()
        save(evidence / 'summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary['automated_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
