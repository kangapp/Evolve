"""Concrete IMP-006 fixture and parent checks for explicitly authorized native sessions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from model_session_checks import SessionChecks

FIRST_FILES = {
    'arithmetic.py': 'def total(values):\n    return sum(values)\n',
    'report.py': 'def render(values, include_mean=False):\n    return "not implemented"\n',
    'test_arithmetic.py': ('import unittest\nfrom arithmetic import total\nclass OriginalTotal(unittest.TestCase):\n'
        '    def test_original_literals(self):\n        self.assertEqual(total([2,3]),5)\n'
        '        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n'
        '        self.assertEqual(total(iter([2,3])),5)\n'),
    'test_summary.py': ('import unittest\nfrom arithmetic import summarize\nclass Summary(unittest.TestCase):\n'
        '    def test_single_pass(self):\n        self.assertEqual(summarize(iter([2,3])),(5,2))\n'
        '        self.assertEqual(summarize(iter([])),(0,0))\n        self.assertEqual(summarize(iter([-2,3])),(1,2))\n'),
    'test_report.py': ('import unittest\nfrom report import render\nclass Report(unittest.TestCase):\n'
        '    def test_original_format(self):\n        self.assertEqual(render(iter([2,3])),"total=5; count=2")\n'
        '        self.assertEqual(render(iter([])),"total=0; count=0")\n'
        '        self.assertEqual(render(iter([-2,3])),"total=1; count=2")\n'),
    'test_integration.py': ('import unittest\nfrom unittest.mock import patch\nimport report\n'
        'from arithmetic import summarize\nclass Integration(unittest.TestCase):\n'
        '    def test_shared_single_pass_boundary(self):\n'
        '        with patch("report.summarize", wraps=summarize) as shared:\n'
        '            self.assertEqual(report.render(iter([5,-2])),"total=3; count=2")\n'
        '            self.assertEqual(shared.call_count,1)\n'),
}
SECOND_FILES = {'test_report_mean.py': ('import unittest\nfrom report import render\nclass MeanReport(unittest.TestCase):\n'
    '    def test_optional_mean(self):\n'
    '        self.assertEqual(render(iter([2,3]),include_mean=True),"total=5; count=2; mean=2.50")\n'
    '        self.assertEqual(render(iter([]),include_mean=True),"total=0; count=0; mean=0.00")\n'
    '        self.assertEqual(render(iter([-2,3]),include_mean=True),"total=1; count=2; mean=0.50")\n'
    '        self.assertEqual(render(iter([2,3])),"total=5; count=2")\n')}
PRODUCTION = {'arithmetic.py', 'report.py'}
CHECK_MODULES = {'original':'test_arithmetic', 'summary':'test_summary', 'report':'test_report', 'integration':'discover'}
PROMPTS = {
    'propose': ('使用 Evolve 接入当前临时项目，仅形成并保存完整复杂方案，本轮不接受方案、不实施或改业务。'
        '先梳理这个临时项目的整体入口、模块职责、检查方式与关键约束，再形成下述方案；结论限本项目。'
        '目标：保留 arithmetic.total 的现有行为，提取单次迭代的 arithmetic.summarize(values)，返回 (总和,数量)；'
        'report.render(values, include_mean=False) 通过该共享接口生成 total=5; count=2 这样的文本。'
        '按当前六个文件的独立测试核对正数、空输入、负数和一次性迭代器；此轮不实现可选均值。'
        '完整 spec 要呈现目标、边界、行为、约束、取舍、测试决定及未决问题。任务键固定 CORE、REPORT：'
        'CORE 是为报告所必需的预重构，文件仅 arithmetic.py，先证明原 total 行为，再形成共享 summarize；'
        'REPORT 文件仅 report.py，依赖 CORE 的独立任务验收通过。所有测试为只读判据，分别声明相关上下文。'
        '登记检查 ID original、summary、report、integration，命令分别为 python3 -B -m unittest '
        'test_arithmetic -v、test_summary -v、test_report -v、discover -v。CORE 必需 original、summary，'
        '原行为保持只用 original，保留 test_arithmetic.py 原判据；REPORT 必需 report；最终必需 integration。'
        '这是两个模块的广泛接口迁移，声明 broad_migration 及最终集成边界；任务完成不能代替全项通过。'
        '不改测试，不批准正式知识。'),
    'refactor_pause': ('本轮明确接受前一会话已存档、且符合上述固定目标和边界的完整方案。先从 Evolve 恢复并呈现原文，'
        '核对范围和实际授权后，仅实施 CORE；授权范围为 arithmetic.py、后续 report.py 及各已登记真实检查。'
        '先单独准备原 total 的真实前证明，再完成 arithmetic.py 文件段并正常暂停，保留原证明；'
        '文件段暂停不运行后检查，不将 CORE 记 done，不验收或封存。report.py 和全部测试保持。'
        '授权覆盖换会话后的原范围实施、相关修正和真实检查，本轮暂停边界仍须遵守。'),
    'cosmetic_revision': ('使用 Evolve 仅修订当前完整方案的展示：将方案标题改为“单次迭代汇总与报告”，'
        '让 plan 摘要更清楚，并将两个任务的展示标题写得易懂。目标、完成条件、AC、测试决定、范围、'
        '依赖和检查含义全部保持；沿原已接受依据保存新的 REV。保留部分进度、授权及原行为证明。'
        '本轮不实施、不运行检查、不写业务或测试。'),
    'continue': ('无旧聊天续接此项目的未完成工作。使用 Evolve 档案恢复当前完整方案、部分进度、原证明和授权，'
        '重点核对 summarize 的生产与 report.render 的消费链路及当前判据，沿相关链路解决缺口，已有可信背景直接复用。'
        '沿原部分来源与同定义任务继续，不重新制造重构前基线。完成 CORE 的原后检查及独立任务验收，'
        '再实施 REPORT，运行任务检查、最终 integration、逐 AC 与规格／规范审查；原范围内发现必需问题可修正复验。'
        '本轮完成整体验收后停止，不封存，保留活动工作项供下一轮明确需求修订；不改原测试或正式知识。'),
    'local_revision': ('使用 Evolve 修改当前活动方案：report.render 的 include_mean=True 分支增加均值，格式固定为 '
        'total=5; count=2; mean=2.50，保留两位小数；空输入 mean=0.00。默认 False 的原文本和 total／summarize '
        '接口与行为保持。控制侧新增的 test_report_mean.py 是只读独立判据，原测试继续保持。'
        '本轮仅呈现并保存完整新 REV；原有 AC 保留，新增可选均值 AC，REPORT 负责该成果，CORE 的原定义和适用结果应保留。'
        'REPORT 需检查原 report 及新增 test_report_mean，最终 discover 全部测试；可按实际命令增量登记 mean 检查。'
        '说明影响并保留旧整体验收及原证明，本轮不接受新语义方案、不实施、运行检查或封存。'
        '若替换旧阶段“不实现均值”的描述触发 scope_confirmation_required，保存并呈现完整待批准候选，'
        '明确旧 REV 仍生效、候选不是已生成的新 REV；不伪造接受依据或绕过确认。'),
    'finish_revision': ('本轮明确接受前一会话已存档、符合可选均值固定格式及原接口保持边界的完整修订。'
        '使用 Evolve 恢复并呈现新方案，按此具体范围只修改 report.py，保留 arithmetic.py、所有原测试和新增均值判据。'
        '若前轮停在范围确认，本轮的具体接受同时覆盖该固定均值候选中旧阶段“不实现均值”描述的替换，'
        '仅限该均值要求相关描述；保留原 AC、CORE 和原接口边界，先以实际候选摘要完成接受和新 REV 登记再实施。'
        '复用仍适用的 CORE 结果及原证明；实施 REPORT 的新定义，运行已登记原／新检查、最终集成、逐 AC 和规格／规范审查，'
        '原范围内修正必需问题，真实通过后封存。不得用原 REV 的整体验收代替新要求验收，不批准正式知识。'),
    'verify': ('控制侧已明确在 report.py 的 include_mean=True 分支引入一次外部回退。使用 Evolve 仅验收当前已封存工作项，'
        '追加实际当前观察，保留原 Task／Change 终态、历史通过截点及 VER。不要修复业务、测试或强行重开。'
        '说明原结果与当前失败的区别，给出必要后续方案；只运行实际检查和记录验收，不预填结论。'),
}


def scope_for(manifest, host, model, transport):
    required = {'propose.create','update.revise','apply.implement','verify.run','archive.close','resume.show','init.connect'}
    if (manifest['schema_version'], manifest['protocol_version']) not in ((1, 5), (2, 6), (2, 7), (3, 8), (4, 9), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15), (4, 16), (4, 17)) or not required.issubset(manifest['available_methods']):
        raise ValueError('Complex acceptance needs the actual complete schema-1/protocol-5, schema-2/protocol-6-to-7 schema-3/protocol-8 or schema-4/protocol-9-to-11 structured runtime')
    if host == 'claude' and model != 'MiniMax-M3.1-Flash':
        raise ValueError('This reviewed complex scope uses only the human-selected MiniMax-M3.1-Flash process override')
    helpers = (Path(__file__), transport, Path(__file__).with_name('model_session_checks.py'), Path(__file__).with_name('verify_hosts.py'))
    body = {'slice':'IMP-006','host':host,'claude_model':model,'package_version':manifest['package_version'],
        'content_digest':manifest['content_digest'],'schema_version':manifest['schema_version'],'protocol_version':manifest['protocol_version'],
        'model_selection': model if host=='claude' else 'model/list isDefault at dispatch',
        'first_files':FIRST_FILES,'second_files':SECOND_FILES,'business_write_paths':sorted(PRODUCTION),
        'cases':PROMPTS,'fresh_conversation_per_case':True,'maximum_sessions':len(PROMPTS),
        'installation_layout':'.agents/evolve-acceptance/{profile,installed-source} within disposable business root; source and cache immutable',
        'limits':['Only the disposable project, its records and actual installed plugin resources',
            'Original tests and the parent-added mean tests remain read-only',
            'No personal configuration or credential changes; no external apps, nested agents, commits, publication or deployment',
            'Stop the host on quota, permission, transport or parent-check failure; no automatic retry or model/account replacement',
            'No formal project knowledge approval; current environment only'],
        'runner_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers}}
    encoded=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return {**body,'scope_digest':hashlib.sha256(encoded).hexdigest()}


class ComplexChecks(SessionChecks):
    def __init__(self, project, scope, evidence, *, package=None, registered_root=None):
        self.project,self.scope,self.evidence=Path(project),scope,Path(evidence)
        self.project_installation=package is not None
        self.installations=tuple(dict.fromkeys(Path(p).resolve() for p in (package,registered_root or package))) if package is not None else ()
        self.installation_files=self.installed_files()
        self.allowed=set(scope['first_files'])
        self.host_settings=self.settings()
        self.before_rows=self.before_files=None
        self.partial=self.proof=self.core_digest=self.core_result=self.pending_revision=None

    def installed_files(self):
        from evolve_core.package import check_package
        result={}
        for root in self.installations:
            root.relative_to(self.project)
            if root.resolve()!=root:raise AssertionError('Prepared installation root changed its actual target')
            if check_package(root)['content_digest']!=self.scope['content_digest']:
                raise AssertionError('Actual installed complete package differs from reviewed complex scope')
            for path in root.rglob('*'):
                if path.is_symlink():raise AssertionError('Installed package acquired a symbolic alias')
                if path.is_file():result[path.relative_to(self.project).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def rows(self):
        from evolve_core.reading import history_snapshot
        with history_snapshot(self.project) as (connection,_):
            return {table:{row['id']:dict(row) for row in connection.execute('SELECT * FROM '+table)} for table in
                ('changes','tasks','verifications','phase_runs','plan_revisions','events','evidence')}

    def before(self, case, *, missing_tests=False):
        if self.installed_files()!=self.installation_files:raise AssertionError('Prepared plugin installation changed before the next case')
        if missing_tests:
            raise AssertionError('Complex scope does not include a missing-tests variant')
        if case=='local_revision':
            for name,content in self.scope['second_files'].items():
                if (self.project/name).exists(): raise AssertionError('Mean fixture already exists')
                (self.project/name).write_text(content)
            self.allowed.update(self.scope['second_files'])
        if case=='verify':
            source=self.project/'report.py'
            source.write_text(source.read_text()+'\n_evolve_fixture_render = render\ndef render(values, include_mean=False):\n'
                '    if include_mean:\n        return "controlled mean regression"\n    return _evolve_fixture_render(values)\n')
        self.before_files=self.files()
        self.before_rows=self.rows() if (self.project/'evolve/history.db').exists() else None

    def work(self, connection, *, mean_required=True):
        changes=connection.execute('SELECT * FROM changes').fetchall()
        if len(changes)!=1 or changes[0]['complexity']!='complex':
            raise AssertionError('Complex scenario requires exactly one actual complex Change')
        change=dict(changes[0])
        revision=dict(connection.execute('SELECT * FROM plan_revisions WHERE id=?',(change['current_revision'],)).fetchone())
        tasks={json.loads(row['definition_json'])['local_key']:dict(row) for row in connection.execute(
            'SELECT * FROM tasks WHERE revision_id=?',(revision['id'],))}
        if set(tasks)!={'CORE','REPORT'}: raise AssertionError('Expected the two real result tasks CORE and REPORT')
        definitions={key:json.loads(row['definition_json']) for key,row in tasks.items()}
        for key,name in (('CORE','arithmetic.py'),('REPORT','report.py')):
            if set(definitions[key]['scope'])!={name}: raise AssertionError('Task scope exceeded its assigned production file')
        core,report=definitions['CORE'],definitions['REPORT']
        if (not core.get('pre_refactor') or 'test_arithmetic.py' not in core.get('preservation_inputs',[]) or
                set(core.get('preservation_checks',[]))!={'original'} or not {'original','summary'}.issubset(core['required_checks'])):
            raise AssertionError('Necessary pre-refactor lost the original behavior boundary')
        if not any(dep['upstream_task']=='CORE' and dep['condition_kind']=='verification_passed' for dep in report['dependencies']):
            raise AssertionError('Report lost its actual upstream task-verification condition')
        if mean_required and 'test_report_mean.py' in self.allowed and not any(
                check['argv'][1:]==['-B','-m','unittest','test_report_mean','-v'] for check in report['checks_basis']):
            raise AssertionError('New mean result lacks its actual required task check')
        document=json.loads(connection.execute('SELECT content FROM blobs WHERE digest=?',(revision['plan_digest'],)).fetchone()[0])
        if not document['spec'].get('broad_migration') or not document['spec'].get('integration_boundary'):
            raise AssertionError('Broad interface migration lost its final integration boundary')
        checks=json.loads(revision['checks_json'])
        if not any(c['id']=='integration' and c['argv'][1:]==['-B','-m','unittest','discover','-v'] for c in checks):
            raise AssertionError('Final independent discovery command was weakened or omitted')
        for check in core['checks_basis']+report['checks_basis']:
            if check['id'] in CHECK_MODULES and check['argv'][1:]!=['-B','-m','unittest',CHECK_MODULES[check['id']],'-v']:
                raise AssertionError('A declared independent task command was changed')
        return change,revision,tasks,definitions

    def pending_mean(self, connection, current, revision, tasks):
        from evolve_core.package import canonical, digest
        fresh=[row for identity,row in current['phase_runs'].items() if identity not in self.before_rows['phase_runs']]
        updates=[row for row in fresh if row['action']=='update' and row['status']=='completed']
        if (len(updates)!=1 or any(row['action'] not in ('init','update') for row in fresh)
                or current['tasks']!=self.before_rows['tasks'] or current['plan_revisions']!=self.before_rows['plan_revisions']
                or current['evidence']!=self.before_rows['evidence'] or current['verifications']!=self.before_rows['verifications']):
            raise AssertionError('Pending mean candidate changed effective work or executed checks')
        result=json.loads(updates[0]['result_json']); candidate=result.get('candidate',{})
        if (result.get('outcome')!='scope_confirmation_required' or candidate.get('from_revision_id')!=revision['id']
                or digest(canonical(candidate))!=result.get('candidate_digest')
                or json.loads(updates[0]['input_json'])['request']['input'].get('approval')):
            raise AssertionError('No actual unapproved candidate bound to the preserved revision')
        document=candidate['document']; proposed={task['local_key']:task for task in document['tasks']}
        if set(proposed)!={'CORE','REPORT'} or set(document['scope'])!=PRODUCTION:
            raise AssertionError('Pending mean candidate changed the two-file task boundary')
        if (candidate['tasks'].get('CORE')!='same_definition' or candidate['tasks'].get('REPORT')!='changed_or_new'
                or candidate['task_definition_digests'].get('CORE')!=tasks['CORE']['definition_digest']):
            raise AssertionError('Pending mean candidate changed the unaffected CORE definition')
        report=proposed['REPORT']; checks={c['id']:c for c in candidate['resolved_basis']['checks']}
        if (set(report['scope'])!={'report.py'} or not {'report','mean'}.issubset(report['required_checks'])
                or 'test_report_mean.py' not in report['context_paths'] or 'mean' not in checks
                or checks['mean']['argv'][1:]!=['-B','-m','unittest','test_report_mean','-v']
                or not any(d['upstream_task']=='CORE' and d['condition_kind']=='verification_passed' for d in report['dependencies'])
                or checks['integration']['argv'][1:]!=['-B','-m','unittest','discover','-v']):
            raise AssertionError('Pending mean result lacks its actual required task check')
        old=json.loads(connection.execute('SELECT content FROM blobs WHERE digest=?',(revision['plan_digest'],)).fetchone()[0])
        retained={a['key']:a['text'] for a in document['acceptance']}
        added=set(retained)-{a['key'] for a in old['acceptance']}
        if (not added or not added.issubset(report['acceptance'])
                or any(retained.get(a['key'])!=a['text'] for a in old['acceptance'])
                or candidate['removed']['scope'] or candidate['removed']['acceptance'] or candidate['rewritten_acceptance']
                or candidate['removed_tasks'] or candidate['removed_analysis']):
            raise AssertionError('Pending mean candidate lost original acceptance or its new result')
        if not document['spec']['broad_migration'] or not document['spec']['integration_boundary']:
            raise AssertionError('Pending mean candidate lost final integration boundary')
        self.pending_revision={'candidate_digest':result['candidate_digest'],'document':document}
        self.core_digest,self.core_result=tasks['CORE']['definition_digest'],tasks['CORE']['result_json']

    def independent(self, case):
        process=subprocess.run([sys.executable,'-B','-m','unittest','discover','-v'],cwd=self.project,
            text=True,capture_output=True,timeout=30)
        (self.evidence/(case+'-independent-check.json')).write_text(json.dumps({'exit_code':process.returncode,
            'stdout':process.stdout,'stderr':process.stderr},ensure_ascii=False,indent=2))
        if process.returncode: raise AssertionError('Parent execution of original independent tests failed')

    def original_proof(self, connection, core):
        from evolve_core.preservation import before_fact
        from evolve_core.structured import current_tasks, dependency_basis
        saved=json.loads(core['result_json']) if core['result_json'] else {}
        proof=saved.get('preservation',{}).get('before')
        definition=json.loads(core['definition_json'])
        peers=current_tasks(connection,core['change_id'],core['revision_id'])
        fact=before_fact(connection,self.project,core,definition,proof,dependency_basis(connection,core,peers))
        expected=hashlib.sha256(self.scope['first_files']['arithmetic.py'].encode()).hexdigest()
        if fact['before_snapshot']['scope']['arithmetic.py']!=expected:
            raise AssertionError('Pre-refactor evidence was manufactured on already modified code')
        if self.proof is not None and self.proof!=proof:
            raise AssertionError('Revision or continuation replaced the original behavior proof')
        self.proof=proof
        return saved

    def after(self, case):
        from evolve_core.reading import history_snapshot
        current=self.rows(); files=self.files()
        if self.installed_files()!=self.installation_files:raise AssertionError('Native case changed the complete installed source/cache')
        if set(files)-self.allowed or self.settings()!=self.host_settings:
            raise AssertionError('Model changed prepared host settings or left unauthorized business files')
        for name,content in {**self.scope['first_files'],**self.scope['second_files']}.items():
            if name.startswith('test_') and name in self.allowed and files.get(name)!=content.encode():
                raise AssertionError('An original independent literal test was changed or removed')
        if case in ('propose','cosmetic_revision','local_revision','verify') and files!=self.before_files:
            raise AssertionError('The requested proposal/revision/verification phase changed business bytes')
        if self.before_rows:
            for table in ('phase_runs','verifications','events','evidence'):
                for identity,row in self.before_rows[table].items():
                    if current[table].get(identity)!=row:
                        raise AssertionError('Case rewrote earlier immutable '+table+' facts')
        with history_snapshot(self.project) as (connection,_):
            self.quiet(connection)
            same_revision=(self.before_rows and list(self.before_rows['changes'].values())[0]['current_revision']==
                list(current['changes'].values())[0]['current_revision'])
            pending=case=='local_revision' and same_revision
            change,revision,tasks,definitions=self.work(connection,mean_required=not pending)
            core,report=tasks['CORE'],tasks['REPORT']
            whole=[r for r in current['verifications'].values() if r['revision_id']==revision['id'] and json.loads(r['items_json']).get('task_id') is None]
            if case=='propose':
                if (revision['accepted_event_id'] is not None or any(t['state']!='todo' or t['result_json'] for t in tasks.values())
                        or current['verifications'] or any(r['action']=='apply' for r in current['phase_runs'].values())):
                    raise AssertionError('Proposal implicitly accepted, implemented or verified work')
            elif case=='refactor_pause':
                if revision['accepted_event_id'] is None or core['state']!='in_progress' or report['state']!='todo' or current['verifications']:
                    raise AssertionError('File pause was confused with implementation or acceptance completion')
                if files['arithmetic.py']==self.scope['first_files']['arithmetic.py'].encode() or files['report.py']!=self.before_files['report.py']:
                    raise AssertionError('Pause must contain only the actual necessary CORE file segment')
                partial=[r for r in current['phase_runs'].values() if r['action']=='apply' and json.loads(r['result_json']).get('checks')=='not_run']
                if len(partial)!=1 or partial[0]['status']!='completed' or json.loads(partial[0]['result_json']).get('outcome')!='partial':
                    raise AssertionError('No safely ended no-post-check partial source')
                if any(e['source_run_id']==partial[0]['id'] for e in current['evidence'].values()):
                    raise AssertionError('No-check file pause executed recorded checks')
                self.partial=partial[0]
                self.original_proof(connection,core)
            elif case in ('cosmetic_revision','local_revision'):
                previous=list(self.before_rows['changes'].values())[0]
                if pending:
                    self.pending_mean(connection,current,revision,tasks)
                elif previous['current_revision']==revision['id']: raise AssertionError('No actual new REV was saved')
                for identity,row in self.before_rows['tasks'].items():
                    if current['tasks'].get(identity)!=row: raise AssertionError('Revision overwrote historical Task state or result')
                if current['evidence']!=self.before_rows['evidence'] or current['verifications']!=self.before_rows['verifications']:
                    raise AssertionError('A revision ran checks or cloned verification records')
                old_tasks={json.loads(t['definition_json'])['local_key']:t for t in self.before_rows['tasks'].values() if t['revision_id']==previous['current_revision']}
                if core['definition_digest']!=old_tasks['CORE']['definition_digest'] or core['result_json']!=old_tasks['CORE']['result_json']:
                    raise AssertionError('Unchanged CORE lost its applicable result')
                self.original_proof(connection,core)
                if case=='cosmetic_revision':
                    if revision['accepted_event_id'] is None or core['state']!='in_progress' or report['state']!='todo':
                        raise AssertionError('Cosmetic revision lost accepted meaning or partial progress')
                    if any(tasks[k]['definition_digest']!=old_tasks[k]['definition_digest'] for k in tasks):
                        raise AssertionError('Cosmetic revision changed actual task meaning')
                elif not pending:
                    if (core['state']!='done' or report['state']!='todo' or report['definition_digest']==old_tasks['REPORT']['definition_digest']
                            or revision['accepted_event_id'] is not None):
                        raise AssertionError('Local revision did not reopen just the changed result as an unaccepted draft')
                    if len(json.loads(revision['acceptance_json']))<=len(json.loads(self.before_rows['plan_revisions'][previous['current_revision']]['acceptance_json'])):
                        raise AssertionError('Local revision omitted its new required acceptance condition')
                    self.core_digest,self.core_result=core['definition_digest'],core['result_json']
            elif case in ('continue','finish_revision'):
                if any(t['state']!='done' for t in tasks.values()) or not whole or whole[-1]['status']!='passed':
                    raise AssertionError('Actual required results and current whole verification did not all pass')
                saved=self.original_proof(connection,core)
                if saved['preservation'].get('status')!='passed': raise AssertionError('No actual original before/after behavior pair')
                if case=='continue':
                    if change['state']=='archived': raise AssertionError('Continuation crossed the requested pre-archive boundary')
                    continued={identity for identity,row in current['phase_runs'].items() if identity not in self.before_rows['phase_runs']
                        and row['action']=='apply' and row['status']=='completed'
                        and json.loads(row['result_json']).get('task_id')==core['id']
                        and json.loads(row['result_json']).get('outcome') in ('implemented','checks_not_passed')}
                    if not any(row['run_id'] in continued for row in connection.execute(
                            "SELECT run_id FROM source_runs WHERE source_run_id=? AND purpose='normal_continuation'",(self.partial['id'],))):
                        raise AssertionError('Fresh session ignored the actual partial continuation source')
                else:
                    if (change['state']!='archived' or core['definition_digest']!=self.core_digest or core['result_json']!=self.core_result
                            or files['arithmetic.py']!=self.before_files['arithmetic.py']):
                        raise AssertionError('Local completion changed CORE or failed to archive the actual new requirement')
                    if self.pending_revision:
                        document=json.loads(connection.execute('SELECT content FROM blobs WHERE digest=?',(revision['plan_digest'],)).fetchone()[0])
                        if document!=self.pending_revision['document'] or revision['accepted_event_id'] is None:
                            raise AssertionError('Completion did not accept the exact pending mean candidate')
                self.independent(case)
            elif case=='verify':
                if current['changes']!=self.before_rows['changes'] or current['tasks']!=self.before_rows['tasks']:
                    raise AssertionError('Verification changed completed implementation history')
                fresh=[row for identity,row in current['verifications'].items() if identity not in self.before_rows['verifications']]
                if not fresh or not any(row['status'] in ('failed','blocked') for row in fresh):
                    raise AssertionError('Current external regression was not recorded as actual failed/blocked verification')
        return {'case':case,'business_files':sorted(files),'change_id':change['id'],'revision_id':revision['id'],
            'task_states':{key:t['state'] for key,t in tasks.items()},'original_proof':self.proof,'parent_checks':'passed',
            'pending_revision_candidate':({'candidate_digest':self.pending_revision['candidate_digest'],
                'state':'awaiting_specific_acceptance'} if case=='local_revision' and self.pending_revision else None),
            'model_semantic_review':'pending; actual native trace and claims need separate review'}
