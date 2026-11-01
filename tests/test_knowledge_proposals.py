"""Formal candidate decisions use immutable versions and never imply document writes."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'runtime'))
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.knowledge import propose_baseline,apply_baseline
from evolve_core.knowledge_proposals import propose_knowledge,check_candidate,review_candidates
from evolve_core.package import digest
from evolve_core.reading import current_state
from evolve_core.recover import recover

BASE='# 术语\n\n- 总额：计数。\n'
CANDIDATE='# 术语\n\n- 总额：输入数值之和。\n'


class KnowledgeProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='evolve-formal-candidate-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.auth={'source':'controlled-formal-candidate-fixture','text':'Present and review the exact temporary formal candidates.',
            'effect_kinds':['project_records','knowledge'],'paths':['terms.md','guide.md']}
        self.project=connect(self.root,{'authorization':self.auth,'input':{}})
        self.baseline('terms.md')

    def identity(self):
        return {'project_id':self.project['project_id'],'expected_workspace_epoch':self.project['workspace_epoch']}

    def request(self,data):
        return {**self.identity(),'request_id':str(uuid.uuid4()),'authorization':{**self.auth,'effect_kinds':['project_records']},'input':data}

    def rows(self,sql,values=()):
        with sqlite3.connect(self.root/'evolve/history.db') as database:
            database.row_factory=sqlite3.Row
            return [dict(row) for row in database.execute(sql,values)]

    def baseline(self,path):
        item=propose_baseline(self.root,{**self.identity(),'authorization':self.auth,'input':{'path':path,'content':BASE,'expected_digest':None,
            'presentation':{'source':'controlled-initial-baseline','text':BASE}}})
        apply_baseline(self.root,{**self.identity(),'authorization':self.auth,'input':{'proposal_id':item['proposal_id'],
            'approval':{'proposal_version':item['proposal_version'],'candidate_digest':item['candidate_digest'],'expected_digest':None,
                'source':'controlled-initial-baseline','text':'Approve this exact temporary baseline.'}}})

    def proposal_data(self,content=CANDIDATE,path='terms.md',**extra):
        return {'path':path,'topic':'总额术语','reason':'Align the term with its arithmetic meaning.',
            'expected_digest':digest((self.root/path).read_bytes()),'content':content,
            'presentation':{'source':'controlled-proposal-presentation','text':content},
            'acceptance':[{'key':'term','text':'总额表达输入数值之和。'}],**extra}

    def propose(self,**options):
        return propose_knowledge(self.root,self.request(self.proposal_data(**options)))

    def reference(self,item):
        return {key:item[key] for key in ('proposal_id','proposal_version','candidate_digest','expected_digest')}

    def check(self,item,status='passed'):
        return check_candidate(self.root,self.request({'proposal':self.reference(item),'observations':[
            {'criterion_key':'term','status':status,'observer':'controlled-content-observer',
             'basis':'Inspected the presented full text against the independent wording criterion.'}]}))

    def decision(self,item,value='approved'):
        return {'proposal':self.reference(item),'decision':value,'source':'controlled-exact-candidate-review',
                'text':'Record this exact fixture decision.','reason':'Actual controlled review of the presented candidate.'}

    def review(self,item,value='approved'):
        return review_candidates(self.root,self.request({'decisions':[self.decision(item,value)]}))

    def test_presented_candidate_check_and_approval_do_not_write_formal_target(self):
        item=self.propose();self.check(item);review=self.review(item)
        self.assertEqual(review['decisions'][0]['state'],'approved')
        self.assertFalse(review['formal_files_written'])
        self.assertEqual((self.root/'terms.md').read_text(),BASE)
        view=current_state(self.root,item['proposal_id'])['knowledge_proposals'][0]
        self.assertEqual(view['candidate'],CANDIDATE);self.assertEqual(view['base'],BASE)
        self.assertIsNone(view['applied_operation_id']);self.assertFalse(view['source_pending'])
        self.assertEqual(view['latest_candidate_check']['recorded_status'],'passed')
        self.assertEqual(self.rows("SELECT * FROM verifications"),[])

    def test_same_candidate_adds_context_without_duplicate_versions(self):
        first=self.propose();second=self.propose()
        self.assertEqual(second['outcome'],'proposal_already_present')
        self.assertEqual(second['proposal_id'],first['proposal_id'])
        self.assertEqual(len(self.rows("SELECT * FROM knowledge_proposals WHERE owner_skill='evolve-archive'")),1)

    def test_replacement_preserves_old_content_decision_and_does_not_transfer_approval(self):
        first=self.propose();self.check(first);self.review(first)
        old=self.rows('SELECT * FROM knowledge_proposals WHERE id=?',(first['proposal_id'],))[0]
        second=self.propose(content=CANDIDATE+'\n仅覆盖已声明的数值输入。\n')
        retained=self.rows('SELECT * FROM knowledge_proposals WHERE id=?',(first['proposal_id'],))[0]
        self.assertEqual(retained['state'],'superseded')
        for key in ('candidate_digest','source_json','approved_event_id','version'):
            self.assertEqual(retained[key],old[key])
        new=self.rows('SELECT * FROM knowledge_proposals WHERE id=?',(second['proposal_id'],))[0]
        self.assertEqual(new['version'],2);self.assertIsNone(new['approved_event_id'])
        view=current_state(self.root,first['proposal_id'])['knowledge_proposals'][0]
        self.assertEqual(view['latest_decision']['decision'],'approved')
        with self.assertRaises(EvolveError) as caught: self.review(first)
        self.assertEqual(caught.exception.code,'KNOWLEDGE_STATE')

    def test_approval_requires_latest_actual_matching_content_check(self):
        item=self.propose()
        with self.assertRaises(EvolveError) as caught: self.review(item)
        self.assertEqual(caught.exception.code,'KNOWLEDGE_CHECK')
        self.check(item);self.check(item,'failed')
        with self.assertRaises(EvolveError) as caught: self.review(item)
        self.assertEqual(caught.exception.code,'KNOWLEDGE_CHECK')
        self.check(item);self.assertEqual(self.review(item)['decisions'][0]['state'],'approved')

    def test_rejection_requires_explicit_reconsideration_even_with_a_new_topic(self):
        item=self.propose();self.review(item,'rejected')
        with self.assertRaises(EvolveError) as caught:
            self.propose(topic='换一个标题仍是同一正文')
        self.assertEqual(caught.exception.code,'KNOWLEDGE_REJECTED')
        reconsider={'proposal_id':item['proposal_id'],'proposal_version':item['proposal_version'],
            'source':'controlled-new-review-intent','text':'Reconsider the exact rejected temporary candidate.','reason':'New explicit review intent.'}
        new=self.propose(reconsideration=reconsider)
        self.assertEqual(new['proposal_version'],2)
        self.assertEqual(current_state(self.root,item['proposal_id'])['knowledge_proposals'][0]['latest_decision']['decision'],'rejected')

    def test_deferred_candidate_keeps_reason_and_requires_content_check_before_approval(self):
        item=self.propose();self.review(item,'deferred')
        view=current_state(self.root,item['proposal_id'])['knowledge_proposals'][0]
        self.assertEqual(view['state'],'deferred');self.assertTrue(view['latest_decision']['reason'])
        with self.assertRaises(EvolveError): self.review(item)
        self.check(item);self.review(item)
        self.assertEqual(len(current_state(self.root,item['proposal_id'])['knowledge_proposals'][0]['decisions']),2)

    def test_stale_version_and_external_formal_edit_cannot_be_approved(self):
        item=self.propose();self.check(item)
        bad=self.decision(item);bad['proposal']['proposal_version']+=1
        with self.assertRaises(EvolveError) as caught:
            review_candidates(self.root,self.request({'decisions':[bad]}))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_VERSION')
        (self.root/'terms.md').write_text(BASE+'\n外部新增内容。\n')
        with self.assertRaises(EvolveError) as caught: self.review(item)
        self.assertEqual(caught.exception.code,'FILE_CONFLICT')
        self.assertFalse(current_state(self.root,item['proposal_id'])['knowledge_proposals'][0]['current_matches_baseline'])
        with self.assertRaises(EvolveError) as caught: self.propose()
        self.assertEqual(caught.exception.code,'KNOWLEDGE_EXTERNAL')

    def test_batch_records_individual_approval_and_deferral_without_file_writes(self):
        self.baseline('guide.md');first=self.propose();second=self.propose(path='guide.md')
        self.check(first)
        result=review_candidates(self.root,self.request({'decisions':[self.decision(first),self.decision(second,'deferred')]}))
        self.assertEqual([d['state'] for d in result['decisions']],['approved','deferred'])
        self.assertEqual((self.root/'guide.md').read_text(),BASE)
        self.assertEqual((self.root/'terms.md').read_text(),BASE)

    def test_retry_returns_original_receipt_after_candidate_was_replaced(self):
        item=self.propose();self.check(item)
        request=self.request({'decisions':[self.decision(item)]})
        result=review_candidates(self.root,request)
        self.propose(content=CANDIDATE+'\n新的候选版本。\n')
        self.assertEqual(review_candidates(self.root,request),result)
        changed=copy.deepcopy(request);changed['input']['decisions'][0]['decision']='deferred'
        with self.assertRaises(EvolveError) as caught: review_candidates(self.root,changed)
        self.assertEqual(caught.exception.code,'REQUEST_CONFLICT')

    def test_status_is_pure_and_latest_candidate_check_is_not_applied_verification(self):
        item=self.propose();self.check(item)
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        current_state(self.root,item['code'])
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        evidence=self.rows("SELECT subject_kind FROM evidence WHERE method='candidate-content-review'")
        self.assertEqual(evidence,[{'subject_kind':'candidate'}])
        self.assertEqual(self.rows('SELECT * FROM tasks'),[])

    def test_invalid_criterion_identity_is_rejected_without_leaving_started_work(self):
        item=self.propose()
        for value in ([],[{'criterion_key':['term'],'status':'passed','observer':'x','basis':'x'}]):
            with self.assertRaises(EvolveError):
                check_candidate(self.root,self.request({'proposal':self.reference(item),'observations':value}))
        self.assertEqual(self.rows("SELECT * FROM phase_runs WHERE status='started'"),[])
        self.assertEqual(self.rows('SELECT * FROM resource_claims'),[])

    def test_actual_metadata_exit_recovers_candidate_without_replay_or_formal_write(self):
        request=self.request(self.proposal_data())
        child="""import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core.store import Store
