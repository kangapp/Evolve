"""Three fresh Codex turns after the Claude host stopped on actual HTTP429.

The original Claude batch stays stopped. Reuse the exact stable work, independent
tests, package and parent assertions; no Claude retry or model substitution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--expected-scope-digest')
    args = parser.parse_args()
    frozen = json.loads(Path('/tmp/evolve-imp014-claude-safe-io-current.json').read_text())
    lab = Path(frozen['native_lab'])
    project, old_evidence = lab / 'business', lab / 'evidence'
    evidence = Path('/private/tmp/evolve14-cx-tail/evidence')
    sys.path.insert(0, str(Path(frozen['package']) / 'runtime'))
    sys.path.insert(0, str(Path(frozen['controller']) / 'scripts'))
    from evolve_core.package import canonical, check_package, digest
    from evolve_core.privacy import redact
    from evolve_core.reading import history_snapshot
    from model_complex_checks import ComplexChecks, PROMPTS
    import model_acceptance as host
    host.redact = redact
    def save(path, value):
        path.write_text(redact(json.dumps(value, ensure_ascii=False, indent=2)) + '\n')
    old = json.loads((old_evidence / 'summary.json').read_text())
    scope = json.loads((old_evidence / 'expanded-scope.json').read_text())
    assert scope['scope_digest'] == frozen['scope_digest'] == digest(canonical({k:v for k,v in scope.items() if k != 'scope_digest'}))
    assert not old['automated_checks_passed'] and len(old['cases']) == 4
    stopped = json.loads((old_evidence / 'local_revision-model.json').read_text())
    assert stopped['transport_stop']['basis']['error_status'] == 429
    cache, registered = Path(old['host_cache_root']), Path(old['registered_installation_root'])
    assert check_package(cache)['content_digest'] == check_package(registered)['content_digest'] == frozen['package_digest']
    bridge = json.loads((old_evidence / 'headless-bridge.json').read_text())
    assert digest(Path(bridge['path']).read_bytes()) == bridge['sha256']
    prefix = ('先读取实际插件根README.md、docs/installation.md、docs/usage.md的相关步骤。'
        '安装根为' + str(cache) + '。这是同一临时项目的已授权跨宿主续接：Claude在第五轮只读调查时遇429，'
        '其批次已停止，没有登记该轮写动作，不重试Claude。当前原四检查及两个任务整体验收已通过但未封存；'
        'test_report_mean.py已由控制侧提供，五测试只读。读取真实Evolve档案，不依赖旧聊天，不改宿主配置、桥或安装包。'
        '本轮具体用户意图如下；按公共CLI实际门禁执行，不直接写数据库或业务文件；待下一轮批准的候选仅呈现并结束。\n')
    prompts = {name: prefix + PROMPTS[name] for name in ('local_revision', 'finish_revision', 'verify')}
    if args.prepare_only:
        evidence.mkdir(parents=True, exist_ok=False)
        with history_snapshot(project) as (connection, meta):
            assert connection.execute('SELECT COUNT(*) FROM phase_runs').fetchone()[0] == 10
            assert connection.execute('SELECT COUNT(*) FROM resource_claims').fetchone()[0] == 0
            prepared = {'slice': 'IMP-014-Codex-cross-host-tail', 'host': 'codex',
                'model_selection': 'model/list isDefault', 'package_digest': frozen['package_digest'],
                'source_claude_scope_digest': frozen['scope_digest'], 'initial_checkpoint': meta['checkpoint'],
                'cases': prompts, 'maximum_fresh_sessions': 3, 'business_write_paths': ['report.py'],
                'readonly_tests': sorted(n for n in {**scope['first_files'], **scope['second_files']} if n.startswith('test_')),
                'first_mean_test_already_provided_by_original_controller': True,
                'controller_side_final_report_regression': 'Exact original ComplexChecks.before(verify)',
                'authorization': 'Actual uniform human authorization call_05f0a84076f549568b149504edf7e4b8 and human Codex-first direction',
                'limits': scope['limits'], 'controller_sha256': digest(Path(__file__).read_bytes()),
                'parent_assertions_sha256': digest((Path(frozen['controller']) / 'scripts/model_complex_checks.py').read_bytes())}
        prepared['scope_digest'] = digest(canonical(prepared))
        save(evidence / 'scope.json', prepared)
        print(json.dumps({'prepared': True, 'scope_digest': prepared['scope_digest'], 'model_requests_sent': False}));return
    prepared = json.loads((evidence / 'scope.json').read_text())
    assert args.expected_scope_digest == prepared['scope_digest']
    assert prepared['controller_sha256'] == digest(Path(__file__).read_bytes()) and prepared['cases'] == prompts
    assert digest(canonical({k:v for k,v in prepared.items() if k != 'scope_digest'})) == prepared['scope_digest']
    checker = ComplexChecks(project, scope, evidence, package=cache, registered_root=registered)
    checker.allowed.update(scope['second_files'])
    with history_snapshot(project) as (connection, meta):
        assert meta['checkpoint'] == prepared['initial_checkpoint']
        _, _, tasks, _ = checker.work(connection, mean_required=False)
        checker.original_proof(connection, tasks['CORE'])
        checker.core_digest, checker.core_result = tasks['CORE']['definition_digest'], tasks['CORE']['result_json']
    readonly = {n: ((project/n).read_bytes(), (project/n).stat().st_mtime_ns) for n in prepared['readonly_tests'] + ['arithmetic.py']}
    summary = {'scope_digest': prepared['scope_digest'], 'host': 'codex', 'cases': [],
        'model_requests_sent': True, 'automated_checks_passed': False, 'review_status': 'pending',
        'original_claude_batch_passed': False, 'claude_not_retried': True}
    save(evidence/'summary.json', summary)
    client = None
    try:
        client = host.CodexSession(project, evidence)
        for name, prompt in prompts.items():
            if name == 'local_revision':
                checker.before_files, checker.before_rows = checker.files(), checker.rows()
            else:
                checker.before(name)
            save(evidence/(name+'-before-rows.json'), checker.before_rows)
            save(evidence/(name+'-before-files.json'), {n: hashlib.sha256(b).hexdigest() for n,b in checker.before_files.items()})
            (evidence/(name+'-prompt.txt')).write_text(prompt)
            print(json.dumps({'case': name, 'state': 'started'}), flush=True)
            result = client.run(prompt, cache)
            observed = checker.after(name)
            assert readonly == {n: ((project/n).read_bytes(), (project/n).stat().st_mtime_ns) for n in readonly}
            assert digest(Path(bridge['path']).read_bytes()) == bridge['sha256']
            save(evidence/(name+'-parent-observation.json'), observed)
            summary['cases'].append({'case': name, 'model_result': result, 'parent_observation': observed})
            save(evidence/'summary.json', summary)
            print(json.dumps({'case': name, 'state': 'observed'}), flush=True)
        summary['automated_checks_passed'] = True
    except Exception as error:
        summary['error'] = redact(str(error))
    finally:
        if client: client.close()
        save(evidence/'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if not summary['automated_checks_passed']: raise SystemExit(1)


if __name__ == '__main__':
    main()
