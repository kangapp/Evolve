"""Real task checks, task review, final integration, and failure-backed complex repairs."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.reading import current_state
from evolve_core.recover import recover
from evolve_core.resume import resume_view
from evolve_core.structured import whole_definition
from evolve_core.verify import verify
from evolve_core.work import fingerprint


SUM = 'def total(values):\n    return sum(values)\n'
REPORT = 'from total import total\ndef render_total(values):\n    return str(total(values))\n'


class StructuredExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-complex-execution-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root/'total.py').write_text('def total(values):\n    return len(values)\n')
        (self.root/'test_total.py').write_text('import unittest\nfrom total import total\nclass TestTotal(unittest.TestCase):\n'
            '    def test_literals(self):\n        self.assertEqual(total([2,3]),5)\n        self.assertEqual(total([]),0)\n        self.assertEqual(total([-2,3]),1)\n')
        (self.root/'test_report.py').write_text('import unittest\nfrom report import render_total\nclass TestReport(unittest.TestCase):\n'
            '    def test_literal(self): self.assertEqual(render_total([2,3]),"5")\n')
        (self.root/'test_integration.py').write_text('import unittest\nfrom report import render_total\nclass TestIntegration(unittest.TestCase):\n'
            '    def test_negative_report(self): self.assertEqual(render_total([-2,3]),"1")\n')
        self.checks = [{'id':key,'argv':[sys.executable,'-B','-m','unittest',*arguments,'-v'],'cwd':'.','timeout':10}
            for key,arguments in [('sum',['test_total']),('report',['test_report']),('integration',['discover'])]]
        self.auth = {'source':'controlled-complex-execution-fixture','text':'Complete the presented two-task fixture and its registered checks.',
            'effect_kinds':['project_records','business_files','checks'],'paths':['total.py','report.py']}
        self.project = connect(self.root,{'authorization':self.auth,'input':{'checks':self.checks}})
        self.data = {'complexity':'complex','title':'Correct total and report','plan':'Correct sums, then expose a report and verify integration.',
            'completion':'Positive and negative totals are reported correctly.','scope':['total.py','report.py'],'required_checks':['integration'],
            'acceptance':[{'key':'sum','text':'Positive, empty and negative totals match independent literals.'},
                          {'key':'report','text':'The report preserves the total including negative inputs.'}],
            'spec':{'problem':'Totals count values.','goals':['Correct arithmetic and report.'],'non_goals':['External writes.'],
                'behavior':['The report uses the total function.'],'constraints':['Keep the total interface.'],
                'tradeoffs':['A separate report preserves the total interface.'],
                'test_decisions':['Keep original literal sum expectations.','Check report and final negative-input integration.'],'open_questions':[]},
            'tasks':[{'local_key':'SUM','title':'Get correct totals','completion':'Original sum examples pass.','validation':'Call total with the original literals.',
                'exclusions':['Report formatting.'],'scope':['total.py'],'acceptance':['sum'],'required_checks':['sum'],
                'context_paths':['test_total.py'],'test_decision_refs':['spec.test_decisions/0'],'dependencies':[]},
                {'local_key':'REPORT','title':'Get a readable total','completion':'Report output agrees with the total.','validation':'Compare public report output to independent literals.',
                'exclusions':['Changing original arithmetic expectations.'],'scope':['report.py'],'acceptance':['report'],'required_checks':['report'],
                'context_paths':['test_report.py','test_integration.py'],'test_decision_refs':['spec.test_decisions/1'],
                'dependencies':[{'upstream_task':'SUM','condition_kind':'verification_passed','basis':'The report consumes the corrected and reviewed sum.'}]}]}
        self.plan = self.propose()

    def identity(self):
        return {'project_id':self.project['project_id'],'expected_workspace_epoch':self.project['workspace_epoch']}

    def rows(self,sql,values=()):
        with sqlite3.connect(self.root/'evolve/history.db') as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute(sql,values)]

    def propose(self,data=None):
        data=copy.deepcopy(self.data if data is None else data)
        data['presentation']={'source':'controlled-presentation-fixture','document':{k:v for k,v in data.items() if k!='complexity'}}
        return propose(self.root,{**self.identity(),'authorization':self.auth,'input':data})

    def context(self,key=None):
        change=self.rows('SELECT * FROM changes WHERE id=?',(self.plan['change_id'],))[0]
        revision=self.rows('SELECT * FROM plan_revisions WHERE id=?',(change['current_revision'],))[0]
        tasks=self.rows('SELECT * FROM tasks WHERE revision_id=? ORDER BY rowid',(revision['id'],))
        task=next((t for t in tasks if json.loads(t['definition_json'])['local_key']==key),None)
        definition=json.loads(task['definition_json']) if task else whole_definition(revision,tasks)
        return change,revision,tasks,task,definition

    def request(self,key=None,extra=None):
        change,revision,tasks,task,_=self.context(key)
        return {**self.identity(),'request_id':str(uuid.uuid4()),'authorization':self.auth,
            'expected_versions':{'change':change['row_version'],'tasks':{t['id']:t['row_version'] for t in tasks}},
            'input':{'change_id':change['id'],'revision_id':revision['id'],'task_id':task['id'] if task else None,
                'definition_digest':task['definition_digest'] if task else revision['definition_digest'],**(extra or {})}}

    def apply(self,key,contents=None,**extra):
        files=[{'path':name,'content':text,'expected_digest':digest((self.root/name).read_bytes()) if (self.root/name).is_file() else None}
               for name,text in (contents or {}).items()]
        return implement(self.root,self.request(key,{'accepted_plan_digest':self.plan['plan_digest'],'files':files,**extra}))

    def review_request(self,key=None,failed_ac=None):
        _,_,_,_,definition=self.context(key)
        snapshot=fingerprint(self.root,definition)
        reviews=[{'axis':axis,'observer':'controlled-fixture-observer','summary':'Controlled observations against the declared public interfaces and independent literal tests.',
            'fingerprint_digest':snapshot['digest'],'findings':[]} for axis in ('spec','standards')]
        reviews[0]['acceptance_results']=[{'ac_id':a['id'],'status':'failed' if a.get('key')==failed_ac else 'passed',
            'basis':'Controlled fixture assessment; literal expectations are retained in test_total.py, test_report.py and test_integration.py.'} for a in definition['acceptance']]
        return self.request(key,{'reviews':reviews})

    def verify(self,key=None,**options):
        return verify(self.root,self.review_request(key,**options))

    def close(self,verification):
        return archive(self.root,self.request(extra={'verification_id':verification['verification_id']}))

    def complete_sum(self):
        self.assertEqual(self.apply('SUM',{'total.py':SUM})['outcome'],'implemented')
        self.assertEqual(self.verify('SUM')['status'],'passed')

    def task(self,key):
        return self.context(key)[3]

    def test_real_two_task_checks_reviews_and_whole_change_closure(self):
        self.complete_sum()
        report=self.apply('REPORT',{'report.py':REPORT})
        self.assertEqual(report['outcome'],'implemented')
        task_verification=self.verify('REPORT')
        self.assertEqual(task_verification['status'],'passed')
        self.assertEqual(task_verification['verification_scope'],'task')
        with self.assertRaises(EvolveError) as caught:
            self.close(task_verification)
        self.assertEqual(caught.exception.code,'VERIFICATION')
        final=self.verify()
        self.assertEqual(final['status'],'passed')
        self.assertEqual(final['verification_scope'],'change')
        self.assertEqual(self.close(final)['outcome'],'archived')

    def test_new_upstream_context_is_consumed_only_after_actual_output_and_review(self):
        self.data['scope'].append('generated/total.py')
        self.data['tasks'][0]['scope'].append('generated/total.py')
        self.data['tasks'][1]['context_paths'].append('generated/total.py')
        self.auth['paths'].append('generated/total.py')
        self.plan = self.propose()
        self.assertFalse((self.root / 'generated/total.py').exists())
        with self.assertRaises(EvolveError) as caught:
            self.apply('REPORT', {'report.py': REPORT})
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        self.apply('SUM', {'total.py': SUM, 'generated/total.py': SUM})
        with self.assertRaises(EvolveError) as caught:
            self.apply('REPORT', {'report.py': REPORT})
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        self.verify('SUM')
        (self.root / 'generated/total.py').write_text('def total(values): return 99\n')
        with self.assertRaises(EvolveError) as caught:
            self.apply('REPORT', {'report.py': REPORT})
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        (self.root / 'generated/total.py').write_text(SUM)
        self.apply('REPORT', {'report.py': REPORT.replace('from total import total', 'from generated.total import total')})
        self.assertEqual(self.verify('REPORT')['status'], 'passed')
        self.assertEqual(self.close(self.verify())['outcome'], 'archived')

    def test_producer_missing_declared_context_output_does_not_release_consumer(self):
        self.data['scope'].append('generated/total.py')
        self.data['tasks'][0]['scope'].append('generated/total.py')
        self.data['tasks'][1]['context_paths'].append('generated/total.py')
        self.data['tasks'][1]['dependencies'][0]['condition_kind'] = 'task_completed'
        self.auth['paths'].append('generated/total.py')
        self.plan = self.propose()
        result = self.apply('SUM', {'total.py': SUM})
        self.assertEqual(result['outcome'], 'checks_not_passed')
        self.assertTrue(all(check['status'] == 'passed' for check in result['task_checks']))
        self.assertEqual(self.task('SUM')['state'], 'in_progress')
        self.assertFalse((self.root / 'generated/total.py').exists())
        with self.assertRaises(EvolveError) as caught:
            self.apply('REPORT', {'report.py': REPORT})
        self.assertEqual(caught.exception.code, 'DEPENDENCY_NOT_READY')
        self.assertFalse((self.root / 'report.py').exists())

    def test_initial_and_done_but_unverified_upstream_cannot_satisfy_verification_condition(self):
        for stage in ('initial','implemented'):
            if stage=='implemented': self.apply('SUM',{'total.py':SUM})
            with self.subTest(stage=stage),self.assertRaises(EvolveError) as caught:
                self.apply('REPORT',{'report.py':REPORT})
            self.assertEqual(caught.exception.code,'DEPENDENCY_NOT_READY')
            self.assertFalse((self.root/'report.py').exists())
        self.verify('SUM')
        self.assertEqual(self.apply('REPORT',{'report.py':REPORT})['outcome'],'implemented')

    def test_partial_task_success_cannot_pass_whole_acceptance_or_archive(self):
        self.complete_sum()
        partial=self.verify()
        self.assertEqual(partial['status'],'blocked')
        with self.assertRaises(EvolveError) as caught:
            self.close(partial)
        self.assertEqual(caught.exception.code,'INCOMPLETE_TASK')
        self.assertEqual(self.task('SUM')['state'],'done')
        self.assertEqual(self.task('REPORT')['state'],'todo')

    def test_final_integration_failure_repairs_same_revision_under_original_plan(self):
        self.complete_sum()
        wrong='from total import total\ndef render_total(values):\n    return "0" if any(v < 0 for v in values) else str(total(values))\n'
        self.assertEqual(self.apply('REPORT',{'report.py':wrong})['outcome'],'implemented')
        failed=self.verify(failed_ac='report')
        self.assertEqual(failed['status'],'failed')
        revision=self.plan['revision_id']
        with self.assertRaises(EvolveError): self.close(failed)
        self.apply('REPORT',{'report.py':REPORT},reopen_verification_id=failed['verification_id'])
        self.assertEqual(self.context()[1]['id'],revision)
        final=self.verify()
        self.assertEqual(final['status'],'passed')
        self.assertEqual(self.close(final)['outcome'],'archived')
        self.assertEqual(self.rows('SELECT status FROM verifications WHERE id=?',(failed['verification_id'],))[0]['status'],'failed')

    def test_real_pause_fresh_resume_and_same_task_continuation(self):
        pause={'reason':'Stop after the file section.','completed':['Corrected sum source.'],
            'remaining':['Run the original checks and review.'],'next_steps':['Resume this actual Task.']}
        partial=self.apply('SUM',{'total.py':SUM},pause=pause)
        self.assertEqual(partial['outcome'],'partial')
        self.assertEqual(partial['checks'],'not_run')
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        restored=resume_view(self.root,self.plan['change_id'])
        after={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        self.assertEqual(restored['suggested_action'],'apply')
        self.assertEqual(next(t for t in restored['task_contexts'] if t['local_key']=='SUM')['result']['progress'],pause)
        source=self.rows('SELECT result_digest FROM phase_runs WHERE id=?',(partial['run_id'],))[0]
        reference={'run_id':partial['run_id'],'result_digest':source['result_digest']}
        continued=self.apply('SUM',continuation=reference)
        self.assertEqual(continued['outcome'],'implemented')
        self.assertEqual(self.rows('SELECT purpose FROM source_runs WHERE run_id=?',(continued['run_id'],))[0]['purpose'],'normal_continuation')
        self.assertEqual(self.rows('SELECT result_digest FROM phase_runs WHERE id=?',(partial['run_id'],))[0],source)

    def test_required_upstream_result_change_reopens_only_its_real_dependents(self):
        self.complete_sum(); self.apply('REPORT',{'report.py':REPORT})
        old_report=self.task('REPORT')['result_json']
        (self.root/'total.py').write_text('def total(values): return len(values)\n')
        failure=self.verify()
        self.assertEqual(failure['status'],'blocked')
        revised='def total(values):\n    result = 0\n    for value in values:\n        result += value\n    return result\n'
        self.apply('SUM',{'total.py':revised},reopen_verification_id=failure['verification_id'],
            observations={'total.py':digest((self.root/'total.py').read_bytes())})
        self.assertEqual(self.task('REPORT')['state'],'todo')
        self.assertEqual(self.task('REPORT')['result_json'],old_report)
        self.verify('SUM')
        self.assertEqual(self.apply('REPORT')['outcome'],'implemented')
        self.assertEqual(self.verify()['status'],'passed')

    def test_ordered_shared_output_uses_actual_upstream_baseline_and_final_output(self):
        data=copy.deepcopy(self.data)
        data['tasks'][1]['scope'].append('total.py')
        self.plan=self.propose(data)
        self.complete_sum()
        altered=SUM.replace('sum(values)','sum(values) + 0')
        self.assertEqual(self.apply('REPORT',{'total.py':altered,'report.py':REPORT})['outcome'],'implemented')
        final=self.verify()
        self.assertEqual(final['status'],'passed')
        self.assertEqual(self.close(final)['outcome'],'archived')

    def test_external_upstream_edit_is_not_consumed_as_a_ready_dependency(self):
        self.complete_sum()
        edited='def total(values): return 99\n'
        (self.root/'total.py').write_text(edited)
        with self.assertRaises(EvolveError) as caught:
            self.apply('REPORT',{'report.py':REPORT})
        self.assertEqual(caught.exception.code,'DEPENDENCY_NOT_READY')
        self.assertEqual((self.root/'total.py').read_text(),edited)
        self.assertFalse((self.root/'report.py').exists())

    def test_unrelated_knowledge_append_does_not_invalidate_task_or_final_verification(self):
        self.complete_sum(); self.apply('REPORT',{'report.py':REPORT})
        final=self.verify()
        self.assertEqual(final['status'],'passed')
        (self.root/'evolve/unrelated.md').write_text('An unrelated observation.\n')
        self.assertEqual(self.close(final)['outcome'],'archived')

    def test_newer_task_failure_blocks_old_whole_pass(self):
        self.complete_sum(); self.apply('REPORT',{'report.py':REPORT})
        final=self.verify()
        self.assertEqual(final['status'],'passed')
        failed=self.verify('REPORT',failed_ac='report')
        self.assertEqual(failed['status'],'failed')
        with self.assertRaises(EvolveError) as caught:
            self.close(final)
        self.assertEqual(caught.exception.code,'VERIFICATION')

    def test_apply_rejects_stale_versions_after_another_task_progresses(self):
        stale=self.request('REPORT',{'files':[],'accepted_plan_digest':self.plan['plan_digest']})
        self.complete_sum()
        with self.assertRaises(EvolveError) as caught:
            implement(self.root,stale)
        self.assertEqual(caught.exception.code,'VERSION')

    def test_pre_refactor_with_failing_original_behavior_writes_no_candidate(self):
        data=copy.deepcopy(self.data)
        data['tasks'][0].update({'pre_refactor':True,'preservation_checks':['sum'],'preservation_inputs':['test_total.py']})
        self.plan=self.propose(data)
        before=(self.root/'total.py').read_bytes()
        result=self.apply('SUM',{'total.py':SUM})
        self.assertEqual(result['outcome'],'checks_not_passed')
        self.assertFalse(result['business_files_dispatched'])
        self.assertEqual((self.root/'total.py').read_bytes(),before)

    def test_unfinished_task_verification_requires_actual_metadata_recovery_before_consumption(self):
        self.apply('SUM',{'total.py':SUM})
        request=self.review_request('SUM')
        from test_crash_points import METADATA_CHILD
        process=subprocess.run([sys.executable,'-B','-c',METADATA_CHILD,
            str(Path(__file__).resolve().parents[1]/'runtime'),str(self.root),'verify','before-run-finish'],
            input=json.dumps(request),text=True,capture_output=True,timeout=15)
        self.assertEqual(process.returncode,35,process.stderr)
        observed=current_state(self.root,self.plan['change_id'])['changes'][0]
        report=next(t for t in observed['tasks'] if t['local_key']=='REPORT')
        self.assertFalse(report['readiness']['ready'])
        original=self.rows('SELECT id FROM phase_runs WHERE request_id=?',(request['request_id'],))[0]
        operation=self.rows('SELECT id FROM operations WHERE run_id=?',(original['id'],))[0]
        result=recover(self.root,self.request(extra={'operation_id':operation['id']}))
        self.assertTrue(result['original_facts_committed'])
        self.assertEqual(self.apply('REPORT',{'report.py':REPORT})['outcome'],'implemented')

    def test_public_cli_selects_and_binds_the_ready_task_without_manual_identifiers(self):
        runtime=Path(__file__).resolve().parents[1]/'runtime/evolve.py'
        request={'authorization':self.auth,'input':{'files':[{'path':'total.py','content':SUM,
            'expected_digest':digest((self.root/'total.py').read_bytes())}]}}
        result=subprocess.run([sys.executable,'-B',str(runtime),'--project',str(self.root),'apply',self.data['title'],'--request','-'],
            input=json.dumps(request),text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        implemented=json.loads(result.stdout)['data']
        self.assertEqual(implemented['outcome'],'implemented')
        self.assertEqual(implemented['input_bindings']['task_id'],self.task('SUM')['id'])
        request.update(implemented['request_context'])
        request['input'].update(implemented['input_bindings'])
        replay=subprocess.run([sys.executable,'-B',str(runtime),'--project',str(self.root),'apply',self.data['title'],'--request','-'],
            input=json.dumps(request),text=True,capture_output=True,timeout=15)
        self.assertEqual(replay.returncode,0,replay.stdout+replay.stderr)
        self.assertEqual(json.loads(replay.stdout)['data']['run_id'],implemented['run_id'])

    def test_task_completed_and_artifact_conditions_are_not_confused_with_verification(self):
        for kind in ('task_completed','artifact_available'):
            with self.subTest(kind=kind):
                data=copy.deepcopy(self.data)
                dependency=data['tasks'][1]['dependencies'][0]
                dependency['condition_kind']=kind
                if kind=='artifact_available': dependency['condition_ref']='total.py'
                self.plan=self.propose(data)
                with self.assertRaises(EvolveError) as caught:
                    self.apply('REPORT',{'report.py':REPORT})
                self.assertEqual(caught.exception.code,'DEPENDENCY_NOT_READY')
                self.apply('SUM',{'total.py':SUM})
                self.assertEqual(self.apply('REPORT',{'report.py':REPORT})['outcome'],'implemented')

    def test_partial_source_cannot_be_reused_as_another_task_continuation(self):
        pause={'reason':'Pause this sum Task.','completed':['Changed sum.'],'remaining':['Checks.'],'next_steps':['Continue SUM.']}
        partial=self.apply('SUM',{'total.py':SUM},pause=pause)
        source=self.rows('SELECT result_digest FROM phase_runs WHERE id=?',(partial['run_id'],))[0]
        with self.assertRaises(EvolveError) as caught:
            self.apply('REPORT',{'report.py':REPORT},continuation={'run_id':partial['run_id'],'result_digest':source['result_digest']})
        self.assertEqual(caught.exception.code,'CONTINUATION')
        self.assertFalse((self.root/'report.py').exists())

    def test_malformed_task_version_map_is_rejected_before_any_task_write(self):
        request=self.request('SUM',{'accepted_plan_digest':self.plan['plan_digest'],'files':[]})
        for value in ({}, {'not-a-version':True}, {'not-a-version':{'nested':1}}):
            with self.subTest(value=value):
                malformed=copy.deepcopy(request)
                malformed['expected_versions']['tasks']=value
                with self.assertRaises(EvolveError) as caught:
                    implement(self.root,malformed)
                self.assertEqual(caught.exception.code,'INPUT')

    def test_task_findings_are_local_but_whole_review_keeps_every_required_finding(self):
        data=copy.deepcopy(self.data)
        data['spec']['behavior']=['Two independent arithmetic interfaces expose the same literals.']
        data['tasks'][1]['dependencies']=[]
        self.plan=self.propose(data)
        self.apply('SUM',{'total.py':SUM})
        self.apply('REPORT',{'report.py':'def render_total(values):\n    return str(sum(values))\n'})
        request=self.review_request('SUM')
        request['input']['reviews'][0]['findings']=[{'id':'F1','path':'total.py','basis':'Controlled blocking-review fixture.',
            'impact':'This required observation awaits resolution.','blocking':True}]
        self.assertEqual(verify(self.root,request)['status'],'failed')
        self.assertEqual(self.verify('REPORT')['status'],'passed')
        whole=self.verify()
        self.assertEqual(whole['status'],'failed')
        self.assertEqual(len(whole['unresolved_prior_findings']),1)

    def test_transitive_declared_context_drift_blocks_the_real_descendant(self):
        (self.root/'evolve/contract.md').write_text('Original arithmetic meaning.\n')
        data=copy.deepcopy(self.data)
        data['tasks'][0]['context_paths'].append('evolve/contract.md')
        data['scope'].append('output.py')
        data['acceptance'].append({'key':'output','text':'A caller can consume the report through the output interface.'})
        data['tasks'].append({'local_key':'OUTPUT','title':'Consume the report','completion':'The output interface consumes the report.',
            'validation':'Compare output against the public report.','exclusions':['Changing arithmetic.'],'scope':['output.py'],
            'acceptance':['output'],'required_checks':[],'context_paths':[],'test_decision_refs':['spec.test_decisions/1'],
            'dependencies':[{'upstream_task':'REPORT','condition_kind':'task_completed','basis':'Output consumes the implemented report.'}]})
        self.plan=self.propose(data)
        self.complete_sum(); self.apply('REPORT',{'report.py':REPORT})
        state=current_state(self.root,self.plan['change_id'])['changes'][0]
        self.assertTrue(next(t for t in state['tasks'] if t['local_key']=='OUTPUT')['readiness']['ready'])
        (self.root/'evolve/contract.md').write_text('A changed arithmetic meaning.\n')
        state=current_state(self.root,self.plan['change_id'])['changes'][0]
        self.assertFalse(next(t for t in state['tasks'] if t['local_key']=='OUTPUT')['readiness']['ready'])

    def test_changed_task_check_contract_blocks_old_whole_pass_even_if_global_check_is_unchanged(self):
        self.complete_sum(); self.apply('REPORT',{'report.py':REPORT})
        final=self.verify()
        self.assertEqual(final['status'],'passed')
        config=self.root/'evolve/config.toml'
        original=config.read_text()
        self.assertEqual(original.count('test_total'),1)
        config.write_text(original.replace('test_total','test_report'))
        with self.assertRaises(EvolveError) as caught:
            self.close(final)
        self.assertEqual(caught.exception.code,'CHECK_CONFIG')


if __name__=='__main__':
    unittest.main()
