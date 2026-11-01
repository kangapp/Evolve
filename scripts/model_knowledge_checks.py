"""Concrete IMP-007 native scope and source-bound parent observations, no model transport."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tomllib
from model_session_checks import SessionChecks

GUIDE = '# 项目约定\n\n当前标签：待定。\n\n审查约定：尚无。\n'
RULE = '检查当前标签对应阶段的独立字面量测试，并注明范围。'
GUIDE_A = GUIDE.replace('待定。', 'A。').replace('尚无。', RULE)
EXTERNAL = '\n外部范围：仅此临时项目。\n'
NOTE_A = '\n后续说明：标签 A。\n'
NOTE_B = '\n后续说明：标签 B。\n'
GUIDE_B = (GUIDE_A + EXTERNAL).replace('当前标签：A。', '当前标签：B。') + NOTE_B
FIRST_FILES = {'policy.py': 'POLICY = "unset"\n', 'guide.md': GUIDE}
for value in ('A', 'B'):
    FIRST_FILES['test_policy_' + value.lower() + '.py'] = ('import unittest\nfrom policy import POLICY\n'
        'class Policy' + value + '(unittest.TestCase):\n    def test_independent_literal(self):\n        self.assertEqual(POLICY, ' + repr(value) + ')\n')
PROMPTS = {
    'baseline': ('使用 Evolve 接入当前临时项目；guide.md 现有全文为“# 项目约定”、空行、“当前标签：待定。”、空行、'
        '“审查约定：尚无。”，保留其实际换行。本轮明确批准的初次正式全文就是这份已存在原文，不额外改正文。'
        '它是本次必需文档成果：先呈现并保存短方案，responsible_action=init，scope 仅 guide.md，明确内容 AC。'
        '按结构化初次候选、实际内容检查、具体决定、init 实际应用、verify 目标验收和封存完成。'
        '登记 policy_a、policy_b 两个真实检查，argv 分别为 python3 -B -m unittest test_policy_a -v 和 '
        'python3 -B -m unittest test_policy_b -v，cwd 为项目根；本轮文档任务不运行它们。'
        '不改 policy.py 或两个测试，不把接入本身称为初次文档已交付，不预填内容检查或验收。'),
    'deliver_a': ('使用 Evolve 呈现并保存新复杂方案“标签 A 与正式约定”，本轮明确接受符合下述边界的完整方案。'
        '新 Change 的任务键固定 CODE、SPEC、RULES：CODE 仅 policy.py，目标 POLICY 等于字符串 A，必需检查 policy_a；'
        'SPEC 仅 guide.md，由 sync 将“当前标签：待定。”改为“当前标签：A。”；RULES 也仅 guide.md，由 learn 将'
        '“审查约定：尚无。”改为“审查约定：检查当前标签对应阶段的独立字面量测试，并注明范围。”。'
        '每项有自己的 AC；SPEC 依赖 CODE 的 verification_passed，RULES 依赖 SPEC 的 verification_passed。'
        '完整 spec 给问题、目标、边界、行为、约束、取舍、测试决定及真实依赖，最终必需检查 policy_a。'
        '只实施 CODE，先实际观察初始 policy_a 失败，再经 apply 修正、实际检查与独立 Task 验收。'
        '原检查文件只读；policy_b 是以后 B 契约的独立判据，本轮未要求通过它。'
        '根据 CODE 的实际修改和检查结果记录 observed 原因的项目候选经验，主题固定“标签交付核查”，建议为上述规则文本；'
        '说明范围只含此临时项目的标签交付，保留真实来源证据和局限，不声称因果收益。'
        '本轮不创建／批准正式知识候选，不实施 SPEC／RULES，不整体验收或封存该 Change。'),
    'candidates': ('从 Evolve 档案恢复“标签 A 与正式约定”，本轮仅保存并实际检查三项 guide.md 候选，不批准或应用。'
        '第一项 topic=policy-spec-a，由 sync 仅把“当前标签：待定。”改成“当前标签：A。”，delivery=required 绑定 SPEC '
        '及其真实 AC，并引用 CODE 的真实适用 Task 验收为实现依据。第二项 topic=label-review-rule，由 learn.promote '
        'stage=propose 仅把“审查约定：尚无。”改为“审查约定：检查当前标签对应阶段的独立字面量测试，并注明范围。”，'
        'delivery=required 绑定 RULES；读取“标签交付核查”经验及实际证据，绑定准确经验、当前状态、全部已知反例和限定范围。'
        '第三项 topic=policy-note，由 sync 在当前原 guide.md 末尾追加空行及“后续说明：标签 A。”，delivery=followup '
        '关联该 A Change，引用 CODE 的真实适用验收。本项以后集中决定。'
        '三项都呈现各自完整正文、具体内容判据、原 UTF-8 字节范围和不同 semantic_target；均基于此刻真实初次正式版本。'
        '保存实际内容观察和明确三项批次，不改 guide.md 或业务，不将候选检查冒充实际目标验收。'),
    'decisions': ('本轮仅记录我对上一轮实际呈现的准确三项候选的具体决定：批准 policy-spec-a 中待定→A 的狭义差异；'
        '批准 label-review-rule 中尚无→“检查当前标签对应阶段的独立字面量测试，并注明范围。”的狭义差异；'
        '延期 policy-note 中“后续说明：标签 A。”，原因是稍后再决定说明。'
        '从档案读取实际完整正文、版本、基线和内容检查，逐项绑定此处真实决定来源，保存明确三项批次；'
        '不改变原候选含义，不转移或伪造批准，不写正式文件、实施、验收或封存。'),
    'finish_a': ('从档案恢复已经批准的 policy-spec-a 与 label-review-rule，以及 CODE 的实际成果。'
        '按具体批准由 sync 完成 SPEC、独立验收 SPEC，再由 learn 完成 RULES；同文件沿真实应用链保留前项批准，'
        '实际阅读组合后的完整正文再提供具名组成观察。只应用已批准子集，policy-note 仍延期。'
        '完成必需 Task、应用后验收、policy_a 真实检查和整项双维验收，真实通过后封存“标签 A 与正式约定”。'
        'CODE 原结果、经验、具体决定及各真实应用来源均保持；不把候选检查或 Task 通过当整项通过。'),
    'adopt_external': ('控制侧已在 guide.md 末尾实际追加空行及“外部范围：仅此临时项目。”，其他已批准含义保持。'
        '使用 Evolve 先呈现原正式全文与当前外部全文；本轮我具体批准仅采纳这份实际外部全文及该新增范围，不额外改写。'
        '将其作为一个新必需正式文档成果，responsible_action=sync，绑定实际 Task／AC。'
        '具体 adoption 候选绑定原 artifact 版本／摘要、真实外部字节及实际观察，修改者未知，edits 只声明该末尾追加。'
        '实际检查、记录具体决定、登记既有字节为正式版本，保持文件修改时间，不重写文件；目标验收通过后封存。'
        '旧 A、规则、延期 policy-note 及其原决定保持，不隐式批准旧说明。'),
    'deliver_b': ('使用 Evolve 建新工作“标签 B”，先呈现短方案，本轮明确接受并授权仅将 policy.py 的 POLICY 改为字符串 B。'
        '当前契约使用预置的 policy_b 检查与独立字面量 B 预期；policy_a 保留为旧 A 历史判据，不修改两个测试，'
        '不能把旧 A passed 冒充 B 当前通过。实际实施、运行 policy_b 并完成新的双维验收。'
        '随后仅提出新的 topic=policy-note 正式候选：以此刻实际已批准 guide.md 为基线，将“当前标签：A。”改为'
        '“当前标签：B。”，并在末尾追加空行及“后续说明：标签 B。”，规则和外部范围保持。'
        'delivery=followup 关联新 B Change，引用 B 真实验收；准确 edits 声明两个独立范围。'
        '旧 A 同主题延期说明被本次明确新行为和内容替代，保留其原文、延期决定与后继关系。'
        '保存并实际检查新候选，本轮不批准或应用它，也不封存 B。'),
    'finish_b': ('从档案恢复 B 实际成果与新的 policy-note 完整候选。这里具体批准该新候选中 A→B 的标签差异及末尾'
        '“后续说明：标签 B。”；规则、外部范围与其他已批准含义保持。'
        '绑定准确新版本、原正式基线和实际决定后由 sync 应用，再验收实际目标。'
        '正式文档改变后重新核对 B 当前现场，执行 policy_b 并取得新的整体验收，随后封存 B。'
        '查询已归档 A 的旧说明及其后继 B，保留旧延期决定和历史通过；不恢复或批准旧标签 A 说明。'),
    'verify': ('控制侧已仅将 guide.md 中“外部范围：仅此临时项目。”改为“外部范围：未知范围。”，尚未批准该编辑。'
        '使用 Evolve 只验收最后 B policy-note 实际 application 的当前正式内容，追加真实 blocked／failed 观察。'
        '保留原应用、原 passed 验收与全部既有工作项的封存终态，不修复、采纳外部内容或修改业务／测试。'
        '分别说明历史结果、当前不确认及需要的下一步；旧源代码判据通过不表示当前正式全文已确认。'),
}


def scope_for(manifest, host, model, transport):
    required={'init.baseline.propose','init.baseline.apply','sync.propose','sync.check','sync.review','sync.apply','learn.promote',
              'verify.knowledge','verify.run','propose.create','archive.close','learn.record','learn.search'}
    if (manifest['schema_version'],manifest['protocol_version']) not in ((4,10),(4,11),(4,12),(4,13),(4,14),(4,15),(4,16)) or not required.issubset(manifest['available_methods']):
        raise ValueError('Knowledge acceptance needs the complete actual schema4/protocol10-to-14 runtime and owner methods')
    if host=='claude' and model!='MiniMax-M3.1-Flash':
        raise ValueError('Reviewed Claude knowledge scope uses only process-local MiniMax-M3.1-Flash')
    helpers=(Path(__file__),transport,Path(__file__).with_name('model_session_checks.py'),Path(__file__).with_name('verify_hosts.py'))
    body={'slice':'IMP-007','host':host,'claude_model':model,'package_version':manifest['package_version'],'content_digest':manifest['content_digest'],
          'schema_version':4,'protocol_version':manifest['protocol_version'],'model_selection':model if host=='claude' else 'model/list isDefault at dispatch',
          'first_files':FIRST_FILES,'business_write_paths':['policy.py','guide.md'],'read_only_tests':['test_policy_a.py','test_policy_b.py'],
          'cases':PROMPTS,'fresh_conversation_per_case':True,'maximum_sessions':len(PROMPTS),
          'installation_layout':'.agents/evolve-acceptance/{profile,installed-source} within the disposable business root; complete package immutable',
          'limits':['Only this disposable project, Evolve records and actual installed complete plugin resources',
                    'Parent edits only the two fixed external guide observations before their named sessions',
                    'Only exact formal texts/differences explicitly approved in the named user case; deferred note stays deferred until superseded',
                    'No personal config/credential changes, external apps, nested agents, commits, publishing or deployment',
                    'Normal host permissions; stop host immediately on quota, permission, transport or parent-check failure; no automatic retry or model/account replacement'],
          'runner_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers}}
    return {**body,'scope_digest':hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()}


class KnowledgeChecks(SessionChecks):
    def __init__(self, project, scope, evidence, *, package, registered_root=None):
        self.project,self.scope,self.evidence=Path(project),scope,Path(evidence)
        self.packages=tuple(dict.fromkeys(Path(p).resolve() for p in (package,registered_root or package)))
        for path in self.packages:path.relative_to(self.project.resolve())
        self.host_settings=self.settings();self.package_files=self.package_snapshot()
        self.before_rows=self.before_files=None
        self.a_id=self.b_id=self.old_note=None
        self.next_case=0;self.running_case=None
        self.tool_config=None
        self.adoption_mtime=self.registered_before_adoption=None

    def package_snapshot(self):
        from evolve_core.package import check_package
        result={}
        for package in self.packages:
            manifest=check_package(package)
            if manifest['content_digest']!=self.scope['content_digest']:
                raise AssertionError('Actual installed complete package differs from the reviewed scope')
            for p in package.rglob('*'):
                if p.is_symlink():raise AssertionError('Installed package cannot acquire a symbolic alias')
                if p.is_file():result[p.relative_to(self.project).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
        return result

    def files(self):
        ignored={'evolve','.evolve-local','.codex','.claude','.agents','__pycache__','.pytest_cache'}
        result={}
        for p in self.project.rglob('*'):
            if set(p.relative_to(self.project).parts)&ignored:continue
            if p.is_symlink():raise AssertionError('Business fixture cannot acquire a symbolic alias')
            if p.is_file():result[p.relative_to(self.project).as_posix()]=p.read_bytes()
        return result

    def rows(self):
        from evolve_core.reading import history_snapshot
        if not (self.project/'evolve/history.db').exists():return {}
        with history_snapshot(self.project) as (c,_):
            result={table:{r['id']:dict(r) for r in c.execute('SELECT * FROM '+table)} for table in
                ('changes','tasks','verifications','phase_runs','knowledge_proposals','spec_applications','artifact_versions','events','evidence')}
            result['rule_bindings']={r['application_id']:dict(r) for r in c.execute('SELECT * FROM rule_bindings')}
            result['claims']={r['resource']:dict(r) for r in c.execute('SELECT * FROM resource_claims')}
            return result

    def literal(self, value):
        p=subprocess.run([sys.executable,'-B','-m','unittest','test_policy_'+value.lower(),'-v'],cwd=self.project,
                         text=True,capture_output=True,timeout=20)
        return {'argv':[sys.executable,'-B','-m','unittest','test_policy_'+value.lower(),'-v'],
                'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

    def before(self, case, *, missing_tests=False):
        if self.running_case or self.next_case>=len(PROMPTS) or case!=list(PROMPTS)[self.next_case] or missing_tests:
            raise AssertionError('Knowledge cases have a fixed reviewed order and two read-only tests')
        self.running_case=case
        if case=='adopt_external':
            if (self.project/'guide.md').read_text()!=GUIDE_A:raise AssertionError('No actual completed A guide precedes external observation')
            from evolve_core.reading import current_state
            self.registered_before_adoption=current_state(self.project)['knowledge_refs'][0]['artifact_version_id']
            (self.project/'guide.md').write_text(GUIDE_A+EXTERNAL)
            self.adoption_mtime=(self.project/'guide.md').stat().st_mtime_ns
        elif case=='verify':
            if (self.project/'guide.md').read_text()!=GUIDE_B:raise AssertionError('No actual completed B guide precedes verify-only external drift')
            (self.project/'guide.md').write_text(GUIDE_B.replace('外部范围：仅此临时项目。','外部范围：未知范围。'))
        self.before_rows=self.rows();self.before_files=self.files()
        if case=='deliver_a':
            observed=self.literal('A')
            if observed['exit_code']==0:raise AssertionError('The initial A independent literal must actually fail')
            (self.evidence/'parent-original-policy-a.json').write_text(json.dumps(observed,ensure_ascii=False,indent=2))

    def proposal(self, rows, topic, *, owner=None):
        from evolve_core.knowledge_proposals import metadata
        values=[r for r in rows['knowledge_proposals'].values() if metadata(r) and metadata(r)['topic']==topic and (not owner or r['owner_skill']==owner)]
        if not values:raise AssertionError('No actual candidate for '+topic)
        return values[-1]

    def actual(self, rows, proposal):
        from evolve_core.formal import application_source
        from evolve_core.reading import history_snapshot
        values=[r for r in rows['spec_applications'].values() if r['proposal_id']==proposal['id']]
        if len(values)!=1:raise AssertionError('Candidate needs exactly one actual application')
        with history_snapshot(self.project) as (c,_):
            facts=application_source(c,values[0])
        if not facts:raise AssertionError('Application must have a sealed actual owner/source, not a fabricated candidate result')
        return values[0],facts

    def work(self, rows, code=None, *, expected_check=None):
        from evolve_core.reading import history_snapshot
        from evolve_core.work import verification_source
        from evolve_core.revisions import eligible_verifications
        if code:
            change=rows['changes'][code]
        else:
            matches=[r for r in rows['changes'].values() if r['complexity']=='complex']
            if len(matches)!=1:raise AssertionError('Exactly one actual complex A work is required')
            change=matches[0]
        tasks=[r for r in rows['tasks'].values() if r['revision_id']==change['current_revision']]
        with history_snapshot(self.project) as (c,_):
            whole=[v for v in eligible_verifications(c,change['id'],change['current_revision']) if json.loads(v['items_json']).get('task_id') is None]
            passed=bool(whole and whole[0]['status']=='passed' and verification_source(c,whole[0]))
            if expected_check:
                passed &= bool(whole and any(item['check_id']==expected_check and item['status']=='passed' and item['evidence_id']
                    for item in json.loads(whole[0]['items_json']).get('checks',[])))
        return change,tasks,passed

    def after(self, case):
        from evolve_core.knowledge_proposals import metadata,latest_check,source_facts
        from evolve_core.reading import history_snapshot,current_state
        from evolve_core.learning import catalog
        from evolve_core.patches import effect_state
        if self.running_case!=case:raise AssertionError('Parent observation must follow its actual declared before boundary')
        current=self.rows();files=self.files()
        if self.settings()!=self.host_settings or self.package_snapshot()!=self.package_files:
            raise AssertionError('Model changed isolated host settings or actual installed package resources')
        config=(self.project/'evolve/config.toml').read_bytes()
        if case=='baseline':
            checks={r['id']:r for r in tomllib.loads(config.decode()).get('verification',{}).get('checks',[])}
            if set(checks)!={'policy_a','policy_b'}:raise AssertionError('Both exact declared independent phase checks must be registered')
            for key,check in checks.items():
                argv=check['argv']
                if len(argv)!=6 or argv[1:]!=['-B','-m','unittest','test_'+key,'-v'] or not Path(argv[0]).name.startswith('python') or check['cwd']!='.':
                    raise AssertionError('Registered command does not execute the original independent literal module')
            self.tool_config=config
        elif config!=self.tool_config:
            raise AssertionError('Later native cases changed the approved check configuration')
        if set(files)!=set(FIRST_FILES):raise AssertionError('Unexpected business/request files outside the declared records area')
        for name in ('test_policy_a.py','test_policy_b.py'):
            if files[name]!=FIRST_FILES[name].encode():raise AssertionError('An independent read-only test changed')
        if case not in ('deliver_a','deliver_b') and files['policy.py']!=self.before_files['policy.py']:
            raise AssertionError('A knowledge/read-only stage changed business policy')
        if case not in ('finish_a','adopt_external','finish_b') and files['guide.md']!=self.before_files['guide.md']:
            raise AssertionError('Candidate/decision/verify stage changed formal text')
        for table in ('phase_runs','verifications','artifact_versions','events','evidence'):
            for key,row in self.before_rows.get(table,{}).items():
                if current.get(table,{}).get(key)!=row:raise AssertionError('Historical '+table+' record changed')
        for key,row in self.before_rows.get('knowledge_proposals',{}).items():
            now=current['knowledge_proposals'].get(key)
            fixed=('version','owner_skill','target_kind','target_path','expected_digest','candidate_digest','source_json','created_run_id')
            if not now or any(now[k]!=row[k] for k in fixed) or (row['approved_event_id'] and now['approved_event_id']!=row['approved_event_id']):
                raise AssertionError('An original proposal/version/approval was rewritten')
        if current.get('claims') or any(r['status']=='started' for r in current.get('phase_runs',{}).values()):
            raise AssertionError('Native case left an unfinished run or resource claim')
        with history_snapshot(self.project) as (c,_):
            for run in current['phase_runs'].values():
                if run['package_digest']!=self.scope['content_digest'] or run['protocol_version']!=self.scope['protocol_version']:
                    raise AssertionError('Actual runtime facts came from another package or protocol')
                if run['action']=='apply' and run['method']!='implement':raise AssertionError('External side effects are outside this scope')
            if case=='baseline':
                initials=[r for r in current['knowledge_proposals'].values() if r['owner_skill']=='evolve-init' and metadata(r)]
                if len(initials)!=1 or not self.actual(current,initials[0])[0]:raise AssertionError('Required typed init application missing')
                changes=list(current['changes'].values())
                if len(changes)!=1 or changes[0]['state']!='archived' or files['guide.md']!=GUIDE.encode():raise AssertionError('Initial required formal result not actually closed')
            elif case=='deliver_a':
                change,tasks,_=self.work(current);self.a_id=change['id']
                definitions={json.loads(t['definition_json'])['local_key']:(t,json.loads(t['definition_json'])) for t in tasks}
                if set(definitions)!={'CODE','SPEC','RULES'}:raise AssertionError('A plan did not preserve all three declared owner Tasks')
                for key,owner in (('CODE','apply'),('SPEC','sync'),('RULES','learn')):
                    task,definition=definitions[key]
                    if definition['responsible_action']!=owner or definition['scope']!=(['policy.py'] if key=='CODE' else ['guide.md']):raise AssertionError('Wrong actual owner or Task scope')
                    if task['state']!=('done' if key=='CODE' else 'todo'):raise AssertionError('A CODE-only stage completed or skipped required formal work')
                    if key=='CODE' and definition['required_checks']!=['policy_a']:raise AssertionError('CODE requires the actual independent A literal command')
                entries=[item for item in catalog(c).values() if item['experience']['topic']=='标签交付核查']
                if change['state']=='archived' or len(entries)!=1 or entries[0]['experience']['cause']['confidence']!='observed':raise AssertionError('A stage needs scoped observed experience, while whole formal work remains open')
                task_ver=[v for v in current['verifications'].values() if json.loads(v['items_json']).get('task_id')==definitions['CODE'][0]['id'] and v['status']=='passed']
                if (not task_ver or not any(check['check_id']=='policy_a' and check['status']=='passed' for v in task_ver for check in json.loads(v['items_json'])['checks'])
                        or not any(f['evidence'] and f['work']['change_id']==change['id'] and f['work']['definition_digest']==definitions['CODE'][0]['definition_digest'] for f in entries[0]['sources'])):raise AssertionError('No actual CODE acceptance/work evidence supports the experience')
            elif case in ('candidates','decisions'):
                expected={'policy-spec-a':('evolve-archive',GUIDE.replace('待定。','A。'),'required'),
                          'label-review-rule':('evolve-learn',GUIDE.replace('尚无。',RULE),'required'),
                          'policy-note':('evolve-archive',GUIDE+NOTE_A,'followup')}
                for topic,(owner,text,role) in expected.items():
                    p=self.proposal(current,topic,owner=owner);value=metadata(p)
                    body=c.execute('SELECT content FROM blobs WHERE digest=?',(p['candidate_digest'],)).fetchone()[0].decode()
                    if body!=text or not value['edits'] or value['delivery']['role']!=role or value['delivery']['change_id']!=self.a_id:
                        raise AssertionError('Candidate meaning, exact scope or actual delivery relation differs')
                    if source_facts(c,p['created_run_id']) is None:raise AssertionError('Candidate source was not safely finalized')
                    check=latest_check(c,p)
                    if not check or check['source_pending'] or check['recorded_status']!='passed':raise AssertionError('Specific content check missing')
                    expected_state='proposed' if case=='candidates' else 'deferred' if topic=='policy-note' else 'approved'
                    if p['state']!=expected_state or p['applied_operation_id']:raise AssertionError('Candidate/decision stage applied or misclassified a decision')
                    if topic=='policy-note':self.old_note=p['id']
            elif case=='finish_a':
                change,tasks,passed=self.work(current,self.a_id,expected_check='policy_a')
                if change['state']!='archived' or not passed or any(t['state']!='done' for t in tasks) or files['guide.md']!=GUIDE_A.encode():raise AssertionError('All actual A Task/whole results must precede archive')
                for topic in ('policy-spec-a','label-review-rule'):self.actual(current,self.proposal(current,topic))
                if len(current['rule_bindings'])!=1 or current['knowledge_proposals'][self.old_note]['state']!='deferred':raise AssertionError('Missing actual rule binding or deferred subset was implicitly accepted')
            elif case=='adopt_external':
                new=[a for key,a in current['spec_applications'].items() if key not in self.before_rows['spec_applications']]
                if len(new)!=1:raise AssertionError('One actual external registration required')
                p=current['knowledge_proposals'][new[0]['proposal_id']];value=metadata(p);_,facts=self.actual(current,p)
                if (not value.get('adoption') or value['adoption']['formal_version_id']!=self.registered_before_adoption
                        or facts.get('adopted_external_bytes') is not True or facts.get('file_bytes_written') is not False
                        or files['guide.md']!=(GUIDE_A+EXTERNAL).encode() or (self.project/'guide.md').stat().st_mtime_ns!=self.adoption_mtime):raise AssertionError('Adoption rewrote bytes or skipped exact observed formal authority')
                change,_,passed=self.work(current,value['delivery']['change_id'])
                if change['state']!='archived' or not passed:raise AssertionError('Required adopted target was not actually accepted and closed')
            elif case=='deliver_b':
                old=current['knowledge_proposals'][self.old_note];new=self.proposal(current,'policy-note');value=metadata(new)
                if old['state']!='superseded' or value['supersedes']!=old['id'] or new['state']!='proposed' or new['applied_operation_id']:raise AssertionError('B did not preserve and explicitly supersede A pending proposal')
                body=c.execute('SELECT content FROM blobs WHERE digest=?',(new['candidate_digest'],)).fetchone()[0].decode()
                if body!=GUIDE_B or not value['edits'] or len(value['edits'])!=2 or not value.get('implementation_basis'):raise AssertionError('B actual content/scope/implementation basis missing')
                self.b_id=value['delivery']['change_id'];change,tasks,passed=self.work(current,self.b_id,expected_check='policy_b')
                if change['state']=='archived' or not passed or any(t['state']!='done' for t in tasks):raise AssertionError('B must have real implementation/VER but stop before formal acceptance and closure')
            elif case=='finish_b':
                change,_,passed=self.work(current,self.b_id,expected_check='policy_b');p=self.proposal(current,'policy-note');self.actual(current,p)
                if change['state']!='archived' or not passed or files['guide.md']!=GUIDE_B.encode():raise AssertionError('B actual target and fresh whole acceptance did not precede closure')
                old=current['knowledge_proposals'][self.old_note]
                nav=current_state(self.project,self.a_id)['changes'][0]['knowledge_proposal_refs']
                if old['state']!='superseded' or not any(r['proposal_id']==old['id'] and any(s['proposal_id']==p['id'] for s in r['superseded_by']) for r in nav):raise AssertionError('Archived A lost exact pending/successor navigation')
            elif case=='verify':
                if any(current[table]!=self.before_rows[table] for table in ('changes','tasks','rule_bindings')):raise AssertionError('Verify-only changed implementation/authority/terminal facts')
                if ({key:{k:v for k,v in row.items() if k!='verification_id'} for key,row in current['spec_applications'].items()}
                        != {key:{k:v for k,v in row.items() if k!='verification_id'} for key,row in self.before_rows['spec_applications'].items()}):
                    raise AssertionError('Verify-only rewrote actual application facts instead of appending target observation')
                fresh=[v for key,v in current['verifications'].items() if key not in self.before_rows['verifications']]
                if not fresh or not any(v['status']=='blocked' and json.loads(v['items_json']).get('application_id') for v in fresh):raise AssertionError('Actual unapproved formal drift needs a new blocked applied VER')
            if case in ('finish_a','adopt_external','deliver_b','finish_b'):
                rule=self.proposal(current,'label-review-rule');app,_=self.actual(current,rule)
                if not effect_state(c,self.project,app)['preserved']:raise AssertionError('An independent approved composition destroyed the declared rule effect')
        observations={}
        if case in ('deliver_a','finish_a','adopt_external','deliver_b','finish_b'):
            expected='B' if case in ('deliver_b','finish_b') else 'A'
            for value in ('A','B'):
                result=self.literal(value);observations['policy_'+value]=result
                if (result['exit_code']==0)!=(value==expected):raise AssertionError('Current literal outcome differs from declared A/B contract; old passing history is not current validity')
        self.running_case=None;self.next_case+=1
        return {'case':case,'passed_parent_checks':True,'counts':{k:len(v) for k,v in current.items()},
                'actual_literal_observations':observations,'limitations':['Parent facts and bounded literal commands; native semantic/authorization trace still requires review.']}
