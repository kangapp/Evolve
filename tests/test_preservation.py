"""Actual original checks precede refactor writes and remain original after pauses or recovery."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_structured_execution as fixtures
from evolve_core.apply import implement
from evolve_core.errors import EvolveError
from evolve_core.package import digest
from evolve_core.reading import current_state
from evolve_core.recover import recover
from evolve_core.resume import resume_view


REFACTOR = 'def total(values):\n    result = 0\n    for value in values:\n        result += value\n    return result\n'
PAUSE = {'reason':'Pause this file segment without running checks.','completed':['Refactored total.py.'],
         'remaining':['Run the unchanged behavior checks.'],'next_steps':['Continue the same Task.']}


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.StructuredExecutionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        (self.root/'total.py').write_text(fixtures.SUM)
        self.data = copy.deepcopy(self.f.data)
        self.data['tasks'][0].update({'pre_refactor':True,'preservation_checks':['sum'],'preservation_inputs':['test_total.py']})
        self.f.plan = self.f.propose(self.data)

    def before_events(self):
        return [row for row in self.f.rows("SELECT * FROM events WHERE kind='preservation_before_checked'")
                if json.loads(row['payload_json'])['task_id'] == self.f.task('SUM')['id']]

    def reference(self, result):
        row = self.f.rows('SELECT result_digest FROM phase_runs WHERE id=?',(result['run_id'],))[0]
        return {'run_id':result['run_id'],'result_digest':row['result_digest']}

    def test_before_and_after_checks_are_real_and_whole_completion_uses_the_pair(self):
        original=(self.root/'total.py').read_bytes()
        result=self.f.apply('SUM',{'total.py':REFACTOR})
        self.assertEqual(result['outcome'],'implemented')
        self.assertEqual(result['preservation']['status'],'passed')
        fact=json.loads(self.before_events()[0]['payload_json'])
        self.assertEqual(fact['before_snapshot']['scope']['total.py'],digest(original))
        reference=fact['input_refs']['total.py']
        retained=self.f.rows('SELECT b.content FROM blobs b JOIN artifact_versions v ON v.blob_digest=b.digest WHERE v.id=?',
            (reference['entity_id'],))[0]['content']
        self.assertEqual(retained,original)
        self.assertNotEqual(fact['before_snapshot']['scope']['total.py'],result['fingerprint']['scope']['total.py'])
        self.assertEqual(len(fact['evidence_ids']),1)
        self.assertEqual(len(result['preservation']['after_evidence_ids']),1)
        self.assertNotEqual(fact['evidence_ids'],result['preservation']['after_evidence_ids'])
        self.assertEqual(self.f.verify('SUM')['status'],'passed')
        self.f.apply('REPORT',{'report.py':fixtures.REPORT})
        final=self.f.verify()
        self.assertEqual(final['status'],'passed')
        self.assertEqual(self.f.close(final)['outcome'],'archived')

    def test_no_check_pause_without_original_proof_does_not_write_or_run_checks(self):
        original=(self.root/'total.py').read_bytes()
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM',{'total.py':REFACTOR},pause=PAUSE)
        self.assertEqual(caught.exception.code,'PRESERVATION_REQUIRED')
        self.assertEqual((self.root/'total.py').read_bytes(),original)
        self.assertEqual(self.before_events(),[])
        self.assertEqual(self.f.task('SUM')['state'],'todo')

    def test_prepare_then_pause_and_continue_preserve_the_original_proof_without_new_before_checks(self):
        original=(self.root/'total.py').read_bytes()
        prepared=self.f.apply('SUM',preservation_only=True)
        self.assertEqual(prepared['outcome'],'partial')
        self.assertEqual(prepared['checks'],'before_only')
        self.assertEqual((self.root/'total.py').read_bytes(),original)
        reference=prepared['preservation']['before']
        paused=self.f.apply('SUM',{'total.py':REFACTOR},pause=PAUSE,continuation=self.reference(prepared))
        self.assertEqual(paused['checks'],'not_run')
        self.assertEqual(paused['preservation']['before'],reference)
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        restored=resume_view(self.root,self.f.plan['change_id'])
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        saved=next(t for t in restored['task_contexts'] if t['local_key']=='SUM')['result']
        self.assertEqual(saved['preservation']['before'],reference)
        result=self.f.apply('SUM',continuation=self.reference(paused))
        self.assertEqual(result['outcome'],'implemented')
        self.assertEqual(result['preservation']['before'],reference)
        self.assertEqual(len(self.before_events()),1)
        self.assertEqual(self.f.verify('SUM')['status'],'passed')

    def test_failed_post_check_reuses_original_baseline_when_repairing(self):
        bad='def total(values):\n    return len(values)\n'
        failed=self.f.apply('SUM',{'total.py':bad})
        self.assertEqual(failed['outcome'],'checks_not_passed')
        self.assertEqual(failed['preservation']['status'],'failed')
        reference=failed['preservation']['before']
        fixed=self.f.apply('SUM',{'total.py':REFACTOR},continuation=self.reference(failed))
        self.assertEqual(fixed['outcome'],'implemented')
        self.assertEqual(fixed['preservation']['before'],reference)
        self.assertEqual(len(self.before_events()),1)
        original=self.f.rows('SELECT result_json FROM phase_runs WHERE id=?',(failed['run_id'],))[0]
        self.assertEqual(json.loads(original['result_json'])['outcome'],'checks_not_passed')

    def test_changed_original_input_cannot_be_adopted_by_silently_rerunning_before(self):
        self.f.apply('SUM',preservation_only=True)
        (self.root/'test_total.py').write_text('import unittest\n')
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM',{'total.py':REFACTOR})
        self.assertEqual(caught.exception.code,'DEPENDENCY_NOT_READY')
        self.assertEqual((self.root/'total.py').read_text(),fixtures.SUM)
        self.assertEqual(len(self.before_events()),1)

    def test_preservation_input_alias_cannot_be_overwritten_as_an_output(self):
        (self.root/'total.py').unlink()
        (self.root/'total.py').symlink_to('test_total.py')
        with self.assertRaises(EvolveError) as caught:
            self.f.propose(self.data)
        self.assertEqual(caught.exception.code,'PRESERVATION')

    def test_directory_alias_changed_after_proposal_cannot_overwrite_an_original_input(self):
        for directory in ('implementation','criteria'):
            (self.root/directory).mkdir()
            (self.root/directory/'total.py').write_text(fixtures.SUM)
        (self.root/'current').symlink_to('implementation',target_is_directory=True)
        (self.root/'total.py').write_text('from current.total import total\n')
        data=copy.deepcopy(self.data)
        data['scope']=['current/total.py','report.py']
        data['tasks'][0]['scope']=['current/total.py']
        data['tasks'][0]['context_paths']+=['total.py','criteria/total.py']
        data['tasks'][0]['preservation_inputs'].append('criteria/total.py')
        self.f.auth['paths']=['current/total.py','report.py']
        self.f.plan=self.f.propose(data)
        original=(self.root/'criteria/total.py').read_bytes()
        (self.root/'current').unlink()
        (self.root/'current').symlink_to('criteria',target_is_directory=True)
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM',{'current/total.py':REFACTOR},observations={'current/total.py':digest(original)})
        self.assertEqual(caught.exception.code,'PRESERVATION')
        self.assertEqual((self.root/'criteria/total.py').read_bytes(),original)

    def test_zero_tests_exit_zero_is_not_an_original_behavior_proof(self):
        (self.root/'test_total.py').write_text('')
        self.f.plan=self.f.propose(self.data)
        result=self.f.apply('SUM',{'total.py':REFACTOR})
        self.assertEqual(result['outcome'],'checks_not_passed')
        self.assertEqual(result['preservation']['status'],'before_blocked')
        self.assertFalse(result['business_files_dispatched'])
        self.assertEqual(result['task_checks'][0]['returncode'],0)
        self.assertIn('Ran 0 tests',result['task_checks'][0]['output'])
        self.assertEqual((self.root/'total.py').read_text(),fixtures.SUM)

    def test_next_build_outputs_do_not_invalidate_before_and_after_checks(self):
        test = self.root/'test_total.py'
        test.write_text(test.read_text()+'\nfrom pathlib import Path\n'
            'build = Path(".next")\nbuild.mkdir(exist_ok=True)\n'
            'marker = build/"BUILD_ID"\n'
            'marker.write_text(marker.read_text()+"x" if marker.exists() else "first")\n')
        self.f.plan = self.f.propose(self.data)
        result = self.f.apply('SUM', {'total.py': REFACTOR})
        self.assertEqual(result['outcome'], 'implemented')
        self.assertEqual(result['preservation']['status'], 'passed')
        self.assertEqual((self.root/'.next/BUILD_ID').read_text(), 'firstx')
        self.assertEqual(self.f.verify('SUM')['status'], 'passed')

    def test_explicit_next_context_remains_protected(self):
        from evolve_core.work import fingerprint
        directory = self.root/'.next'
        directory.mkdir()
        marker = directory/'BUILD_ID'
        marker.write_text('original')
        definition = {'scope': [], 'structured': True, 'context': {'.next/BUILD_ID': None},
                      'required_checks': [], 'checks_basis': []}
        before = fingerprint(self.root, definition)
        marker.write_text('changed')
        after = fingerprint(self.root, definition)
        self.assertNotEqual(before['context'], after['context'])
        self.assertNotEqual(before['digest'], after['digest'])

    def test_check_that_changes_its_workspace_cannot_establish_a_before_proof(self):
        original=(self.root/'test_total.py').read_text()
        (self.root/'test_total.py').write_text(original+'\nfrom pathlib import Path\nPath("unexpected.txt").write_text("actual check side effect")\n')
        self.f.plan=self.f.propose(self.data)
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM',{'total.py':REFACTOR})
        self.assertEqual(caught.exception.code,'WORKSPACE_CHANGED')
        self.assertEqual((self.root/'total.py').read_text(),fixtures.SUM)
        self.assertEqual(self.before_events(),[])
        self.assertEqual((self.root/'unexpected.txt').read_text(),'actual check side effect')

    def test_empty_post_suite_does_not_turn_a_real_original_proof_into_completion(self):
        original=(self.root/'test_total.py').read_text()
        (self.root/'test_total.py').write_text(original+'\ndef load_tests(loader, tests, pattern):\n'
            '    from pathlib import Path\n'
            '    return unittest.TestSuite() if "result = 0" in Path("total.py").read_text() else tests\n')
        self.f.plan=self.f.propose(self.data)
        result=self.f.apply('SUM',{'total.py':REFACTOR})
        self.assertEqual(result['outcome'],'checks_not_passed')
        self.assertEqual(result['preservation']['status'],'blocked')
        self.assertEqual(self.f.task('SUM')['state'],'in_progress')
        self.assertEqual(json.loads(self.before_events()[0]['payload_json'])['status'],'passed')

    def test_preparation_rejects_candidate_files_and_does_not_grant_modification_authority(self):
        with self.assertRaises(EvolveError) as caught:
            self.f.apply('SUM',{'total.py':REFACTOR},preservation_only=True)
        self.assertEqual(caught.exception.code,'INPUT')
        self.f.apply('SUM',preservation_only=True)
        request=self.f.request('SUM',{'accepted_plan_digest':self.f.plan['plan_digest'],'files':[]})
        request['authorization']['effect_kinds']=['project_records','checks']
        with self.assertRaises(EvolveError) as caught:
            implement(self.root,request)
        self.assertEqual(caught.exception.code,'AUTHORIZATION')

    def test_original_and_post_checks_run_outside_the_writer_lock_and_sqlite_transaction(self):
        runtime=str(Path(__file__).resolve().parents[1]/'runtime')
        probe='''import json,os,sqlite3,sys,time
from pathlib import Path
sys.path.insert(0,RUNTIME_PATH)
from evolve_core.workspace import writer_lock
from evolve_core.errors import EvolveError
deadline=time.monotonic()+2
while True:
    with sqlite3.connect('file:evolve/history.db?mode=ro',uri=True) as db:
        rows=db.execute("SELECT payload_json FROM events WHERE kind='check_process_started' ORDER BY rowid DESC").fetchall()
    if any(json.loads(row[0]).get('pid')==os.getpid() for row in rows):
        try:
            with writer_lock(Path.cwd()):
                with sqlite3.connect('evolve/history.db',timeout=.2) as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.rollback()
            break
        except EvolveError as error:
            if error.code!='WRITER_ACTIVE': raise
    if time.monotonic()>deadline: raise RuntimeError('check could not acquire its own short writer/SQLite lock')
    time.sleep(.01)
'''.replace('RUNTIME_PATH',repr(runtime))
        test=self.root/'test_total.py'
        test.write_text(probe+'\n'+test.read_text())
        self.f.plan=self.f.propose(self.data)
        self.assertEqual(self.f.apply('SUM',{'total.py':REFACTOR})['outcome'],'implemented')

    def test_reading_formal_context_for_before_proof_does_not_replace_its_approved_version(self):
        from evolve_core.knowledge import propose_baseline, apply_baseline
        content='# Arithmetic contract\nPreserve empty, positive and negative total results.\n'
        auth={**self.f.auth,'effect_kinds':['project_records','knowledge'],'paths':['evolve/contract.md']}
        proposal=propose_baseline(self.root,{**self.f.identity(),'authorization':auth,'input':{
            'path':'evolve/contract.md','expected_digest':None,'content':content,
            'presentation':{'source':'controlled-knowledge-fixture','text':content}}})
        apply_baseline(self.root,{**self.f.identity(),'authorization':auth,'input':{'proposal_id':proposal['proposal_id'],
            'approval':{'proposal_version':proposal['proposal_version'],'candidate_digest':proposal['candidate_digest'],
                'expected_digest':None,'source':'controlled-knowledge-fixture','text':'Approve this exact temporary contract.'}}})
        original=self.f.rows("SELECT * FROM artifacts WHERE path='evolve/contract.md'")[0]
        data=copy.deepcopy(self.data)
        data['tasks'][0]['context_paths'].append('evolve/contract.md')
        self.f.plan=self.f.propose(data)
        self.assertEqual(self.f.apply('SUM',{'total.py':REFACTOR})['outcome'],'implemented')
        self.assertEqual(self.f.rows("SELECT * FROM artifacts WHERE path='evolve/contract.md'")[0],original)
        self.assertEqual((self.root/'evolve/contract.md').read_text(),content)

    def crash(self,target):
        request=self.f.request('SUM',{'accepted_plan_digest':self.f.plan['plan_digest'],'files':[
            {'path':'total.py','content':REFACTOR,'expected_digest':digest((self.root/'total.py').read_bytes())}]})
        child='''
import importlib,json,os,sys
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
app=importlib.import_module('evolve_core.apply')
obj=app.Store if sys.argv[3]=='finish' else app
with patch.object(obj,sys.argv[3],side_effect=lambda *a,**k:os._exit(35)):
    app.implement(Path(sys.argv[2]),json.load(sys.stdin))
'''
        process=subprocess.run([sys.executable,'-B','-c',child,str(Path(__file__).resolve().parents[1]/'runtime'),str(self.root),target],
            input=json.dumps(request),text=True,capture_output=True,timeout=20)
        self.assertEqual(process.returncode,35,process.stdout+process.stderr)
        run=self.f.rows('SELECT id FROM phase_runs WHERE request_id=?',(request['request_id'],))[0]
        operation=self.f.rows('SELECT id FROM operations WHERE run_id=?',(run['id'],))[0]
        return run,operation

    def test_recovery_after_file_commit_keeps_original_before_evidence_and_requires_real_post_checks(self):
        run,operation=self.crash('finish_journal')
        original_event=self.before_events()[0]
        self.assertEqual((self.root/'total.py').read_text(),REFACTOR)
        result=recover(self.root,self.f.request(extra={'operation_id':operation['id']}))
        self.assertFalse(result['business_commands_run'])
        self.assertEqual(result['checks'],'not_run')
        self.assertEqual(self.f.task('SUM')['state'],'in_progress')
        final=self.f.apply('SUM')
        self.assertEqual(final['outcome'],'implemented')
        self.assertEqual(final['preservation']['before'],{'run_id':run['id'],'event_id':original_event['id']})
        self.assertEqual(len(self.before_events()),1)
        self.assertEqual(self.f.verify('SUM')['status'],'passed')

    def test_recovery_after_task_done_preserves_actual_pair_and_completion_without_rerunning_checks(self):
        run,operation=self.crash('finish')
        task=self.f.task('SUM')
        evidence=self.f.rows('SELECT * FROM evidence')
        self.assertEqual(task['state'],'done')
        observed=current_state(self.root,self.f.plan['change_id'])['changes'][0]
        self.assertTrue(any(item['kind']=='behavior_proof' for t in observed['tasks'] if t['local_key']=='SUM' for item in t['readiness']['unmet']))
        recover(self.root,self.f.request(extra={'operation_id':operation['id']}))
        self.assertEqual(self.f.task('SUM'),task)
        self.assertEqual(self.f.rows('SELECT * FROM evidence'),evidence)
        self.assertEqual(self.f.verify('SUM')['status'],'passed')


if __name__=='__main__':
    unittest.main()
