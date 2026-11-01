"""Actual seven-stage fixture exercises the native runner's parent checks without models."""
import copy
import json
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'runtime'))
sys.path.insert(0,str(ROOT/'scripts'))
from model_complex_checks import ComplexChecks,FIRST_FILES,PROMPTS,scope_for
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.package import check_package,digest
from evolve_core.plans import propose
from evolve_core.revisions import revise
from evolve_core.structured import whole_definition
from evolve_core.verify import verify
from evolve_core.work import fingerprint

CORE='def summarize(values):\n    result = count = 0\n    for value in values:\n        result += value\n        count += 1\n    return result, count\ndef total(values):\n    return summarize(values)[0]\n'
REPORT='from arithmetic import summarize\ndef render(values, include_mean=False):\n    total, count = summarize(values)\n    return f"total={total}; count={count}"\n'
MEAN='from arithmetic import summarize\ndef render(values, include_mean=False):\n    total, count = summarize(values)\n    text = f"total={total}; count={count}"\n    if include_mean:\n        text += f"; mean={total/count if count else 0:.2f}"\n    return text\n'


class ComplexModelParentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='evolve-complex-model-parent-')
        self.addCleanup(self.temp.cleanup)
        self.lab=Path(self.temp.name).resolve(); self.root=self.lab/'business';self.root.mkdir()
        self.evidence=self.lab/'evidence';self.evidence.mkdir()
        for name,content in FIRST_FILES.items(): (self.root/name).write_text(content)
        self.scope=scope_for(check_package(),'codex',None,ROOT/'scripts/model_acceptance.py')
        self.checker=ComplexChecks(self.root,self.scope,self.evidence)
        self.auth={'source':'controlled-native-parent-fixture','text':'Exercise the exact temporary complex fixture without models.',
            'effect_kinds':['project_records','business_files','checks'],'paths':['arithmetic.py','report.py']}
        self.data={'complexity':'complex','title':'Shared single-pass report','plan':'Extract summary preserving original total, then provide report.',
            'completion':'Original totals and single-pass public reports pass.','scope':['arithmetic.py','report.py'],'required_checks':['integration'],
            'acceptance':[{'key':'total','text':'Original total behavior is preserved.'},{'key':'summary','text':'Single-pass summary returns sum and count.'},
                {'key':'report','text':'Public report uses shared summary and independent literals.'}],
            'spec':{'problem':'Report lacks the required single-pass summary.','goals':['Preserve original totals and provide report.'],
                'non_goals':['External systems.'],'behavior':['Report consumes the shared summary exactly once.'],'constraints':['Keep original total interface and tests.'],
                'tradeoffs':['Extract shared summary before exposing report.'],'test_decisions':['Preserve original total literals.','Verify shared summary and final report.'],
                'open_questions':[],'broad_migration':True,'integration_boundary':'arithmetic summary consumed by report, verified through full unittest discovery.'},
            'tasks':[{'local_key':'CORE','title':'Shared summary','completion':'Original total and new summary literals pass.','validation':'Run independent original and summary tests.',
                'exclusions':['Report formatting.'],'scope':['arithmetic.py'],'acceptance':['total','summary'],'required_checks':['original','summary'],
                'context_paths':['test_arithmetic.py','test_summary.py'],'test_decision_refs':['spec.test_decisions/0'],'dependencies':[],
                'pre_refactor':True,'preservation_checks':['original'],'preservation_inputs':['test_arithmetic.py']},
                {'local_key':'REPORT','title':'Public report','completion':'Report consumes shared summary.','validation':'Run independent public report tests.',
                'exclusions':['Changing original total.'],'scope':['report.py'],'acceptance':['report'],'required_checks':['report'],
                'context_paths':['test_report.py','test_integration.py'],'test_decision_refs':['spec.test_decisions/1'],
                'dependencies':[{'upstream_task':'CORE','condition_kind':'verification_passed','basis':'Report consumes preserved and independently reviewed core.'}]}]}

    def install_inside_project(self):
        manifest=check_package();base=self.root/'.agents/evolve-acceptance';source=base/'installed-source';source.mkdir(parents=True)
        for name in [*manifest['files'],'evolve-package.json']:
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        cache=base/'profile/plugins/cache/evolve';shutil.copytree(source,cache)
        self.checker=ComplexChecks(self.root,self.scope,self.evidence,package=cache,registered_root=source)
        return source,cache

    def rows(self,sql,values=()):
        with sqlite3.connect(self.root/'evolve/history.db') as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute(sql,values)]

    def context(self,key=None):
        change=self.rows('SELECT * FROM changes')[0]
        revision=self.rows('SELECT * FROM plan_revisions WHERE id=?',(change['current_revision'],))[0]
        tasks=self.rows('SELECT * FROM tasks WHERE revision_id=? ORDER BY rowid',(revision['id'],))
        task=next((r for r in tasks if json.loads(r['definition_json'])['local_key']==key),None)
        return change,revision,tasks,task

    def request(self,key=None,**extra):
        change,revision,tasks,task=self.context(key)
        return {'request_id':str(uuid.uuid4()),'project_id':self.project['project_id'],'expected_workspace_epoch':self.project['workspace_epoch'],
            'authorization':self.auth,'expected_versions':{'change':change['row_version'],'tasks':{t['id']:t['row_version'] for t in tasks}},
            'input':{'change_id':change['id'],'revision_id':revision['id'],'definition_digest':task['definition_digest'] if task else revision['definition_digest'],
                'task_id':task['id'] if task else None,**extra}}

    def proposal(self):
        data=copy.deepcopy(self.data)
        data['presentation']={'source':'controlled-complex-presentation','document':{k:v for k,v in data.items() if k!='complexity'}}
        return data

    def plan(self):
        self.checker.before('propose')
        checks=[{'id':key,'argv':[sys.executable,'-B','-m','unittest',module,'-v'],'cwd':'.','timeout':10}
            for key,module in [('original','test_arithmetic'),('summary','test_summary'),('report','test_report'),('integration','discover')]]
        self.checks=checks
        self.project=connect(self.root,{'authorization':self.auth,'input':{'checks':checks}})
        propose(self.root,{'project_id':self.project['project_id'],'expected_workspace_epoch':self.project['workspace_epoch'],
            'authorization':self.auth,'input':self.proposal()})
        return self.checker.after('propose')

    def apply(self,key,contents=None,**extra):
        _,revision,_,_=self.context(key)
        files=[{'path':name,'content':text,'expected_digest':digest((self.root/name).read_bytes())} for name,text in (contents or {}).items()]
        return implement(self.root,self.request(key,accepted_plan_digest=revision['plan_digest'],files=files,**extra))

    def reference(self,result):
        return {'run_id':result['run_id'],'result_digest':self.rows('SELECT result_digest FROM phase_runs WHERE id=?',(result['run_id'],))[0]['result_digest']}

    def update(self,approval=None,**extra):
        extra={'reason':'Exercise the exact native complex fixture revision.','proposal':self.proposal(),**extra}
        if approval: extra['approval']={'candidate_digest':approval,'source':'controlled-complex-fixture','text':'Accept this exact fixture candidate.'}
        return revise(self.root,self.request(**extra))

    def verify(self,key=None):
        _,revision,tasks,task=self.context(key)
        definition=json.loads(task['definition_json']) if task else whole_definition(revision,tasks)
        fp=fingerprint(self.root,definition)
        reviews=[{'axis':axis,'observer':'controlled-component-fixture','summary':'Actual fixture source and retained literals inspected; no native model.',
            'fingerprint_digest':fp['digest'],'findings':[]} for axis in ('spec','standards')]
        reviews[0]['acceptance_results']=[{'ac_id':a['id'],'status':'passed','basis':'Controlled independent literal expectations.'} for a in definition['acceptance']]
        return verify(self.root,self.request(key,reviews=reviews))

    def register_mean(self):
        checks=self.checks+[{'id':'mean','argv':[sys.executable,'-B','-m','unittest','test_report_mean','-v'],'cwd':'.','timeout':10}]
        identity={'project_id':self.project['project_id'],'expected_workspace_epoch':self.project['workspace_epoch'],'authorization':self.auth}
        candidate=connect(self.root,{**identity,'input':{'checks':checks}})
        connect(self.root,{**identity,'input':{'checks':checks,'expected_config_digest':candidate['expected_config_digest'],
            'presentation':{'source':'controlled-new-mean-check','text':candidate['candidate']}}})

    def walk(self,until='verify'):
        self.plan()
        if until=='propose': return
        self.checker.before('refactor_pause')
        prepared=self.apply('CORE',preservation_only=True)
        self.paused=self.apply('CORE',{'arithmetic.py':CORE},continuation=self.reference(prepared),pause={'reason':'Actual file boundary.',
            'completed':['Shared summary written.'],'remaining':['Original post checks and acceptance.'],'next_steps':['Continue with original proof.']})
        self.checker.after('refactor_pause')
        if until=='refactor_pause': return
        self.checker.before('cosmetic_revision')
        self.data['title']='单次迭代汇总与报告';self.data['plan']='Clarify the same shared summary and report.'
        self.update();self.checker.after('cosmetic_revision')
        if until=='cosmetic_revision': return
        self.checker.before('continue')
        self.apply('CORE',continuation=self.reference(self.paused));self.verify('CORE')
        self.apply('REPORT',{'report.py':REPORT});self.verify()
        self.checker.after('continue')
        if until=='continue': return
        self.checker.before('local_revision')
        self.data['acceptance'].append({'key':'mean','text':'Optional mean uses two decimal places; empty mean is 0.00.'})
        self.data['tasks'][1]['acceptance'].append('mean')
        self.data['tasks'][1]['completion']+=' Include optional mean while retaining default output.'
        self.data['tasks'][1]['context_paths'].append('test_report_mean.py')
        self.data['tasks'][1]['required_checks'].append('mean')
        self.register_mean()
        self.draft=self.update();self.checker.after('local_revision')
        if until=='local_revision': return
        self.checker.before('finish_revision')
        self.update(self.draft['candidate_digest']);self.apply('REPORT',{'report.py':MEAN})
        final=self.verify();archive(self.root,self.request(verification_id=final['verification_id']))
        self.checker.after('finish_revision')
        if until=='finish_revision': return
        self.checker.before('verify');self.verify();return self.checker.after('verify')

    def test_all_seven_actual_workflow_boundaries_pass_without_model_transport(self):
        observed=self.walk()
        self.assertEqual(observed['parent_checks'],'passed')
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'],'archived')
        self.assertEqual(len(self.rows("SELECT * FROM events WHERE kind='preservation_before_checked'")),1)

    def test_cosmetic_revision_retains_context_produced_by_its_declared_upstream(self):
        self.data['tasks'][1]['context_paths'].append('arithmetic.py')
        observed=self.walk()
        self.assertEqual(observed['parent_checks'],'passed')

    def test_current_normal_pause_source_is_resolved_when_same_bytes_are_resubmitted(self):
        self.walk('cosmetic_revision')
        result=self.apply('CORE',{'arithmetic.py':CORE})
        self.assertTrue(self.rows("SELECT * FROM source_runs WHERE run_id=? AND source_run_id=? AND purpose='normal_continuation'",
            (result['run_id'],self.paused['run_id'])))
        self.assertEqual(result['continuation']['run_id'],self.paused['run_id'])
        self.assertTrue(result['continuation']['resolved_from_task_result'])
        self.assertEqual((self.root/'arithmetic.py').read_text(),CORE)
        self.assertEqual(self.context('CORE')[3]['state'],'done')
        self.assertTrue(self.rows("SELECT * FROM source_runs WHERE source_run_id=? AND purpose='normal_continuation'",(self.paused['run_id'],)))

    def test_implicit_pause_source_does_not_expand_the_original_grant(self):
        self.walk('cosmetic_revision')
        request=self.request('CORE',accepted_plan_digest=self.context()[1]['plan_digest'],files=[])
        request['authorization']={**self.auth,'paths':self.auth['paths']+['other.py']}
        with self.assertRaises(EvolveError) as caught:
            implement(self.root,request)
        self.assertEqual(caught.exception.code,'AUTHORIZATION')
        blocked=self.rows('SELECT id FROM phase_runs WHERE request_id=?',(request['request_id'],))[0]['id']
        self.assertFalse(self.rows("SELECT * FROM source_runs WHERE run_id=?",(blocked,)))

    def test_before_proof_cannot_replace_the_current_file_pause_source(self):
        self.walk('cosmetic_revision')
        source=self.checker.proof['run_id']
        reference={'run_id':source,'result_digest':self.rows('SELECT result_digest FROM phase_runs WHERE id=?',(source,))[0]['result_digest']}
        with self.assertRaises(EvolveError) as caught:
            self.apply('CORE',continuation=reference)
        self.assertEqual(caught.exception.code,'CONTINUATION')
        self.apply('CORE',continuation=self.reference(self.paused))
        self.assertEqual(self.context('CORE')[3]['state'],'done')

    def test_declared_producer_context_does_not_hide_an_external_producer_edit(self):
        self.data['tasks'][1]['context_paths'].append('arithmetic.py')
        self.walk('continue')
        (self.root/'arithmetic.py').write_text(CORE.replace('result += value','result += value * 2'))
        self.data['title']+=' clearer title'
        self.update()
        self.assertEqual(self.context('CORE')[3]['state'],'todo')
        with self.assertRaises(EvolveError) as caught:
            self.apply('REPORT',{'report.py':REPORT})
        self.assertEqual(caught.exception.code,'DEPENDENCY_NOT_READY')

    def test_producer_context_does_not_hide_unrelated_fixed_context_drift(self):
        self.data['tasks'][1]['context_paths'].append('arithmetic.py')
        self.walk('refactor_pause')
        path=self.root/'test_report.py';path.write_text(path.read_text()+'\n# external context observation\n')
        self.data['title']+=' clearer title'
        result=self.update()
        self.assertFalse(result['semantic_same'])
        self.assertIsNone(self.context()[1]['accepted_event_id'])

    def pending_mean_candidate(self, *, include_check=True):
        self.data['spec']['non_goals'].append('The first report iteration excludes optional mean.')
        self.walk('continue')
        self.checker.before('local_revision')
        self.data['spec']['non_goals'].remove('The first report iteration excludes optional mean.')
        self.data['spec']['behavior'].append('Optional mean has two decimals; empty input is 0.00.')
        self.data['acceptance'].append({'key':'mean','text':'Optional mean uses two decimals while default output stays unchanged.'})
        self.data['tasks'][1]['acceptance'].append('mean')
        self.data['tasks'][1]['completion']+=' Include optional mean while retaining default output.'
        self.data['tasks'][1]['context_paths'].append('test_report_mean.py')
        if include_check:self.data['tasks'][1]['required_checks'].append('mean')
        self.register_mean()
        impact={'affected_tasks':['REPORT'],'basis':'Optional mean only changes the report; original arithmetic contract and checks stay unchanged.'}
        pending=self.update(impact=impact)
        self.assertEqual(pending['outcome'],'scope_confirmation_required')
        return pending,impact

    def test_specific_scope_candidate_waits_without_acceptance_then_completes_new_mean(self):
        pending,impact=self.pending_mean_candidate()
        self.checker.after('local_revision')
        self.checker.before('finish_revision')
        self.update(pending['candidate_digest'],impact=impact)
        self.apply('REPORT',{'report.py':MEAN})
        final=self.verify();archive(self.root,self.request(verification_id=final['verification_id']))
        self.checker.after('finish_revision')
        self.checker.before('verify');self.verify()
        self.assertEqual(self.checker.after('verify')['parent_checks'],'passed')

    def test_pending_scope_candidate_without_mean_task_check_cannot_pass(self):
        self.pending_mean_candidate(include_check=False)
        with self.assertRaisesRegex(AssertionError,'Pending mean result lacks its actual required task check'):
            self.checker.after('local_revision')

    def test_pending_scope_candidate_cannot_be_silently_rewritten_at_acceptance(self):
        self.pending_mean_candidate();self.checker.after('local_revision')
        self.checker.before('finish_revision')
        self.data['plan']+=' Silent new wording after the reviewed candidate.'
        candidate=self.update(impact={'affected_tasks':['REPORT'],'basis':'Only report meaning changes.'})
        self.update(candidate['candidate_digest'],impact={'affected_tasks':['REPORT'],'basis':'Only report meaning changes.'})
        self.apply('REPORT',{'report.py':MEAN})
        final=self.verify();archive(self.root,self.request(verification_id=final['verification_id']))
        with self.assertRaisesRegex(AssertionError,'exact pending mean candidate'):
            self.checker.after('finish_revision')

    def test_proposal_cannot_claim_pass_after_implicit_execution(self):
        self.plan();self.apply('CORE',preservation_only=True)
        with self.assertRaisesRegex(AssertionError,'Proposal implicitly'):
            self.checker.after('propose')

    def test_immutable_test_edit_is_rejected_despite_workflow_progress(self):
        self.walk('refactor_pause')
        (self.root/'test_arithmetic.py').write_text(FIRST_FILES['test_arithmetic.py'].replace('total([2,3]),5','total([2,3]),2'))
        with self.assertRaisesRegex(AssertionError,'independent literal test'):
            self.checker.after('refactor_pause')

    def test_cosmetic_case_requires_real_revision(self):
        self.walk('refactor_pause');self.checker.before('cosmetic_revision')
        with self.assertRaisesRegex(AssertionError,'No actual new REV'):
            self.checker.after('cosmetic_revision')

    def test_cosmetic_case_rejects_semantic_reopening(self):
        self.walk('refactor_pause');self.checker.before('cosmetic_revision')
        self.data['tasks'][0]['completion']+=' Changed behavior boundary.';self.update()
        with self.assertRaisesRegex(AssertionError,'Unchanged CORE lost'):
            self.checker.after('cosmetic_revision')

    def test_continuation_cannot_implicitly_archive_before_planned_revision(self):
        self.walk('continue')
        final=self.verify();archive(self.root,self.request(verification_id=final['verification_id']))
        with self.assertRaisesRegex(AssertionError,'pre-archive boundary'):
            self.checker.after('continue')

    def test_local_revision_cannot_reopen_unaffected_core(self):
        self.walk('continue');self.checker.before('local_revision')
        self.data['tasks'][1]['required_checks'].append('mean');self.register_mean()
        self.data['tasks'][0]['completion']+=' Unrelated new boundary.';self.update()
        with self.assertRaisesRegex(AssertionError,'Unchanged CORE lost'):
            self.checker.after('local_revision')

    def test_new_mean_result_requires_its_own_registered_task_check(self):
        self.walk('continue');self.checker.before('local_revision')
        self.data['acceptance'].append({'key':'mean','text':'Optional mean uses two decimal places.'})
        self.data['tasks'][1]['acceptance'].append('mean')
        self.data['tasks'][1]['context_paths'].append('test_report_mean.py')
        self.update()
        with self.assertRaisesRegex(AssertionError,'actual required task check'):
            self.checker.after('local_revision')

    def test_verify_only_cannot_silently_repair_the_controlled_regression(self):
        self.walk('finish_revision');self.checker.before('verify')
        (self.root/'report.py').write_text(MEAN)
        with self.assertRaisesRegex(AssertionError,'phase changed business bytes'):
            self.checker.after('verify')

    def test_same_seven_stages_pass_with_both_actual_plugin_roots_inside_project(self):
        self.install_inside_project();self.walk()
        self.assertEqual(self.rows('SELECT state FROM changes')[0]['state'],'archived')

    def test_registered_root_change_is_rejected_while_cache_stays_intact(self):
        source,_=self.install_inside_project();(source/'shared/contract.md').write_text('changed')
        with self.assertRaises(EvolveError) as caught:self.checker.before('propose')
        self.assertEqual(caught.exception.code,'PACKAGE_INCOMPLETE')

    def test_unrelated_agents_file_is_not_hidden_by_the_installation_exception(self):
        self.install_inside_project();(self.root/'.agents/foreign.md').write_text('Unexpected file.')
        with self.assertRaisesRegex(AssertionError,'unauthorized business files'):self.plan()


