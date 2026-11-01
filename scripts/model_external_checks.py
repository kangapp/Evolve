"""Six fresh native sessions over an actual finite SQLite write mechanism."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from external_fixture import ENTRY, HELPER

TARGET = {'kind': 'sqlite', 'path': 'business.db', 'environment': 'isolated',
          'objects': ['ledger', 'operation_receipts'], 'scope': 'ledger id=1 and this operation receipt only',
          'identity': {'sql': 'SELECT value FROM identity', 'expected': 'temporary-native-target'}}
MECHANISM = ['alias.json', 'helper.py', 'step.sql', 'writer.py']
CHECKS = [{'id': 'data' + str(n), 'argv': ['python3', '-B', '-m', 'unittest', 'test_target' + str(n), '-v'],
           'cwd': '.', 'timeout': 30} for n in (20, 30)]
FILES = {'writer.py': ENTRY, 'helper.py': HELPER,
         'step.sql': 'UPDATE ledger SET value=? WHERE id=1 AND value=?;\n',
         'alias.json': json.dumps({'sql': 'step.sql', 'identity': 'temporary-native-target', 'before': 10, 'after': 20})}
for n in (20, 30):
    FILES['test_target' + str(n) + '.py'] = ('import sqlite3,unittest\nclass ActualTarget(unittest.TestCase):\n'
        '    def test_original_literal(self):\n        db=sqlite3.connect("file:business.db?mode=ro",uri=True)\n'
        '        try:\n            self.assertEqual(db.execute("SELECT id,value FROM ledger ORDER BY id").fetchall(),[(1,' + str(n) + ')])\n'
        '        finally:\n            db.close()\n')
LOST = 'import sys\nfrom helper import execute\nexecute(sys.argv[1],sys.argv[2])\nprint("transport receipt deliberately lost after real commit")\n'
PROMPTS = {
 'seed': ('使用 Evolve 接入本临时项目，只登记给定 data20／data30 检查。只读机制和两个独立测试；'
          '建立短方案“Controlled ledger to 20”，execution_kind=external_write，external_target 为给定准确目标，'
          'scope 为四机制文件及 test_target20.py，required_checks=[data20]，AC 为真实 ledger id=1 从 10 变20且仅有一条独立 provider 收据。'
          '本次准确接受该方案，以及你实际准备／呈现后与给定机制、目标和前置完全一致的候选；授权仅经 external.execute 改数据，不改业务源码／测试。'
          '先 prepare 保存完整有限材料，实际读取 helper 的事务／身份／幂等条件，准确批准其 candidate／target 摘要后 apply，'
          '独立 verify 逐AC／规格与规范审查、archive。最后 maintain.backup 保存准确完整回执供后续恢复。不得用直接 SQLite 写入绕过内核。'),
 'unknown': ('控制侧将 alias 改为20→30，writer 在实际提交后故意不打印有效回执，其他机制／独立测试不变。'
          '使用 Evolve 建立独立短方案“Controlled ledger to 30”，scope 四机制及 test_target30.py、必需 data30、external_write 和给定目标；'
          '准确接受该方案及与控制侧实际机制完全一致的有限候选，prepare／具体批准后仅经 external.execute apply 一次。'
          '本轮到 unknown 停止，保留原 operation、资源与来源；不要自行 reconcile、换ID重发、verify 或 archive，不修复 writer 或测试。'),
 'reconcile': ('只核实“Controlled ledger to 30”的原 unknown 操作，不发送数据。先 external.reconcile，单独对账 provider 收据及完整ledger行；'
          '随后对该原操作 external.execute stage=checks，接受原同一任务具体方案以继续原 data30 检查。'
          '独立 verify 逐AC／规格与规范审查并 archive；保留前次 unknown 及第一个已封存项。不改任何机制、测试或数据，不新建 Change 或重发。'),
 'compensate': ('控制侧将 alias 改为30→20，writer 仍故意丢回执。原30操作已确认结束且完整范围已知。'
          '使用 Evolve 为补偿建立独立方案“Controlled compensation to 20”，scope 四机制及 test_target20.py、必需data20、external_write和同一目标。'
          '准确接受此新方案及实际 prepare／呈现后与固定30→20机制一致的新候选。仅经 external.compensate prepare，关联给定原30操作；'
          '按补偿自身准确摘要批准后 apply 一次。到补偿 unknown 停止，不核实／重发／验收／封存，不改源码或测试。'),
 'restore_reconcile': ('控制侧已真实损坏 Evolve history.db／sidecar，业务数据库保持20，补偿的真实未决保护与来源仍存在。'
          '仅按给定第一轮完整备份执行准确 restore 方案和 apply，本次授权保护当前现场并恢复该准确旧档案；不重跑 init、不直接改库或控制索引。'
          '维护只恢复档案，不回滚业务数据，不派发旧命令。随后按给定补偿 operation 以 external.reconcile 只读核实，'
          '即使补偿 Task 已不在恢复的库，也不能创建／重开任务或伪造旧 run。保留真实来源、恢复保护和观察。不做 verify，不另行调用 maintain.backup；运行时首次受管写入的必要自动保护备份保留，不能关闭或绕过。'),
 'current_verify': ('控制侧将真实 ledger id=1 改为19，原测试和机制字节不变。本轮仅用 Evolve 验收已封存“Controlled ledger to 20”的当前现场。'
          '明确授权实际只读目标及原data20检查，追加真实失败或受阻的逐AC／规格与规范验收；保留历史通过与封存。'
          '不修复数据／机制／测试，不重开或新增任务，不恢复或重发，不写正式知识。说明历史完成和当前变化的区别。')}


def recipe(before, after):
    return {'stage': 'prepare', 'target': copy.deepcopy(TARGET), 'execution': {
        'files': MECHANISM, 'argv': ['writer.py', '{target}', '{operation_id}'], 'cwd': '.', 'timeout': 30,
        'closure': {'complete': True, 'no_detached_or_delayed_work': True,
                    'observer': 'must-be-actual-native-host-review', 'basis': 'Replace with actual finite source review, not a prefilled conclusion.',
                    'limitations': ['Only the inspected synchronous local SQLite mechanism; no production or detached work.']}},
        'idempotency': {'supported': True, 'basis': 'Host must actually inspect unique provider receipt check in the same BEGIN IMMEDIATE transaction.'},
        'preconditions': [{'sql': 'SELECT id,value FROM ledger WHERE id=1', 'expected_rows': [[1, before]], 'description': 'Exact single-row prior condition.'}],
        'reconciliation': {'receipt': {'sql': 'SELECT operation_id,outcome,known_effects_json,finished FROM operation_receipts WHERE operation_id=?', 'parameters': ['{operation_id}']},
            'complete_scope': True, 'coverage_basis': 'Host must actually inspect all four finite materials and target scope.',
            'effects': [{'sql': 'SELECT id,value FROM ledger WHERE id=1', 'expected_rows': [[1, after]], 'description': 'Complete actual target row; provider receipt separately attributed by original operation ID.'}]},
        'limitations': ['Only a controlled finite SQLite mechanism; no production claim. Missing transport receipt must remain unknown until a separate actual probe.']}


def inventory(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_symlink()}


def scope_for(package):
    from evolve_core.package import check_package, canonical
    manifest = check_package(package)
    assert (manifest['protocol_version'], manifest['schema_version']) == (17, 4)
    body = {'slice': 'IMP-013', 'host': 'codex', 'package_version': manifest['package_version'],
        'content_digest': manifest['content_digest'], 'protocol_version': manifest['protocol_version'], 'schema_version': 4,
        'first_files': FILES, 'business_write_paths': [], 'readonly_paths': list(FILES),
        'external_write_target': TARGET, 'external_transitions': ['10→20', '20→30 with lost receipt', '30→20 compensation with lost receipt'],
        'parent_initial_database': 'Actual new SQLite business.db identity/ledger(1,10)/empty operation_receipts; no Evolve initialization.',
        'parent_mutations': ['Before unknown change only alias 20→30 and writer to finite lost receipt entry',
            'Before compensate change only alias 30→20', 'Before restore actually corrupt tool DB and sidecar, preserve business.db and pending source',
            'Before current_verify change only ledger id=1 to19 through an actual independent parent connection'],
        'checks': CHECKS, 'cases': PROMPTS, 'maximum_sessions': 6, 'fresh_conversation_per_case': True,
        'model_selection': 'model/list isDefault at dispatch; no manual replacement',
        'authorization_limits': ['Actual unified human authorization, temporary controlled target only; no formal knowledge decisions',
            'No personal config/credential changes, external applications, nested agents, commits, publication or production execution',
            'Stop on actual quota/permission/transport or parent boundary failure; no automatic model retry'],
        'runner_files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            Path(__file__).resolve(), ROOT / 'scripts/model_external_acceptance.py', ROOT / 'scripts/model_data_acceptance.py',
            ROOT / 'scripts/model_acceptance.py', ROOT / 'scripts/verify_hosts.py', ROOT / 'tests/external_fixture.py')}}
    return {**body, 'scope_digest': hashlib.sha256(canonical(body)).hexdigest()}


class ExternalChecks:
    def __init__(self, project, evidence, scope, package, registered):
        self.project, self.evidence, self.scope, self.package, self.registered = project, evidence, scope, package, registered
        db = sqlite3.connect(project / 'business.db')
        try:
            db.executescript("CREATE TABLE identity(value TEXT); INSERT INTO identity VALUES('temporary-native-target'); "
                'CREATE TABLE ledger(id INTEGER PRIMARY KEY,value INTEGER); INSERT INTO ledger VALUES(1,10); '
                'CREATE TABLE operation_receipts(operation_id TEXT PRIMARY KEY,outcome TEXT,known_effects_json TEXT,finished INTEGER);')
            db.commit()
        finally:
            db.close()
        self.packages = {str(p): inventory(p) for p in (package, registered)}
        base = project / '.agents/evolve-acceptance'
        self.configs = {p: p.read_bytes() for p in (base / 'profile/config.toml', project / '.codex/config.toml')}
        self.selected, self.original30, self.compensation = None, None, None
        self.saved_verifications = {}
        self.manual_backup_run_id = None

    def rows(self, table):
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (db, _):
            return [dict(r) for r in db.execute('SELECT * FROM ' + table)]

    def target_rows(self, query):
        db = sqlite3.connect((self.project / 'business.db').as_uri() + '?mode=ro', uri=True)
        try:
            return db.execute(query).fetchall()
        finally:
            db.close()

    def before(self, case):
        if case in ('unknown', 'compensate'):
            before, after = (20, 30) if case == 'unknown' else (30, 20)
            (self.project / 'alias.json').write_text(json.dumps({'sql': 'step.sql', 'identity': 'temporary-native-target', 'before': before, 'after': after}))
            (self.project / 'writer.py').write_text(LOST)
        elif case == 'restore_reconcile':
            (self.project / 'evolve/history.db').write_bytes(b'actual controlled damaged tool database\x00\xff')
            (self.project / 'evolve/history.db-wal').write_bytes(b'actual controlled damaged tool sidecar')
        elif case == 'current_verify':
            db = sqlite3.connect(self.project / 'business.db')
            try:
                db.execute('UPDATE ledger SET value=19 WHERE id=1'); db.commit()
            finally:
                db.close()
        self.before_files = {n: ((self.project / n).read_bytes(), (self.project / n).stat().st_mtime_ns) for n in FILES}

    def context_for(self, case):
        context = {'target': TARGET, 'checks': CHECKS,
                   'actual_scope_authorization': {**{k: TARGET[k] for k in ('kind', 'path', 'environment', 'objects', 'scope')}, 'provider_identity': TARGET['identity']['expected']}}
        if case in ('seed', 'unknown', 'compensate'):
            context['candidate_recipe_requires_actual_source_review'] = recipe(*( (10, 20) if case == 'seed' else (20, 30) if case == 'unknown' else (30, 20)))
        if self.selected and case == 'restore_reconcile':
            context['exact_selected_backup'] = self.selected
        if self.original30 and case in ('reconcile', 'compensate'):
            context['original_operation_id'] = self.original30
        if self.compensation and case == 'restore_reconcile':
            context['compensation_operation_id'] = self.compensation
        return '\n实际控制侧边界及供准备用的准确字段（审阅结论须真实检查后填写）：' + json.dumps(context, ensure_ascii=False)

    def after(self, case):
        from evolve_core.package import check_package
        for p in (self.package, self.registered):
            assert check_package(p)['content_digest'] == self.scope['content_digest']
            assert inventory(p) == self.packages[str(p)], 'Installed package changed'
        assert all(p.read_bytes() == content for p, content in self.configs.items()), 'Host configuration changed'
        assert all(((self.project / n).read_bytes(), (self.project / n).stat().st_mtime_ns) == saved for n, saved in self.before_files.items()), 'Readonly mechanism or original literal test changed'
        expected_value, expected_receipts = {'seed': (20, 1), 'unknown': (30, 2), 'reconcile': (30, 2),
            'compensate': (20, 3), 'restore_reconcile': (20, 3), 'current_verify': (19, 3)}[case]
        assert self.target_rows('SELECT id,value FROM ledger ORDER BY id') == [(1, expected_value)], 'Actual target value differs'
        receipts = self.target_rows('SELECT operation_id,outcome,finished FROM operation_receipts ORDER BY rowid')
        assert len(receipts) == expected_receipts and all(r[1:] == ('succeeded', 1) for r in receipts), 'Real provider effects missing or repeated'
        runs, changes, tasks, verifications, operations = (self.rows(t) for t in ('phase_runs', 'changes', 'tasks', 'verifications', 'operations'))
        assert not [r for r in runs if r['status'] == 'started'], 'Unsealed native run'
        pending = json.loads((self.project / '.evolve-local/control/external.json').read_text())['pending']
        claims = self.rows('resource_claims')
        if case in ('unknown', 'compensate'):
            assert len(pending) == 1 and claims, 'Lost receipt was treated as no effect'
            operation = next(o for o in operations if o['id'] == receipts[-1][0])
            assert json.loads(operation['result_json'])['effect_outcome'] == 'unknown'
            if case == 'unknown': self.original30 = operation['id']
            else: self.compensation = operation['id']
        else:
            assert not pending and not claims, 'Confirmed ended effects remain unresolved'
        if case == 'seed':
            assert len(changes) == 1 and changes[0]['state'] == 'archived' and tasks[0]['state'] == 'done'
            assert any(v['status'] == 'passed' for v in verifications)
            backups = [r for r in runs if (r['action'], r['method'], r['status']) == ('maintain', 'backup', 'completed')]
            assert len(backups) == 1
            self.selected = json.loads(backups[0]['result_json'])
            self.manual_backup_run_id = backups[0]['id']
            self.saved_verifications = {v['id']: v for v in verifications}
            self.old_epoch = self.selected['workspace_epoch']
        elif case == 'reconcile':
            assert len(changes) == 2 and all(c['state'] == 'archived' for c in changes)
            assert all(t['state'] == 'done' for t in tasks)
            assert any(r['method'] == 'external.reconcile' for r in runs)
            assert any(json.loads(r['input_json'])['request']['input'].get('stage') == 'checks' for r in runs if r['method'] == 'external.execute')
        elif case in ('restore_reconcile', 'current_verify'):
            assert len(changes) == 1 and changes[0]['state'] == 'archived', 'Restored-away work was recreated'
            current = {v['id']: v for v in verifications}
            assert all(current.get(k) == v for k, v in self.saved_verifications.items()), 'Historical verification changed'
            barrier = json.loads((self.project / '.evolve-local/control/maintenance.json').read_text())
            assert barrier['state'] == 'completed' and barrier['new_epoch'] != self.old_epoch
            restored = next(o for o in operations if o['id'] == self.compensation)
            assert json.loads(restored['result_json'])['restored_protection_source']['source_is_protected_capsule_not_a_fabricated_old_run']
            if case == 'restore_reconcile':
                assert set(current) == set(self.saved_verifications), 'Restore/reconcile inferred a business verification'
                protection = self.project / '.evolve-local/control/restores' / barrier['plan_id'] / 'protection'
                assert (protection / 'evolve/history.db').read_bytes() == b'actual controlled damaged tool database\x00\xff'
            else:
                added = [v for k, v in current.items() if k not in self.saved_verifications]
                assert added and any(v['status'] in ('failed', 'blocked') for v in added), 'Current data19 failure was hidden'
        assert {r['id'] for r in runs if (r['action'], r['method']) == ('maintain', 'backup')} == {self.manual_backup_run_id}, 'An extra manual backup was invoked; automatic protection remains allowed'
        return {'case': case, 'actual_ledger': expected_value, 'actual_provider_receipts': len(receipts),
            'pending_external': len(pending), 'active_claims': len(claims), 'changes': len(changes),
            'verifications': len(verifications), 'readonly_files_and_packages_preserved': True, 'semantic_model_review': 'pending'}
