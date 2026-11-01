"""Four fresh Codex sessions restore a damaged archive without reverting business."""
import hashlib
import json
import os
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
GUIDE = '# Recovery terms\n\nTotal means integer sum. Archive recovery never restores business code or data.\n'
EXTRA = '# Later fact\n\nThis separately approved temporary document was registered after the selected backup.\n'
EXTERNAL_GUIDE = GUIDE + '\nUnapproved external note before archive damage.\n'
UNKNOWN = 'An unregistered user file must remain in place.\n'
BROKEN = 'def total(values):\n    return len(values)\n'
FILES = {'total.py': BROKEN, 'test_total.py': 'import unittest\nfrom total import total\nclass TotalTests(unittest.TestCase):\n    def test_literals(self):\n        self.assertEqual(total([2,3]),5)\n        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n'}
CHECKS = [{'id': 'total', 'argv': ['python3', '-B', '-m', 'unittest', 'test_total'], 'cwd': '.', 'timeout': 30}]
TITLE = 'Restore fixture total'
PROMPTS = {
    'seed': ('在本临时项目使用 Evolve 接入，只登记下面的固定 total 检查。呈现并保存短方案“' + TITLE +
        '”，scope 仅 total.py，必需 total，AC 为原三个列表字面量 5／0／1；已统一授权完整实施验证，具体接受本方案后仅经 apply '
        '把 len 修为整数求和，真实检查及逐 AC／规格和规范双轴验收通过后 archive。保留 test_total.py 原字节，不补测试。'
        '再仅以 init.baseline.propose／baseline.apply 初次建立 terms.md，expected_digest=null，实际完整呈现并按本次准确批准登记：\n' + GUIDE +
        '\n该临时正文已由实际统一验收授权及本准确夹具具体批准，不另问用户。最后 maintain.backup，保存完整目录／manifest_digest／checkpoint 回执；'
        '不手写数据库或恢复控制材料，不执行外部业务。\n固定检查：' + json.dumps(CHECKS, ensure_ascii=False)),
    'later': ('不修改业务文件／测试／terms.md，也不新增备份。仅以 Evolve init 的初次基线提案和应用，建立 later.md，expected_digest=null，'
        '实际呈现下面完整正文，并按本次准确临时批准应用：\n' + EXTRA +
        '\n该临时全文已由统一验收授权及本准确夹具具体批准，不另问。说明它晚于给定选中备份，不伪称已在该包。保持原封存与历史。'),
    'restore': ('控制侧已真实损坏当前 history.db／sidecar，将 terms.md 追加固定未批准字节，把 total.py 手改回 len 错误，'
        '并创建 unknown.md 未登记用户文件及一条仅受控引用的外部 running 保护。现在只恢复给定准确旧备份，已授权该具体档案恢复与 '
        'later.md 的保护隔离。读 evolve-maintain 和 shared/recovery.md，损坏库不重跑 init／改 DB／删屏障，也不因 status 不可读停止在建议。'
        '用 maintain.restore stage=plan 展示实际集合／当前字节和差异，再以准确 plan_id／plan_digest 执行 apply。调用前保存完整唯一 request_id、'
        '项目／原 epoch／真实授权，恢复未知结果只用原请求。原损坏 DB／sidecar、未批准 Terms 和包外 later.md 必须保护；未知用户文件留原位。'
        '不运行检查、不修复或回退 total.py／测试，不重放业务或把历史 passed 当当前通过。外部引用只是保护演练，不发生派发，恢复后仍需核实。'),
    'current_verify': ('恢复已完成。本轮只验收原封存“' + TITLE + '”的当前业务现场：total.py 已被控制侧改为 len，恢复不还原源码。'
        '按原三个字面量及原 total 检查真实运行 verify.run，逐 AC 和双轴观察如实保存 failed／blocked，保留原历史 passed／封存截点。'
        '不修业务／测试，不重开、不应用或批准新知识；terms.md 应为选中旧批准版本，later.md 已在保护隔离，unknown.md 原位。'
        '说明当前差异、旧请求不能重放、新 epoch 与外部未决仍需核实，不能称当前业务已通过。'),
}


