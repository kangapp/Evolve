"""Real revision lineage, scoped acceptance and historical evidence checks."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evolve_core.revisions import revise
from evolve_core.errors import EvolveError
from evolve_core.resume import resume_view
from evolve_core.reading import current_state
from tests import test_structured_execution as execution


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.f = execution.StructuredExecutionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def document(self, **changes):
        data = copy.deepcopy(self.f.data)
        data.update(changes)
        return data

    def update(self, data, approval=None, **options):
        proposal = copy.deepcopy(data)
        proposal['presentation'] = {'source': 'controlled-revision-fixture',
            'document': {k:v for k,v in proposal.items() if k != 'complexity'}}
        extra = {'reason': 'Controlled revision of the actual presented fixture.', 'proposal': proposal, **options}
        if approval is not None:
            extra['approval'] = {'candidate_digest': approval, 'source': 'controlled-revision-fixture',
                'text': 'Accept this exact controlled fixture candidate.'}
        result = revise(self.f.root, self.f.request(extra=extra))
        if result['outcome'] == 'revised':
            self.f.plan.update({k: result[k] for k in ('revision_id', 'plan_digest', 'definition_digest')})
        return result

    def complete(self):
        self.f.complete_sum()
        self.f.apply('REPORT', {'report.py': execution.REPORT})
        return self.f.verify()

    def test_format_revision_reuses_real_task_verification_and_old_whole_cutoff(self):
        final = self.complete()
        tasks = self.f.rows('SELECT * FROM tasks')
        count = len(self.f.rows('SELECT * FROM evidence'))
        data = self.document(title='Readable plan title', plan='Same behavior, clearer prose.')
        data['tasks'][0]['title'] = 'Readable task title'
        result = self.update(data)
        self.assertTrue(result['semantic_same'])
        self.assertTrue(result['accepted'])
        self.assertTrue(all(t['result_reused'] and t['state']=='done' for t in result['tasks']))
        self.assertEqual(len(self.f.rows('SELECT * FROM evidence')), count)
        self.assertEqual(len(self.f.rows('SELECT * FROM verifications')), 2)
        for row in tasks:
            self.assertEqual(self.f.rows('SELECT * FROM tasks WHERE id=?',(row['id'],))[0], row)
        view = resume_view(self.f.root,self.f.plan['change_id'])
        self.assertIn(final['verification_id'],[v['id'] for v in view['verifications']])
        self.assertEqual(self.f.close(final)['outcome'],'archived')

    def test_scope_reduction_keeps_head_until_exact_candidate_accepted(self):
        self.complete()
        old = self.f.plan['revision_id']
        data = self.document(scope=['total.py'], acceptance=[self.f.data['acceptance'][0]], tasks=[self.f.data['tasks'][0]])
        pending = self.update(data)
        self.assertEqual(pending['outcome'],'scope_confirmation_required')
        self.assertEqual(self.f.context()[1]['id'],old)
        with self.assertRaises(EvolveError) as caught:
            self.update(data, 'stale-candidate')
        self.assertEqual(caught.exception.code,'REVISION_APPROVAL')
        result = self.update(data,pending['candidate_digest'])
        self.assertTrue(result['accepted'])
        self.assertEqual(len(result['tasks']),1)
        self.assertTrue((self.f.root/'report.py').exists())
        self.assertEqual(len(self.f.rows('SELECT * FROM plan_revisions')),2)

    def test_semantic_draft_requires_acceptance_and_reopens_changed_descendants(self):
        self.complete()
        data = self.document()
        data['tasks'][0]['completion'] += ' Include the retained boundary examples.'
        result = self.update(data)
        self.assertFalse(result['accepted'])
        self.assertTrue(all(t['state']=='todo' for t in result['tasks']))
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM', {'total.py':execution.SUM})
        self.assertEqual(caught.exception.code,'PLAN_ACCEPTANCE')
        accepted = self.update(data, result['candidate_digest'])
        self.assertEqual(accepted['outcome'],'accepted')
        self.assertEqual(len(self.f.rows('SELECT * FROM plan_revisions')),2)
        self.assertEqual(self.f.apply('SUM', {'total.py':execution.SUM})['outcome'],'implemented')

    def test_local_report_revision_preserves_upstream_actual_verification(self):
        self.complete()
        data = self.document()
        data['tasks'][1]['completion'] += ' Preserve its public formatting contract.'
        result = self.update(data)
        self.assertEqual([t['state'] for t in result['tasks']],['done','todo'])
        self.update(data,result['candidate_digest'])
        self.assertEqual(self.f.apply('REPORT', {'report.py':execution.REPORT})['outcome'],'implemented')
        self.assertEqual(self.f.verify()['status'],'passed')

    def test_external_edit_invalidates_scope_candidate_approval(self):
        self.complete()
        data = self.document(scope=['total.py'], acceptance=[self.f.data['acceptance'][0]], tasks=[self.f.data['tasks'][0]])
        pending = self.update(data)
        (self.f.root/'total.py').write_text(execution.SUM+'# external observation\n')
        with self.assertRaises(EvolveError) as caught:
            self.update(data,pending['candidate_digest'])
        self.assertEqual(caught.exception.code,'REVISION_APPROVAL')
        self.assertEqual(len(self.f.rows('SELECT * FROM plan_revisions')),1)

    def test_partial_continuation_crosses_only_proven_same_task_revision(self):
        partial = self.f.apply('SUM', {'total.py':execution.SUM},pause={'reason':'Controlled stop.',
            'completed':['Source written.'],'remaining':['Run declared checks.'],'next_steps':['Continue actual task.']})
        source = self.f.rows('SELECT result_digest FROM phase_runs WHERE id=?',(partial['run_id'],))[0]
        result = self.update(self.document(plan='Clarify existing task order.'))
        self.assertTrue(result['tasks'][0]['result_reused'])
        continuation = {'run_id': partial['run_id'], 'result_digest': source['result_digest']}
        self.assertEqual(self.f.apply('SUM',continuation=continuation)['outcome'],'implemented')
        context = current_state(self.f.root,self.f.plan['change_id'])
        self.assertEqual(context['changes'][0]['plan']['ordinal'],2)

    def test_cosmetic_array_order_preserves_meaning(self):
        self.complete()
        data = self.document()
        data['acceptance'].reverse()
        data['scope'].reverse()
        data['tasks'].reverse()
        result = self.update(data)
        self.assertTrue(result['semantic_same'])
        self.assertTrue(all(t['state']=='done' for t in result['tasks']))

    def test_uncovered_acceptance_is_not_removed_by_dropping_task(self):
        data = self.document(tasks=[self.f.data['tasks'][0]])
        with self.assertRaises(EvolveError) as caught:
            self.update(data)
        self.assertEqual(caught.exception.code,'COVERAGE')
        self.assertEqual(len(self.f.rows('SELECT * FROM plan_revisions')),1)

    def test_acceptance_rewrite_needs_exact_scope_confirmation(self):
        self.complete()
        data = self.document()
        data['acceptance'][1]['text'] = 'The report returns the documented total for all retained examples.'
        pending = self.update(data)
        self.assertEqual(pending['outcome'],'scope_confirmation_required')
        self.assertEqual(len(pending['candidate']['rewritten_acceptance']),1)
        result = self.update(data,pending['candidate_digest'])
        self.assertEqual([t['state'] for t in result['tasks']],['done','todo'])

    def test_global_spec_impact_can_preserve_tasks_but_needs_new_whole_verification(self):
        final = self.complete()
        data = self.document()
        data['spec']['constraints'].append('Document the current integration boundary.')
        impact = {'affected_tasks': [], 'basis': 'The added global documentation constraint changes final review only.'}
        result = self.update(data,impact=impact)
        self.assertTrue(all(t['state']=='done' for t in result['tasks']))
        with self.assertRaises(EvolveError) as caught:
            self.f.verify()
        self.assertEqual(caught.exception.code,'PLAN_ACCEPTANCE')
        self.update(data,result['candidate_digest'],impact=impact)
        with self.assertRaises(EvolveError) as caught:
            self.f.close(final)
        self.assertEqual(caught.exception.code,'VERIFICATION')
        new = self.f.verify()
        self.assertEqual(new['status'],'passed')
        self.assertEqual(self.f.close(new)['outcome'],'archived')

    def test_old_blocking_finding_survives_revision_until_actual_resolution(self):
        from evolve_core.verify import verify
        self.f.complete_sum()
        self.f.apply('REPORT', {'report.py':execution.REPORT})
        request = self.f.review_request()
        request['input']['reviews'][0]['findings'] = [{'id':'report-contract','blocking':True,
            'basis':'Controlled fixture requires an explicit report reinspection.', 'path':'report.py', 'impact':'Required review.'}]
        failed = verify(self.f.root,request)
        self.assertEqual(failed['status'],'failed')
        self.update(self.document(plan='Clarify the current task order.'))
        self.assertEqual(self.f.verify()['status'],'failed')
        request = self.f.review_request()
        request['input']['reviews'][0]['resolutions'] = [{'verification_id':failed['verification_id'],
            'finding_id':'report-contract','basis':'Reinspected the public report with original negative and positive literals.'}]
        self.assertEqual(verify(self.f.root,request)['status'],'passed')
        self.assertEqual(self.f.verify('SUM')['status'],'passed')

    def test_changed_context_reopens_task_and_descendants(self):
        self.complete()
        original = (self.f.root/'test_total.py').read_text()
        (self.f.root/'test_total.py').write_text(original+'# inspected context update\n')
        result = self.update(self.document(plan='Rebind the inspected original test context.'))
        self.assertTrue(all(t['state']=='todo' for t in result['tasks']))
        self.assertFalse(result['semantic_same'])

    def test_external_output_change_cannot_be_carried_as_completed(self):
        self.complete()
        (self.f.root/'total.py').write_text(execution.SUM+'# external change\n')
        result = self.update(self.document(plan='Clarify the current task order.'))
        self.assertEqual(result['tasks'][0]['state'],'todo')
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM',{'total.py':execution.SUM})
        self.assertEqual(caught.exception.code,'FILE_CONFLICT')

    def test_format_revision_cannot_bypass_pending_semantic_acceptance(self):
        self.complete()
        data = self.document()
        data['tasks'][1]['completion'] += ' Retain the public output boundary.'
        self.update(data)
        data['plan'] = 'Clarify prose after the semantic draft.'
        result = self.update(data)
        self.assertTrue(result['semantic_same'])
        self.assertFalse(result['accepted'])
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('REPORT',{'report.py':execution.REPORT})
        self.assertEqual(caught.exception.code,'PLAN_ACCEPTANCE')

    def test_preservation_original_proof_survives_format_revision_and_partial_continuation(self):
        (self.f.root/'total.py').write_text(execution.SUM)
        data = self.document()
        data['tasks'][0].update({'pre_refactor':True,'preservation_checks':['sum'],'preservation_inputs':['test_total.py']})
        self.f.data = data
        self.f.plan = self.f.propose(data)
        prepared = self.f.apply('SUM',preservation_only=True)
        refactor = 'def total(values):\n    result = 0\n    for value in values:\n        result += value\n    return result\n'
        paused = self.f.apply('SUM', {'total.py':refactor},pause={'reason':'Controlled segment stop.',
            'completed':['Refactor written.'],'remaining':['Post checks.'],'next_steps':['Continue with original proof.']})
        original = prepared['preservation']['before']
        self.update(self.document(plan='Describe the same original behavior proof.'))
        source = self.f.rows('SELECT result_digest FROM phase_runs WHERE id=?',(paused['run_id'],))[0]
        result = self.f.apply('SUM',continuation={'run_id':paused['run_id'],'result_digest':source['result_digest']})
        self.assertEqual(result['preservation']['before'],original)
        self.assertEqual(len(self.f.rows("SELECT * FROM events WHERE kind='preservation_before_checked'")),1)
        self.assertEqual(self.f.verify('SUM')['status'],'passed')
        self.update(self.document(plan='Keep completed original proof.'))
        self.assertEqual(self.f.task('SUM')['state'],'done')
        self.assertEqual(self.f.apply('REPORT',{'report.py':execution.REPORT})['outcome'],'implemented')
        self.assertEqual(self.f.verify()['status'],'passed')

    def test_archived_and_cancelled_changes_cannot_be_revised(self):
        final = self.complete()
        self.f.close(final)
        with self.assertRaises(EvolveError) as caught:
            self.update(self.document(plan='Attempt to reopen archived work.'))
        self.assertEqual(caught.exception.code,'TERMINAL_CHANGE')

    def test_completed_cli_receipt_can_be_retried_after_task_uuid_changes(self):
        runtime = Path(__file__).resolve().parents[1]/'runtime/evolve.py'
        request = {'authorization':self.f.auth,'input':{'files':[{'path':'total.py','content':execution.SUM,
            'expected_digest':execution.digest((self.f.root/'total.py').read_bytes())}]}}
        def cli():
            result = subprocess.run([sys.executable,'-B',str(runtime),'--project',str(self.f.root),'apply',self.f.plan['change_id'],'--request','-'],
                input=json.dumps(request),text=True,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return json.loads(result.stdout)['data']
        original = cli()
        request.update(original['request_context'])
        request['input'].update(original['input_bindings'])
        self.update(self.document(plan='Clarify plan after completed implementation.'))
        self.assertEqual(cli()['run_id'],original['run_id'])

    def test_metadata_crash_recovers_new_revision_without_replaying_checks_or_tasks(self):
        data = self.document(plan='Clarify the original plan for recovery.')
        proposal = copy.deepcopy(data)
        proposal['presentation'] = {'source':'controlled-revision-fixture','document':{k:v for k,v in proposal.items() if k!='complexity'}}
        request = self.f.request(extra={'reason':'Exercise actual metadata crash.','proposal':proposal})
        child = """import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core.store import Store
