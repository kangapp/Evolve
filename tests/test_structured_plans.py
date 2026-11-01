"""Complex proposals retain the whole presented document and enforce real task structure."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
from evolve_core.connect import connect
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
from evolve_core.plans import propose
from evolve_core.reading import current_state


class StructuredPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evolve-structured-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root/'total.py').write_text('def total(values): return len(values)\n')
        (self.root/'contract.md').write_text('Totals preserve signs and empty input returns zero.\n')
        self.auth = {'source':'isolated-structured-fixture', 'text':'Present the complete specification; do not implement yet.',
                     'effect_kinds':['project_records']}
        self.project = connect(self.root, {'request_id':'connect','authorization':self.auth,
            'input':{'checks':[{'id':'unit','argv':[sys.executable,'-B','-m','unittest','discover','-v'],'cwd':'.','timeout':10}]}})
        self.data = {
            'complexity':'complex','title':'Show correct arithmetic totals',
            'plan':'Correct totals, then expose a formatted report.','completion':'Callers see correct totals in the report.',
            'scope':['total.py','report.py'],'required_checks':['unit'],
            'acceptance':[{'key':'sum','text':'[2,3] totals 5 and empty input totals zero.'},
                          {'key':'report','text':'The report presents the arithmetic total.'}],
            'spec':{'problem':'The current function counts values instead of adding them.',
                'goals':['Correct sums and a readable report.'],'non_goals':['No external data writes.'],
                'behavior':['The report uses the arithmetic total.'],'constraints':['Keep the existing public total function.'],
                'tradeoffs':['Keep the report separate to preserve the function interface.'],
                'test_decisions':['Use independent literal expectations for sums and reporting.'],'open_questions':[]},
            'tasks':[
                {'local_key':'SUM','title':'Callers receive correct totals','completion':'Positive, empty and negative examples pass.',
                 'validation':'Run independent literal total expectations through the public total function.',
                 'exclusions':['Report formatting.'],'test_decision_refs':['spec.test_decisions/0'],
                 'scope':['total.py'],'acceptance':['sum'],'required_checks':['unit'],'context_paths':['contract.md'],'dependencies':[]},
                {'local_key':'REPORT','title':'Callers can display the total','completion':'A formatted report exposes the verified sum.',
                 'validation':'Call the report interface and compare its output with an independent literal.',
                 'exclusions':['Changing arithmetic expectations.'],'test_decision_refs':['spec.test_decisions/0'],
                 'scope':['report.py'],'acceptance':['report'],'required_checks':['unit'],'context_paths':[],
                 'dependencies':[{'upstream_task':'SUM','condition_kind':'task_completed','basis':'The report consumes the corrected total function.'}]}]}

    def request(self, data=None, request_id=None):
        data = copy.deepcopy(self.data if data is None else data)
        shown = {key:value for key,value in data.items() if key != 'complexity'}
        data['presentation'] = {'source':'fixture-assistant-message','document':shown}
        return {'request_id':request_id or str(uuid.uuid4()),'project_id':self.project['project_id'],
            'expected_workspace_epoch':self.project['workspace_epoch'],'authorization':self.auth,'input':data}

    def rows(self, sql, parameters=()):
        with sqlite3.connect(self.root/'evolve/history.db') as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(sql, parameters)]

    def assert_rejected(self, data, code):
        with self.assertRaises(EvolveError) as caught:
            propose(self.root, self.request(data))
        self.assertEqual(caught.exception.code,code)
        self.assertEqual(self.rows('SELECT id FROM changes'),[])

    def test_entire_presented_spec_is_restored_without_approval_or_business_write(self):
        before = (self.root/'total.py').read_bytes()
        request = self.request()
        result = propose(self.root,request)
        self.assertFalse(result['accepted'])
        self.assertEqual((self.root/'total.py').read_bytes(),before)
        self.assertFalse((self.root/'report.py').exists())
        state = current_state(self.root,result['change_id'])['changes'][0]
        self.assertEqual(state['plan']['document'],request['input']['presentation']['document'])
        self.assertFalse(state['plan']['accepted'])
        self.assertEqual({t['local_key']:t['readiness']['ready'] for t in state['tasks']},{'SUM':True,'REPORT':False})
        self.assertEqual(len(result['tasks']),2)
        self.assertEqual([t['task_code'] for t in result['tasks']],['TASK-001','TASK-002'])
        self.assertTrue(all(t['change_id']==result['change_id'] for t in result['tasks']))

    def test_repeated_request_does_not_allocate_duplicate_tasks_or_acceptance(self):
        request = self.request(request_id='same-structured-plan')
        first = propose(self.root,request)
        self.assertEqual(propose(self.root,request),first)
        self.assertEqual(len(self.rows('SELECT id FROM changes')),1)
        self.assertEqual(len(self.rows('SELECT id FROM tasks')),2)
        self.assertEqual(len({a['id'] for a in first['acceptance']}),2)

    def test_same_summary_cannot_approve_a_different_task_definition(self):
        first = propose(self.root,self.request())
        changed = copy.deepcopy(self.data)
        changed['tasks'][1]['completion'] = 'A JSON result exposes the verified sum.'
        second = propose(self.root,self.request(changed))
        self.assertNotEqual(first['plan_digest'],second['plan_digest'])
        self.assertNotEqual(first['definition_digest'],second['definition_digest'])

    def test_summary_only_presentation_does_not_count_as_presented_spec(self):
        request = self.request()
        request['input']['presentation']={'source':'fixture-message','text':self.data['plan']}
        with self.assertRaises(EvolveError) as caught:
            propose(self.root,request)
        self.assertEqual(caught.exception.code,'PRESENTATION')

    def test_public_cli_prepares_identity_and_restores_the_structured_document(self):
        runtime=Path(__file__).resolve().parents[1]/'runtime/evolve.py'
        request=self.request()
        for key in ('request_id','project_id','expected_workspace_epoch'):
            request.pop(key)
        result=subprocess.run([sys.executable,'-B',str(runtime),'--project',str(self.root),'propose',
            '--owner','evolve-propose','--request','-'],input=json.dumps(request),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        planned=json.loads(result.stdout)['data']
        self.assertEqual(planned['request_context']['project_id'],self.project['project_id'])
        observed=subprocess.run([sys.executable,'-B',str(runtime),'--project',str(self.root),'status',planned['change_id']],
            text=True,capture_output=True)
        self.assertEqual(observed.returncode,0,observed.stdout+observed.stderr)
        restored=json.loads(observed.stdout)['data']['project']['changes'][0]
        self.assertEqual(restored['plan']['document'],request['input']['presentation']['document'])
        blocked=subprocess.run([sys.executable,'-B',str(runtime),'--project',str(self.root),'apply',planned['change_id'],
            '--request','-'],input=json.dumps({'authorization':self.auth,'input':{'files':[]}}),text=True,capture_output=True)
        self.assertEqual(json.loads(blocked.stdout)['error']['code'],'AUTHORIZATION')

    def test_dependency_cycle_and_unknown_target_are_rejected(self):
        cycle = copy.deepcopy(self.data)
        cycle['tasks'][0]['dependencies']=[{'upstream_task':'REPORT','condition_kind':'task_completed','basis':'Cycle fixture.'}]
        self.assert_rejected(cycle,'DEPENDENCY_CYCLE')
        unknown = copy.deepcopy(self.data)
        unknown['tasks'][1]['dependencies'][0]['upstream_task']='UNKNOWN'
        self.assert_rejected(unknown,'DEPENDENCY')

    def test_order_without_condition_basis_is_not_a_dependency(self):
        changed=copy.deepcopy(self.data)
        changed['tasks'][1]['dependencies'][0].pop('basis')
        self.assert_rejected(changed,'INPUT')

    def test_uncovered_acceptance_and_file_are_rejected(self):
        acceptance=copy.deepcopy(self.data)
        acceptance['acceptance'].append({'key':'extra','text':'Another required result.'})
        self.assert_rejected(acceptance,'COVERAGE')
        scope=copy.deepcopy(self.data)
        scope['scope'].append('other.py')
        self.assert_rejected(scope,'COVERAGE')

    def test_empty_task_outcome_or_duplicate_identity_is_rejected(self):
        for field,value in [('completion',''),('local_key','SUM')]:
            changed=copy.deepcopy(self.data)
            changed['tasks'][1][field]=value
            self.assert_rejected(changed,'INPUT')

    def test_task_requires_independent_validation_test_decision_reference_and_exclusions(self):
        for field in ('validation','test_decision_refs','exclusions'):
            with self.subTest(field=field):
                changed=copy.deepcopy(self.data)
                changed['tasks'][0].pop(field)
                self.assert_rejected(changed,'INPUT')
        changed=copy.deepcopy(self.data)
        changed['tasks'][0]['test_decision_refs']=['spec.test_decisions/99']
        self.assert_rejected(changed,'CONTEXT')

    def test_unordered_shared_output_is_rejected(self):
        changed=copy.deepcopy(self.data)
        changed['tasks'][1]['scope'].append('total.py')
        changed['tasks'][1]['dependencies']=[]
        self.assert_rejected(changed,'DEPENDENCY')

    def test_required_knowledge_and_cross_change_dependencies_are_not_ignored(self):
        knowledge=copy.deepcopy(self.data)
        knowledge['tasks'][0]['required_knowledge']=['evolve/project.md']
        self.assert_rejected(knowledge,'UNAVAILABLE')
        unknown=copy.deepcopy(self.data)
        unknown['tasks'][1]['dependencies'][0]['condition_kind']='knowledge_applied'
        self.assert_rejected(unknown,'UNAVAILABLE')

    def test_unregistered_check_and_unproven_refactor_are_rejected(self):
        changed=copy.deepcopy(self.data)
        changed['tasks'][0]['required_checks']=['unknown']
        self.assert_rejected(changed,'CHECK_CONFIG')
        refactor=copy.deepcopy(self.data)
        refactor['tasks'][0]['pre_refactor']=True
        self.assert_rejected(refactor,'INPUT')

    def test_broad_migration_requires_final_integration_boundary_and_check(self):
        changed=copy.deepcopy(self.data)
        changed['spec']['broad_migration']=True
        self.assert_rejected(changed,'INPUT')
        changed['spec']['integration_boundary']='The report and sum expose the same public behavior.'
        changed['required_checks']=[]
        self.assert_rejected(changed,'CHECK_CONFIG')

    def test_question_blocks_only_its_affected_task(self):
        changed=copy.deepcopy(self.data)
        changed['tasks'][1]['dependencies']=[]
        changed['spec']['open_questions']=[{'id':'Q1','question':'How are missing values represented?',
            'blocking':True,'task_keys':['SUM']}]
        result=propose(self.root,self.request(changed))
        state=current_state(self.root,result['change_id'])['changes'][0]
        tasks={t['local_key']:t for t in state['tasks']}
        self.assertFalse(tasks['SUM']['readiness']['ready'])
        self.assertTrue(tasks['REPORT']['readiness']['ready'])

    def test_context_drift_is_local_and_queries_preserve_project_bytes(self):
        result=propose(self.root,self.request())
        (self.root/'evolve/unrelated.md').write_text('Unrelated knowledge appended.\n')
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        state=current_state(self.root,result['change_id'])['changes'][0]
        self.assertTrue(next(t for t in state['tasks'] if t['local_key']=='SUM')['readiness']['ready'])
        after={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        (self.root/'contract.md').write_text('Changed the arithmetic contract.\n')
        state=current_state(self.root,result['change_id'])['changes'][0]
        task=next(t for t in state['tasks'] if t['local_key']=='SUM')
        self.assertEqual(task['readiness']['unmet'][0]['kind'],'context_changed')

    def test_actual_preserved_old_writer_rejects_new_task_protocol(self):
        source=Path(__file__).resolve().parents[1]
        old=self.root/'old-package'
        with zipfile.ZipFile(source/'docs/evidence/m1-current-scope-package-alpha4.zip') as archive:
            archive.extractall(old)
        runtime=old/'package/runtime/evolve.py'
        before=(self.root/'evolve/history.db').read_bytes()
        result=subprocess.run([sys.executable,'-B',str(runtime),'--project',str(self.root),'apply','--request','-'],
            input=json.dumps({'authorization':self.auth,'input':{'change_id':'not-selected'}}),text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout)['error']['code'],'SCHEMA_VERSION')
        self.assertEqual((self.root/'evolve/history.db').read_bytes(),before)

    def test_single_structured_task_still_requires_its_explicit_task_binding(self):
        changed=copy.deepcopy(self.data)
        changed['scope']=['total.py']
        changed['acceptance']=changed['acceptance'][:1]
        changed['tasks']=changed['tasks'][:1]
        result=propose(self.root,self.request(changed))
        task=result['tasks'][0]
        original=(self.root/'total.py').read_bytes()
        request={'project_id':self.project['project_id'],'expected_workspace_epoch':self.project['workspace_epoch'],
            'authorization':{**self.auth,'effect_kinds':['project_records','business_files','checks'],'paths':['total.py']},
            'expected_versions':{'change':1,'task':1},'input':{'change_id':result['change_id'],
                'revision_id':result['revision_id'],'definition_digest':task['definition_digest'],
                'accepted_plan_digest':result['plan_digest'],'files':[]}}
        with self.assertRaises(EvolveError) as caught:
            implement(self.root,request)
        self.assertEqual(caught.exception.code,'TASK_TARGET')
        self.assertEqual((self.root/'total.py').read_bytes(),original)
        self.assertEqual(self.rows('SELECT state FROM tasks'),[{'state':'todo'}])


if __name__=='__main__':
    unittest.main()