def scope_for(package):
    from evolve_core.package import check_package, canonical
    manifest = check_package(package)
    if (manifest['schema_version'], manifest['protocol_version']) not in ((4, 15), (4, 16), (4, 17)):
        raise ValueError('Recovery acceptance requires the actual complete schema4/protocol15-or-16 package')
    names = ['scripts/model_recovery_acceptance.py', 'scripts/model_recovery_checks.py',
             'scripts/model_data_acceptance.py', 'scripts/model_acceptance.py', 'scripts/verify_hosts.py']
    body = {'slice': 'IMP-012', 'host': 'codex', 'package_version': manifest['package_version'],
        'content_digest': manifest['content_digest'], 'protocol_version': manifest['protocol_version'], 'schema_version': 4,
        'first_files': FILES, 'checks': CHECKS, 'business_write_paths': ['total.py'], 'readonly_paths': ['test_total.py'],
        'cases': PROMPTS, 'maximum_sessions': 4, 'fresh_conversation_per_case': True,
        'formal_decisions': {'terms.md': GUIDE, 'later.md': EXTRA, 'scope': 'Exact temporary initial baselines only; later restore returns Terms and protects/quarantines Later.'},
        'parent_mutations': {'before_restore': {'total.py': BROKEN, 'terms.md': EXTERNAL_GUIDE, 'unknown.md': UNKNOWN,
            'history.db': 'actual invalid SQLite bytes; original recorded before damage',
            'history.db-wal': 'actual invalid sidecar bytes', 'external': 'one fixed pending reference; no actual dispatch'}},
        'model_selection': 'actual model/list isDefault; no model replacement',
        'authorization_limits': ['Uniform actual human continuation authorization; controlled temporary project only.',
            'Only total.py may change through seed apply; test_total.py stays read-only. Exact temporary Terms/Later initial approvals are listed above.',
            'Restore manages archive/control/approved documents only; preserve all current business bytes and unknown files.',
            'No Claude, personal config/credentials, nested agents, CI/hook, production/external dispatch, publication or deployment.',
            'Permission/quota/transport or parent failure stops the host; same-scope repairs/retests keep failed evidence.'],
        'runner_files': {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}}
    return {**body, 'scope_digest': hashlib.sha256(canonical(body)).hexdigest()}