from evolve_core.revisions import revise
original=Store.finish
def finish(self,run_id,*args,**kwargs):
    row=self.one('SELECT action FROM phase_runs WHERE id=?',(run_id,))
    if row['action']=='update': os._exit(36)
    return original(self,run_id,*args,**kwargs)
Store.finish=finish
revise(sys.argv[2],json.load(sys.stdin))
"""
        process = subprocess.run([sys.executable,'-B','-c',child,str(Path(__file__).resolve().parents[1]/'runtime'),str(self.f.root)],
            input=json.dumps(request),text=True,capture_output=True,timeout=15)
        self.assertEqual(process.returncode,36,process.stderr)
        self.assertEqual(len(self.f.rows('SELECT * FROM plan_revisions')),2)
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM',{'total.py':execution.SUM})
        self.assertEqual(caught.exception.code,'WRITER_ACTIVE')
        self.assertTrue(current_state(self.f.root,self.f.plan['change_id'])['changes'][0]['plan']['source_pending'])
        from evolve_core.recover import recover
        run = self.f.rows('SELECT id FROM phase_runs WHERE request_id=?',(request['request_id'],))[0]
        operation = self.f.rows('SELECT id FROM operations WHERE run_id=?',(run['id'],))[0]
        recovered = recover(self.f.root, {**self.f.identity(),'authorization':self.f.auth,'input':{'operation_id':operation['id']}})
        self.assertTrue(recovered['original_facts_committed'])
        self.assertFalse(recovered['business_commands_run'])
        self.assertEqual(len(self.f.rows('SELECT * FROM tasks')),4)
        self.assertEqual(self.f.rows('SELECT * FROM evidence'),[])
        self.f.plan['plan_digest'] = self.f.context()[1]['plan_digest']
        self.assertEqual(self.f.apply('SUM',{'total.py':execution.SUM})['outcome'],'implemented')

    def test_real_alpha5_writer_rejects_revision_protocol_without_database_write(self):
        import zipfile
        source = Path(__file__).resolve().parents[1]
        old = self.f.root.parent/(self.f.root.name+'-alpha5')
        self.addCleanup(lambda: __import__('shutil').rmtree(old,ignore_errors=True))
        with zipfile.ZipFile(source/'docs/evidence/imp006/preservation-package-alpha5.zip') as archive:
            archive.extractall(old)
        before = (self.f.root/'evolve/history.db').read_bytes()
        result = subprocess.run([sys.executable,'-B',str(old/'package/runtime/evolve.py'),'--project',str(self.f.root),'apply','--request','-'],
            input=json.dumps({'authorization':self.f.auth,'input':{'change_id':self.f.plan['change_id']}}),text=True,capture_output=True,timeout=15)
        self.assertEqual(json.loads(result.stdout)['error']['code'],'SCHEMA_VERSION')
        self.assertEqual((self.f.root/'evolve/history.db').read_bytes(),before)

    def test_actual_alpha13_writer_rejects_new_pause_protocol_without_database_write(self):
        import zipfile
        source=Path(__file__).resolve().parents[1]
        old=self.f.root.parent/(self.f.root.name+'-alpha13')
        self.addCleanup(lambda: __import__('shutil').rmtree(old,ignore_errors=True))
        with zipfile.ZipFile(source/'docs/evidence/imp006/context-package-alpha13.zip') as archive:
            archive.extractall(old)
        manifest=json.loads((old/'package/evolve-package.json').read_text())
        self.assertEqual((manifest['schema_version'],manifest['protocol_version']),(4,10))
        self.assertEqual(self.f.rows("SELECT value FROM project_meta WHERE key='protocol_version'")[0]['value'],'16')
        before=(self.f.root/'evolve/history.db').read_bytes()
        result=subprocess.run([sys.executable,'-B',str(old/'package/runtime/evolve.py'),'--project',str(self.f.root),'apply','--request','-'],
            input=json.dumps({'authorization':self.f.auth,'input':{'change_id':self.f.plan['change_id']}}),text=True,capture_output=True,timeout=15)
        self.assertEqual(json.loads(result.stdout)['error']['code'],'SCHEMA_VERSION')
        self.assertEqual((self.f.root/'evolve/history.db').read_bytes(),before)

    def test_task_codes_are_not_recycled_after_retirement(self):
        self.complete()
        data = self.document(scope=['total.py'], acceptance=[self.f.data['acceptance'][0]], tasks=[self.f.data['tasks'][0]])
        pending = self.update(data)
        self.update(data,pending['candidate_digest'])
        added = self.document()
        added['tasks'][1]['local_key'] = 'DISPLAY'
        result = self.update(added)
        codes = {t['local_key']:t['task_code'] for t in result['tasks']}
        self.assertEqual(codes['SUM'],'TASK-001')
        self.assertEqual(codes['DISPLAY'],'TASK-003')

    def test_changed_task_cannot_continue_an_old_partial_grant(self):
        paused = self.f.apply('SUM', {'total.py':execution.SUM},pause={'reason':'Controlled stop.',
            'completed':['Source.'],'remaining':['Checks.'],'next_steps':['Continue unchanged definition only.']})
        source = self.f.rows('SELECT result_digest FROM phase_runs WHERE id=?',(paused['run_id'],))[0]
        data = self.document()
        data['tasks'][0]['completion'] += ' New result boundary.'
        revised = self.update(data)
        self.update(data,revised['candidate_digest'])
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM',continuation={'run_id':paused['run_id'],'result_digest':source['result_digest']})
        self.assertEqual(caught.exception.code,'CONTINUATION')

    def test_simple_revision_and_upgrade_preserve_existing_acceptance_and_history(self):
        from evolve_core.plans import propose
        from evolve_core.apply import implement
        from evolve_core.package import digest
        data = {'title':'Simple total','plan':'Correct total with original tests.','completion':'Original literals pass.',
            'scope':['total.py'],'acceptance':[self.f.data['acceptance'][0]['text']],'required_checks':['sum']}
        data['presentation'] = {'source':'controlled-simple-fixture','text':data['plan']}
        simple = propose(self.f.root,{**self.f.identity(),'authorization':self.f.auth,'input':data})
        def request(proposal):
            change = self.f.rows('SELECT * FROM changes WHERE id=?',(simple['change_id'],))[0]
            task = self.f.rows('SELECT * FROM tasks WHERE revision_id=?',(change['current_revision'],))[0]
            return {**self.f.identity(),'authorization':self.f.auth,'expected_versions':{'change':change['row_version'],'task':task['row_version']},
                'input':{'change_id':change['id'],'revision_id':change['current_revision'],'definition_digest':task['definition_digest'],
                    'reason':'Clarify or upgrade the same concrete result.','proposal':proposal}}
        changed = copy.deepcopy(data)
        changed['title'] = 'Readable simple total'
        changed['plan'] = 'Clarify the same total and original tests.'
        changed['presentation']['text'] = changed['plan']
        revised = revise(self.f.root,request(changed))
        self.assertTrue(revised['semantic_same'])
        base = request(changed)
        base['input'] = {k:v for k,v in base['input'].items() if k not in ('reason','proposal')}
        base['input'].update({'accepted_plan_digest':revised['plan_digest'],'files':[{'path':'total.py','content':execution.SUM,
            'expected_digest':digest((self.f.root/'total.py').read_bytes())}]})
        self.assertEqual(implement(self.f.root,base)['outcome'],'implemented')
        structured = self.document()
        structured['presentation'] = {'source':'controlled-upgrade-fixture','document':{k:v for k,v in structured.items() if k!='complexity'}}
        upgraded = revise(self.f.root,request(structured))
        self.assertEqual(upgraded['outcome'],'revised')
        self.assertEqual([t['task_code'] for t in upgraded['tasks']],['TASK-002','TASK-003'])
        revision = self.f.rows('SELECT acceptance_json FROM plan_revisions WHERE id=?',(upgraded['revision_id'],))[0]
        self.assertEqual(json.loads(revision['acceptance_json'])[0]['id'],simple['acceptance'][0]['id'])

    def test_newer_task_failure_outweighs_inherited_whole_pass(self):
        final = self.complete()
        self.update(self.document(plan='Clarify completed task order.'))
        self.assertEqual(self.f.verify('REPORT',failed_ac='report')['status'],'failed')
        with self.assertRaises(EvolveError) as caught:
            self.f.close(final)
        self.assertEqual(caught.exception.code,'VERIFICATION')

    def test_exact_revision_retry_reuses_receipt_after_later_revision(self):
        data = self.document(plan='First prose refinement.')
        proposal = copy.deepcopy(data)
        proposal['presentation'] = {'source':'controlled-revision-fixture','document':{k:v for k,v in proposal.items() if k!='complexity'}}
        request = self.f.request(extra={'reason':'Exercise immutable request replay.','proposal':proposal})
        first = revise(self.f.root,request)
        self.f.plan.update({k:first[k] for k in ('revision_id','plan_digest','definition_digest')})
        self.update(self.document(plan='Second prose refinement.'))
        self.assertEqual(revise(self.f.root,request),first)
        self.assertEqual(len(self.f.rows('SELECT * FROM plan_revisions')),3)

    def test_inherited_actual_failure_can_authorize_same_definition_repair(self):
        self.complete()
        failed = self.f.verify('REPORT',failed_ac='report')
        self.update(self.document(plan='Clarify completed plan after actual failed acceptance.'))
        self.assertEqual(self.f.apply('REPORT',{'report.py':execution.REPORT+'# reinspected public contract\n'},
            reopen_verification_id=failed['verification_id'])['outcome'],'implemented')
        self.assertEqual(self.f.verify()['status'],'passed')

    def test_ordered_shared_file_partial_result_survives_revision_and_continuation(self):
        data = self.document()
        data['tasks'][1]['scope'].append('total.py')
        self.f.data = data
        self.f.plan = self.f.propose(data)
        self.f.complete_sum()
        paused = self.f.apply('REPORT',{'total.py':execution.SUM.replace('sum(values)','sum(values) + 0'),'report.py':execution.REPORT},
            pause={'reason':'Stop shared output segment.','completed':['Report and shared file.'],'remaining':['Checks.'],'next_steps':['Continue original task.']})
        source = self.f.rows('SELECT result_digest FROM phase_runs WHERE id=?',(paused['run_id'],))[0]
        result = self.update(self.document(plan='Clarify the same shared output order.'))
        self.assertEqual([t['state'] for t in result['tasks']],['done','in_progress'])
        self.assertEqual(self.f.apply('REPORT',continuation={'run_id':paused['run_id'],'result_digest':source['result_digest']})['outcome'],'implemented')
        self.assertEqual(self.f.verify()['status'],'passed')

    def test_diagnostic_basis_is_preserved_or_explicitly_listed_for_removal(self):
        import test_diagnostic_workflow as diagnostics
        fixture = diagnostics.DiagnosticWorkflowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.investigate_symptom()
        fixture.plan = fixture.diagnostic_plan()
        task = fixture.rows('SELECT * FROM tasks WHERE id=?',(fixture.plan['task_id'],))[0]
        definition = json.loads(task['definition_json'])
        plan = fixture.rows('SELECT b.content FROM plan_revisions r JOIN blobs b ON b.digest=r.plan_digest WHERE r.id=?',(fixture.plan['revision_id'],))[0]['content'].decode()
        data = {'title':'Readable investigation-backed repair','plan':plan,'completion':definition['completion'],
            'scope':definition['scope'],'acceptance':[a['text'] for a in definition['acceptance']],'required_checks':definition['required_checks'],
            'presentation':{'source':'controlled-diagnostic-revision','text':plan}}
        result = revise(fixture.root,fixture.request({'reason':'Clarify the same repair.','proposal':data}))
        self.assertTrue(result['semantic_same'])
        new_task = result['tasks'][0]['id']
        kept = json.loads(fixture.rows('SELECT definition_json FROM tasks WHERE id=?',(new_task,))[0]['definition_json'])
        self.assertEqual(kept['analysis_basis'],definition['analysis_basis'])
        fixture.plan['task_id'] = new_task
        data['analysis_basis'] = None
        pending = revise(fixture.root,fixture.request({'reason':'Review explicit removal of the original diagnostic criterion.','proposal':data}))
        self.assertEqual(pending['outcome'],'scope_confirmation_required')
        self.assertEqual(pending['candidate']['removed_analysis'],[definition['analysis_basis']])


if __name__ == '__main__':
    unittest.main()