from evolve_core.knowledge_proposals import propose_knowledge
original=Store.finish
def finish(self,run_id,*args,**kwargs):
 if self.one('SELECT action FROM phase_runs WHERE id=?',(run_id,))['action']=='sync': os._exit(41)
 return original(self,run_id,*args,**kwargs)
Store.finish=finish
propose_knowledge(sys.argv[2],json.load(sys.stdin))
"""
        process=subprocess.run([sys.executable,'-B','-c',child,str(ROOT/'runtime'),str(self.root)],input=json.dumps(request),text=True,capture_output=True,timeout=15)
        self.assertEqual(process.returncode,41,process.stderr)
        item=self.rows("SELECT * FROM knowledge_proposals WHERE owner_skill='evolve-archive'")[0]
        self.assertTrue(current_state(self.root,item['id'])['knowledge_proposals'][0]['source_pending'])
        run=self.rows('SELECT id FROM phase_runs WHERE request_id=?',(request['request_id'],))[0]
        recovered=recover(self.root,self.request({'run_id':run['id']}))
        self.assertTrue(recovered['original_facts_committed']);self.assertFalse(recovered['business_commands_run'])
        reference={'proposal_id':item['id'],'proposal_version':item['version'],'candidate_digest':item['candidate_digest'],'expected_digest':item['expected_digest']}
        self.check(reference)
        self.assertFalse(current_state(self.root,item['id'])['knowledge_proposals'][0]['source_pending'])
        self.assertEqual((self.root/'terms.md').read_text(),BASE)
        self.assertEqual(len(self.rows("SELECT * FROM knowledge_proposals WHERE owner_skill='evolve-archive'")),1)

    def test_actual_old_writer_refuses_new_document_protocol_before_formal_application(self):
        item=self.propose();old=self.root/'old-complete-package'
        with zipfile.ZipFile(ROOT/'tests/fixtures/revision-package-alpha6.zip') as archive: archive.extractall(old)
        result=subprocess.run([sys.executable,'-B',str(old/'package/runtime/evolve.py'),'--project',str(self.root),'init','--method','baseline.apply','--request','-'],
            input=json.dumps({'authorization':self.auth,'input':{'proposal_id':item['proposal_id']}}),text=True,capture_output=True,timeout=15)
        self.assertEqual(json.loads(result.stdout)['error']['code'],'SCHEMA_VERSION')
        self.assertEqual((self.root/'terms.md').read_text(),BASE)
        self.assertIsNone(self.rows('SELECT applied_operation_id FROM knowledge_proposals WHERE id=?',(item['proposal_id'],))[0]['applied_operation_id'])

    def test_revisiting_old_body_extends_current_family_head_instead_of_forking_versions(self):
        first=self.propose()
        second=self.propose(content=CANDIDATE+'\n补充输入限制。\n')
        third=self.propose(topic='重新整理旧定义')
        self.assertEqual(third['proposal_version'],3)
        self.assertEqual(third['supersedes'],second['proposal_id'])
        self.assertEqual(self.rows('SELECT state FROM knowledge_proposals WHERE id=?',(second['proposal_id'],))[0]['state'],'superseded')
        first_view=current_state(self.root,first['proposal_id'])['knowledge_proposals'][0]
        third_view=current_state(self.root,third['proposal_id'])['knowledge_proposals'][0]
        self.assertEqual(first_view['definition']['family_id'],third_view['definition']['family_id'])

    def test_superseding_a_rejection_does_not_erase_the_rejected_body_boundary(self):
        first=self.propose();self.review(first,'rejected')
        reconsider={'proposal_id':first['proposal_id'],'proposal_version':first['proposal_version'],
            'source':'controlled-reconsideration','text':'Consider revised wording with an explicit input limit.','reason':'New revised wording.'}
        self.propose(content=CANDIDATE+'\n补充输入限制。\n',reconsideration=reconsider)
        with self.assertRaises(EvolveError) as caught: self.propose(topic='旧正文换个主题')
        self.assertEqual(caught.exception.code,'KNOWLEDGE_REJECTED')

    def test_initial_baseline_presentation_fields_cannot_impersonate_sync_metadata(self):
        propose_baseline(self.root,{**self.identity(),'authorization':self.auth,'input':{'path':'guide.md','content':BASE,'expected_digest':None,
            'presentation':{'source':'controlled-init-presentation','text':BASE,'format':'knowledge-proposal-v1'}}})
        self.assertEqual(current_state(self.root)['knowledge_proposals'],[])

    def test_initial_baselines_and_remaining_delivery_fields_are_not_silently_ignored(self):
        for extra, code in (({'delivery':{'role':'required'}},'KNOWLEDGE_DELIVERY'),({'edits':[]},'KNOWLEDGE_PATCH'),({'rule_sources':[]},'KNOWLEDGE_OWNER')):
            with self.assertRaises(EvolveError) as caught: self.propose(**extra)
            self.assertEqual(caught.exception.code,code)
        data=self.proposal_data(path='terms.md');data['path']='unmapped.md';data['expected_digest']=None
        with self.assertRaises(EvolveError) as caught: propose_knowledge(self.root,self.request(data))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_OWNER')


if __name__=='__main__': unittest.main()