class RecoveryChecks:
    def __init__(self, project, evidence, scope, package, registered):
        self.project, self.evidence, self.scope = project, evidence, scope
        self.package, self.registered = package, registered
        self.packages = {str(p): self.inventory(p) for p in (package, registered)}
        self.configs = {p: p.read_bytes() for p in (project / '.codex/config.toml', registered.parent / 'profile/config.toml')}
        self.original_test = ((project / 'test_total.py').read_bytes(), (project / 'test_total.py').stat().st_mtime_ns)
        self.selected = None

    @staticmethod
    def inventory(root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

    def rows(self, table):
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection, _):
            return [dict(r) for r in connection.execute('SELECT * FROM ' + table)]

    def context_for(self, case):
        return '\n控制侧提供的准确选中备份原回执：' + json.dumps(self.selected, ensure_ascii=False) if case in ('later', 'restore') else ''

    def before(self, case):
        if case == 'restore':
            (self.project / 'total.py').write_text(BROKEN)
            (self.project / 'terms.md').write_text(EXTERNAL_GUIDE)
            (self.project / 'unknown.md').write_text(UNKNOWN)
            database = self.project / 'evolve/history.db'
            self.old_database_digest = hashlib.sha256(database.read_bytes()).hexdigest()
            database.write_bytes(b'actual controlled damaged SQLite archive\x00\xff')
            (self.project / 'evolve/history.db-wal').write_bytes(b'actual controlled damaged sidecar')
            external = self.project / '.evolve-local/control/external.json'
            value = json.loads(external.read_text())
            value['pending'] = [{'operation_id': 'controlled-reference-only-no-dispatch', 'state': 'running',
                                 'resources': ['temporary:recovery-reference'], 'target': 'controlled-reference-only'}]
            external.write_text(json.dumps(value))
        self.before_files = {n: ((self.project / n).read_bytes(), (self.project / n).stat().st_mtime_ns)
                             for n in ('total.py', 'test_total.py')}

    def after(self, case):
        from evolve_core.package import check_package
        for root in (self.package, self.registered):
            assert check_package(root)['content_digest'] == self.scope['content_digest']
            assert self.inventory(root) == self.packages[str(root)], 'Installed package changed'
        assert all(p.read_bytes() == content for p, content in self.configs.items()), 'Host configuration changed'
        assert ((self.project / 'test_total.py').read_bytes(), (self.project / 'test_total.py').stat().st_mtime_ns) == self.original_test
        if case != 'seed':
            assert ((self.project / 'total.py').read_bytes(), (self.project / 'total.py').stat().st_mtime_ns) == self.before_files['total.py']
        actual_checks = tomllib.loads((self.project / 'evolve/config.toml').read_text())['verification']['checks']
        assert actual_checks == CHECKS
        changes, tasks, verifications, runs = (self.rows(t) for t in ('changes', 'tasks', 'verifications', 'phase_runs'))
        assert len(changes) == 1 and changes[0]['title'] == TITLE and changes[0]['state'] == 'archived'
        assert len(tasks) == 1 and tasks[0]['state'] == 'done'
        assert not self.rows('resource_claims') and not [r for r in runs if r['status'] == 'started']
        assert any(v['status'] == 'passed' for v in verifications)
        if case == 'seed':
            assert (self.project / 'terms.md').read_text() == GUIDE
            assert not (self.project / 'later.md').exists()
            backups = [r for r in runs if (r['action'], r['method'], r['status']) == ('maintain', 'backup', 'completed')]
            assert len(backups) == 1
            self.selected = json.loads(backups[0]['result_json'])
            from evolve_core.archive_sets import validate_archive
            manifest = validate_archive(Path(self.selected['path']), self.selected['manifest_digest'])
            assert {r['path'] for r in manifest['files']} == {'evolve/history.db', 'evolve/config.toml', 'terms.md'}
            self.old_epoch = manifest['workspace_epoch']
            self.old_verifications = {v['id']: v for v in verifications}
            assert (self.project / 'total.py').read_bytes() != BROKEN.encode()
        elif case == 'later':
            assert (self.project / 'terms.md').read_text() == GUIDE
            assert (self.project / 'later.md').read_text() == EXTRA
            assert len([r for r in runs if (r['action'], r['method']) == ('maintain', 'backup')]) == 1
        else:
            assert (self.project / 'terms.md').read_text() == GUIDE
            assert not (self.project / 'later.md').exists()
            assert (self.project / 'unknown.md').read_text() == UNKNOWN
            assert (self.project / 'total.py').read_text() == BROKEN
            barrier = json.loads((self.project / '.evolve-local/control/maintenance.json').read_text())
            assert barrier['state'] == 'completed' and barrier['new_epoch'] != self.old_epoch
            folder = self.project / '.evolve-local/control/restores' / barrier['plan_id']
            journal = json.loads((folder / 'journal.json').read_text())
            assert journal['state'] == 'completed'
            protection = folder / 'protection'
            assert (protection / 'terms.md').read_text() == EXTERNAL_GUIDE
            assert (protection / 'later.md').read_text() == EXTRA
            assert (protection / 'evolve/history.db').read_bytes() == b'actual controlled damaged SQLite archive\x00\xff'
            assert (protection / 'evolve/history.db-wal').read_bytes() == b'actual controlled damaged sidecar'
            external = json.loads((self.project / '.evolve-local/control/external.json').read_text())
            assert len(external['pending']) == 1 and external['pending'][0]['state'] == 'unknown'
            assert external['pending'][0]['operation_id'] == 'controlled-reference-only-no-dispatch'
            current_verifications = {v['id']: v for v in verifications}
            assert all(current_verifications[k] == row for k, row in self.old_verifications.items())
            if case == 'restore':
                assert len(verifications) == len(self.old_verifications), 'Restore reran or rewrote checks'
            else:
                latest = sorted(verifications, key=lambda r: (r['observed_at'], r['id']))[-1]
                assert latest['status'] in ('failed', 'blocked')
                assert len(verifications) > len(self.old_verifications)
        visible = set()
        for directory, subdirs, names in os.walk(self.project):
            subdirs[:] = [n for n in subdirs if n not in {'evolve', '.evolve-local', '.agents', '.codex', '__pycache__'}]
            visible.update((Path(directory) / n).relative_to(self.project).as_posix() for n in names)
        expected = set(FILES) | {'terms.md'} | ({'later.md'} if case == 'later' else set()) | ({'unknown.md'} if case in ('restore', 'current_verify') else set())
        assert visible == expected, 'Unexpected business files: ' + str(visible ^ expected)
        return {'case': case, 'changes': len(changes), 'archived': True, 'verifications': len(verifications),
                'selected_backup': self.selected, 'business_test_immutable': True,
                'pending_runs': 0, 'active_claims': 0, 'semantic_model_review': 'pending'}