class ComplexModelScopeTests(unittest.TestCase):
    def cli(self,*args):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/model_acceptance.py'),'--host','codex','--package',str(ROOT),
            '--structured',*args],text=True,capture_output=True,timeout=15)

    def test_preflight_freezes_seven_cases_without_profiles_or_model_calls(self):
        result=self.cli('--preflight-only');self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertFalse(data['model_requests_sent']);self.assertFalse(data['host_profile_created'])
        self.assertEqual(list(data['expanded_scope']['cases']),list(PROMPTS))
        self.assertEqual(len(data['expanded_scope']['first_files']),6)
        self.assertEqual(len(data['expanded_scope']['second_files']),1)

    def test_absent_authorization_or_stale_scope_never_creates_host_project(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'must-not-exist'
            for options,expected in [((), 'actual human authorization'),
                    (('--authorization-text','Controlled test text, not a grant','--expected-scope-digest','stale'), 'scope differs')]:
                result=self.cli('--out',str(out),*options)
                self.assertEqual(result.returncode,2);self.assertIn(expected,result.stderr);self.assertFalse(out.exists())

    def test_legacy_variants_cannot_change_the_reviewed_complex_scope(self):
        for flag in ('--session-learning','--verify-missing-tests','--diagnostic','--skip-inspect'):
            result=self.cli('--preflight-only',flag)
            self.assertEqual(result.returncode,2);self.assertIn('seven fixed cases',result.stderr)

    def test_unknown_protocol_or_unapproved_model_scope_is_rejected(self):
        manifest=check_package()
        with self.assertRaisesRegex(ValueError,'protocol-5'):
            scope_for({**manifest,'protocol_version':manifest['protocol_version']+1},'codex',None,ROOT/'scripts/model_acceptance.py')
        with self.assertRaisesRegex(ValueError,'human-selected'):
            scope_for(manifest,'claude',None,ROOT/'scripts/model_acceptance.py')
        expected=scope_for(manifest,'claude','MiniMax-M3.1-Flash',ROOT/'scripts/model_acceptance.py')
        self.assertNotEqual(expected['scope_digest'],scope_for(manifest,'codex',None,ROOT/'scripts/model_acceptance.py')['scope_digest'])


if __name__=='__main__': unittest.main()
