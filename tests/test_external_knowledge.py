"""Explicit external formal adoption and archived A's obsolete proposals versus B."""
from datetime import datetime, timezone
import json
import subprocess
import sys
import unittest
import zipfile

import test_formal_application as fixture
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.formal import apply_knowledge, verify_knowledge
from evolve_core.knowledge_proposals import propose_knowledge, check_candidate, review_candidates
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.reading import current_state
from evolve_core.recover import recover
from evolve_core.verify import verify
from evolve_core.work import fingerprint


EXTERNAL=fixture.BASE+'\n仅限数值输入。\n'


class ExternalKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.FormalApplicationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.root=self.f.root

    def data(self,*,edits=True,required=False):
        formal=current_state(self.root)['knowledge_refs'][0]
        data={'path':'terms.md','expected_digest':digest(EXTERNAL.encode()),'content':EXTERNAL,
            'presentation':{'source':'controlled-external-content-presentation','text':EXTERNAL},'topic':'external-domain',
            'reason':'Adopt only the actual externally edited numeric domain after specific review.',
            'acceptance':[{'key':'term','text':'The actual external full text states its numeric input scope.'}],
            'adoption':{'formal_version_id':formal['artifact_version_id'],'registered_digest':formal['registered_digest'],
                'source':'controlled-external-observation','observer':'controlled-actual-file-reader','observed_at':datetime.now(timezone.utc).isoformat(),
                'basis':'Read the registered original and actual external bytes; editor identity is unknown.'}}
        if edits:data['edits']=[{'start':len(fixture.BASE.encode()),'end':len(fixture.BASE.encode()),'before':'','after':'\n仅限数值输入。\n','semantic_target':'numeric-domain'}]
        if required:data['delivery']={'role':'required',**{k:self.f.plan[k] for k in ('change_id','revision_id','task_id','definition_digest')},'acceptance_ids':[self.f.plan['acceptance'][0]['id']]}
        return data

    def external(self):
        (self.root/'terms.md').write_text(EXTERNAL)

    def candidate(self,**kwargs):
        return propose_knowledge(self.root,self.f.request(self.data(**kwargs)))

    def test_external_content_is_not_authority_until_checked_approved_and_actually_adopted(self):
        self.external();before=(self.root/'terms.md').stat().st_mtime_ns;old=current_state(self.root)['knowledge_refs'][0]
        item=self.candidate();view=current_state(self.root,item['proposal_id'])['knowledge_proposals'][0]
        self.assertEqual(view['base'],fixture.BASE);self.assertEqual(view['candidate'],EXTERNAL)
        self.assertEqual(current_state(self.root)['knowledge_refs'][0]['confirmation'],'unconfirmed')
        approval=self.f.approve(item);self.assertEqual(current_state(self.root)['knowledge_refs'][0]['artifact_version_id'],old['artifact_version_id'])
        actual=apply_knowledge(self.root,self.f.application_request(item,approval))
        self.assertTrue(actual['adopted_external_bytes']);self.assertFalse(actual['file_bytes_written'])
        self.assertEqual((self.root/'terms.md').stat().st_mtime_ns,before)
        self.assertEqual((self.root/'terms.md').read_text(),EXTERNAL)
        new=current_state(self.root)['knowledge_refs'][0];self.assertEqual(new['confirmation'],'approved_version');self.assertNotEqual(new['artifact_version_id'],old['artifact_version_id'])
        self.assertEqual(verify_knowledge(self.root,self.f.request({'application_id':actual['application_id'],'observations':self.f.observations()}))['status'],'passed')

    def test_observation_without_explicit_adoption_cannot_register_external_authority(self):
        self.external();data=self.data();data.pop('adoption')
        with self.assertRaises(EvolveError) as caught:propose_knowledge(self.root,self.f.request(data))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_EXTERNAL');self.assertEqual(self.f.rows('SELECT * FROM spec_applications'),[])

    def test_adoption_requires_exact_registered_version_and_timezone_observation(self):
        self.external()
        for key,value in [('formal_version_id','not-current'),('registered_digest','0'*64),('observed_at','2026-10-31T12:00:00')]:
            data=self.data();data['adoption'][key]=value
            with self.subTest(key=key),self.assertRaises(EvolveError) as caught:propose_knowledge(self.root,self.f.request(data))
            self.assertEqual(caught.exception.code,'KNOWLEDGE_ADOPTION')

    def test_adoption_is_not_an_implicit_external_rewrite_or_unchanged_registration(self):
        self.external();data=self.data();data['content']=EXTERNAL+'Additional unobserved rewrite.\n';data['presentation']['text']=data['content']
        with self.assertRaises(EvolveError) as caught:propose_knowledge(self.root,self.f.request(data))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_ADOPTION');self.assertEqual((self.root/'terms.md').read_text(),EXTERNAL)
        (self.root/'terms.md').write_text(fixture.BASE);data=self.data();data.update(expected_digest=digest(fixture.BASE.encode()),content=fixture.BASE);data['presentation']['text']=fixture.BASE
        with self.assertRaises(EvolveError) as caught:propose_knowledge(self.root,self.f.request(data))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_ADOPTION')

    def test_adoption_edits_bind_original_formal_bytes_not_external_bytes(self):
        self.external();data=self.data();data['edits'][0]['start']+=1
        with self.assertRaises(EvolveError) as caught:propose_knowledge(self.root,self.f.request(data))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_PATCH')

    def test_later_external_edit_blocks_approval_and_application_without_overwrite(self):
        self.external();item=self.candidate();approval=self.f.approve(item);new=EXTERNAL+'\n第三方再次修改。\n';(self.root/'terms.md').write_text(new)
        with self.assertRaises(EvolveError) as caught:apply_knowledge(self.root,self.f.application_request(item,approval))
        self.assertEqual(caught.exception.code,'FILE_CONFLICT');self.assertEqual((self.root/'terms.md').read_text(),new)
        self.assertEqual(self.f.rows('SELECT * FROM spec_applications'),[])

    def test_adoption_rejects_advanced_authority_even_when_original_external_bytes_return(self):
        self.external();a=self.candidate();aa=self.f.approve(a)
        (self.root/'terms.md').write_text(fixture.BASE)
        b=self.f.proposal(content=fixture.BASE+'\n另一项具体批准的正式含义。\n');bb=self.f.approve(b);apply_knowledge(self.root,self.f.application_request(b,bb))
        self.external()
        with self.assertRaises(EvolveError) as caught:apply_knowledge(self.root,self.f.application_request(a,aa))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_ADOPTION');self.assertEqual(len(self.f.rows('SELECT * FROM spec_applications')),1)

    def test_following_normal_revision_uses_actual_adopted_formal_baseline(self):
        self.external();a=self.candidate();aa=self.f.approve(a);apply_knowledge(self.root,self.f.application_request(a,aa))
        b=self.f.proposal(content=EXTERNAL.replace('计数。','数值之和。'));bb=self.f.approve(b);actual=apply_knowledge(self.root,self.f.application_request(b,bb))
        self.assertEqual(verify_knowledge(self.root,self.f.request({'application_id':actual['application_id'],'observations':self.f.observations()}))['status'],'passed')

    def test_old_independent_approval_continues_only_through_explicit_adoption_chain(self):
        data={'path':'terms.md','content':fixture.BASE.replace('计数。','数值之和。'),'expected_digest':digest(fixture.BASE.encode()),
            'presentation':{'source':'controlled-old-specific-definition','text':fixture.BASE.replace('计数。','数值之和。')},'topic':'sum-definition','reason':'Correct only sum meaning.',
            'acceptance':[{'key':'term','text':'Total means numeric sum.'}],'edits':[{'start':fixture.BASE.encode().index('计数。'.encode()),'end':fixture.BASE.encode().index('计数。'.encode())+len('计数。'.encode()),'before':'计数。','after':'数值之和。','semantic_target':'sum-definition'}]}
        old=propose_knowledge(self.root,self.f.request(data));approval=self.f.approve(old);self.external();adopt=self.candidate()
        check_candidate(self.root,self.f.request({'proposal':self.f.ref(adopt),'observations':self.f.observations()}))
        decision=review_candidates(self.root,self.f.request({'batch':[self.f.ref(old),self.f.ref(adopt)],'decisions':[{'proposal':self.f.ref(adopt),'decision':'approved',
            'source':'controlled-specific-adoption','text':'Approve only the actual external numeric domain.','reason':'The old independent meaning remains specifically approved.'}]}))['decisions'][0]['decision_event_id']
        apply_knowledge(self.root,self.f.application_request(adopt,decision))
        effect=current_state(self.root,old['proposal_id'])['knowledge_proposals'][0]['effective_candidate'];review={k:effect[k] for k in ('base_digest','result_digest','semantic_targets')}
        review.update(status='passed',observer='controlled-actual-composition-reader',basis='The full actual text combines numeric input scope and numeric sum meaning.')
        request=self.f.application_request(old,approval);request['input']['composition_review']=review;apply_knowledge(self.root,request)
        self.assertEqual((self.root/'terms.md').read_text(),EXTERNAL.replace('计数。','数值之和。'))
        self.assertEqual(self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?',(old['proposal_id'],))[0]['approved_event_id'],approval)

    def test_old_whole_candidate_does_not_replace_newly_adopted_external_meaning(self):
        old=self.f.proposal();approval=self.f.approve(old);self.external();a=self.candidate();aa=self.f.approve(a);apply_knowledge(self.root,self.f.application_request(a,aa))
        with self.assertRaises(EvolveError) as caught:apply_knowledge(self.root,self.f.application_request(old,approval))
        self.assertEqual(caught.exception.code,'FILE_CONFLICT');self.assertEqual((self.root/'terms.md').read_text(),EXTERNAL)

    def test_explicit_adoption_batch_does_not_allow_overlapping_old_meaning(self):
        start=fixture.BASE.encode().index('计数。'.encode())
        def data(content,after):
            return {'path':'terms.md','expected_digest':digest(fixture.BASE.encode()),'content':content,
                'presentation':{'source':'controlled-specific-term','text':content},'topic':after,'reason':'Inspect only this exact formal meaning.',
                'acceptance':[{'key':'term','text':'The declared exact meaning is present.'}],
                'edits':[{'start':start,'end':start+len('计数。'.encode()),'before':'计数。','after':after,'semantic_target':'sum-definition'}]}
        old=propose_knowledge(self.root,self.f.request(data(fixture.CANDIDATE,'输入数值之和。')));approval=self.f.approve(old)
        external=fixture.BASE.replace('计数。','有效值总和。');(self.root/'terms.md').write_text(external)
        adoption=data(external,'有效值总和。');adoption['expected_digest']=digest(external.encode());adoption['adoption']=self.data()['adoption']
        new=propose_knowledge(self.root,self.f.request(adoption));check_candidate(self.root,self.f.request({'proposal':self.f.ref(new),'observations':self.f.observations()}))
        decision=review_candidates(self.root,self.f.request({'batch':[self.f.ref(old),self.f.ref(new)],'decisions':[{'proposal':self.f.ref(new),'decision':'approved','source':'controlled-conflicting-new-meaning','text':'Adopt this exact new meaning.','reason':'Keep old conflict visible.'}]}))['decisions'][0]['decision_event_id']
        apply_knowledge(self.root,self.f.application_request(new,decision))
        with self.assertRaises(EvolveError) as caught:apply_knowledge(self.root,self.f.application_request(old,approval))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_CONFLICT');self.assertEqual((self.root/'terms.md').read_text(),external)

    def test_required_external_document_is_actually_adopted_then_independently_verified(self):
        self.external();self.f.document_plan(['terms.md']);item=self.candidate(required=True);approval=self.f.approve(item);actual=apply_knowledge(self.root,self.f.application_request(item,approval,True))
        self.assertTrue(actual['adopted_external_bytes'])
        with self.assertRaises(EvolveError):archive(self.root,self.f.change_request({'verification_id':'not-yet'}))
        verified=self.f.verify_change();self.assertEqual(verified['status'],'passed')
        self.assertEqual(archive(self.root,self.f.change_request({'verification_id':verified['verification_id']}))['outcome'],'archived')

    def crash(self,request,*,metadata=False):
        script="""import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core import formal
from evolve_core.store import Store
from evolve_core.knowledge_proposals import propose_knowledge
def stop(*args,**kwargs):os._exit(int(sys.argv[4]))
if sys.argv[3]=='metadata':Store.finish=stop;propose_knowledge(sys.argv[2],json.load(sys.stdin))
else:formal._commit_application=stop;formal.apply_knowledge(sys.argv[2],json.load(sys.stdin))
"""
        code=61 if metadata else 62
        p=subprocess.run([sys.executable,'-B','-c',script,str(fixture.ROOT/'runtime'),str(self.root),'metadata' if metadata else 'application',str(code)],input=json.dumps(request),text=True,capture_output=True,timeout=15)
        self.assertEqual(p.returncode,code,p.stderr)
        return self.f.rows('SELECT id FROM phase_runs WHERE request_id=?',(request['request_id'],))[0]['id']

    def test_real_adoption_metadata_exit_recovers_without_advancing_formal_version(self):
        self.external();before=current_state(self.root)['knowledge_refs'][0]['artifact_version_id'];run=self.crash(self.f.request(self.data()),metadata=True)
        result=recover(self.root,self.f.request({'run_id':run}));self.assertTrue(result['original_facts_committed'])
        self.assertEqual(current_state(self.root)['knowledge_refs'][0]['artifact_version_id'],before);self.assertEqual((self.root/'terms.md').read_text(),EXTERNAL)

    def test_real_adoption_registration_exit_recovers_facts_without_rewriting_bytes(self):
        self.external();item=self.candidate();approval=self.f.approve(item);mtime=(self.root/'terms.md').stat().st_mtime_ns
        run=self.crash(self.f.application_request(item,approval));result=recover(self.root,self.f.request({'run_id':run}))
        self.assertFalse(result['business_commands_run']);self.assertEqual((self.root/'terms.md').stat().st_mtime_ns,mtime)
        self.assertEqual(len(self.f.rows('SELECT * FROM spec_applications')),1)
        self.assertEqual(verify_knowledge(self.root,self.f.request({'application_id':result['application_id'],'observations':self.f.observations()}))['status'],'passed')

    def archived_a_replaced_by_b(self,decision):
        self.f.auth['effect_kinds'].append('business_files');self.f.auth['paths'].append('policy.py')
        def deliver(value):
            text='Set the declared local policy label to '+value+'.'
            self.f.plan=propose(self.root,self.f.request({'title':'Policy '+value,'plan':text,'completion':text,'scope':['policy.py'],'required_checks':[],
                'acceptance':[text],'presentation':{'source':'controlled-specific-policy-plan','text':text}}))
            request=self.f.change_request({'accepted_plan_digest':self.f.plan['plan_digest'],'files':[{'path':'policy.py','expected_digest':digest((self.root/'policy.py').read_bytes()) if (self.root/'policy.py').exists() else None,'content':'POLICY = '+repr(value)+'\n'}]})
            implement(self.root,request)
            observed=(self.root/'policy.py').read_text();self.assertEqual(observed,'POLICY = '+repr(value)+'\n')
            definition=json.loads(self.f.rows('SELECT definition_json FROM tasks WHERE id=?',(self.f.plan['task_id'],))[0]['definition_json'])
            snapshot=fingerprint(self.root,definition)
            reviews=[{'axis':axis,'observer':'controlled-actual-policy-reader','summary':'Read actual policy literal '+repr(value)+' and unchanged file scope.',
                'findings':[],'fingerprint_digest':snapshot['digest']} for axis in ('spec','standards')]
            reviews[0]['acceptance_results']=[{'ac_id':ac['id'],'status':'passed','basis':'Read actual policy.py text '+repr(observed)+' against the independently declared '+repr(value)+' label.'} for ac in self.f.plan['acceptance']]
            verified=verify(self.root,self.f.change_request({'reviews':reviews}));self.assertEqual(verified['status'],'passed');return verified
        a=deliver('A');aid=self.f.plan['change_id'];archive(self.root,self.f.change_request({'verification_id':a['verification_id']}))
        old=self.f.proposal(content=fixture.BASE+'\nPolicy A。\n',delivery={'role':'followup','change_id':aid},basis={'verification_id':a['verification_id'],'purpose':'Describe actual policy A.'})
        check_candidate(self.root,self.f.request({'proposal':self.f.ref(old),'observations':self.f.observations()}))
        old_decision=review_candidates(self.root,self.f.request({'decisions':[{'proposal':self.f.ref(old),'decision':decision,'source':'controlled-A-specific-decision','text':'Record A exact decision.','reason':'Actual A content review.'}]}))['decisions'][0]['decision_event_id']
        b=deliver('B');bid=self.f.plan['change_id'];new=self.f.proposal(content=fixture.BASE+'\nPolicy B。\n',delivery={'role':'followup','change_id':bid},basis={'verification_id':b['verification_id'],'purpose':'Describe actual newer policy B.'})
        approval=self.f.approve(new);apply_knowledge(self.root,self.f.application_request(new,approval));before=(self.root/'terms.md').read_bytes()
        with self.assertRaises(EvolveError):apply_knowledge(self.root,self.f.application_request(old,old_decision))
        self.assertEqual((self.root/'terms.md').read_bytes(),before)
        view=current_state(self.root,old['proposal_id'])['knowledge_proposals'][0]
        self.assertEqual(view['state'],'superseded');self.assertEqual(view['latest_decision']['decision'],decision)
        self.assertEqual(view['superseded_by'][0]['proposal_id'],new['proposal_id'])
        nav=current_state(self.root,aid)['changes'][0];self.assertEqual(nav['state'],'archived')
        self.assertEqual(nav['knowledge_proposal_refs'][0]['state'],'superseded')
        self.assertEqual(nav['knowledge_proposal_refs'][0]['superseded_by'][0]['proposal_id'],new['proposal_id'])

    def test_archived_a_deferred_proposal_is_discoverably_replaced_by_actual_b(self):self.archived_a_replaced_by_b('deferred')

    def test_archived_a_approved_unapplied_proposal_does_not_overwrite_actual_b(self):self.archived_a_replaced_by_b('approved')

    def test_learn_adopts_exact_external_rule_and_binds_actual_experience(self):
        import test_rule_owner as rule_fixture
        from evolve_core.learning import learn
        rules=rule_fixture.RuleOwnerTests();rules.setUp();self.addCleanup(rules.doCleanups)
        data=rules.data();formal=current_state(rules.root)['knowledge_refs'][0]
        external=data['content'];(rules.root/'terms.md').write_text(external);data['expected_digest']=digest(external.encode())
        data['adoption']={'formal_version_id':formal['artifact_version_id'],'registered_digest':formal['registered_digest'],
            'source':'controlled-actual-rule-observation','observer':'controlled-external-rule-reader','observed_at':datetime.now(timezone.utc).isoformat(),
            'basis':'Read actual external rule and exact retained experience support; editor identity is unknown.'}
        item=learn(rules.root,rules.f.request(data),method='promote');approval=rules.f.approve(item);mtime=(rules.root/'terms.md').stat().st_mtime_ns
        actual=rules.apply(item,approval);self.assertTrue(actual['adopted_external_bytes'])
        self.assertEqual((rules.root/'terms.md').stat().st_mtime_ns,mtime);self.assertEqual(len(rules.f.rows('SELECT * FROM rule_bindings')),1)

    def test_preserved_alpha11_writer_rejects_adoption_protocol_without_mutation(self):
        package=self.root/'old-alpha11'
        with zipfile.ZipFile(fixture.ROOT/'docs/evidence/imp007/rule-owner-package-alpha11.zip') as z:z.extractall(package)
        before=(self.root/'evolve/history.db').read_bytes()
        p=subprocess.run([sys.executable,'-B',str(package/'package/runtime/evolve.py'),'--project',str(self.root),'init','--request','-'],input=json.dumps({'authorization':self.f.auth,'input':{}}),text=True,capture_output=True,timeout=15)
        self.assertEqual(json.loads(p.stdout)['error']['code'],'SCHEMA_VERSION');self.assertEqual((self.root/'evolve/history.db').read_bytes(),before)
