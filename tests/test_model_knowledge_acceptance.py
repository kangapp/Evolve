"""Nine real runtime stages exercise the native knowledge parent, without models."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_formal_application as fixture
sys.path.insert(0,str(fixture.ROOT/'scripts'))
from model_acceptance import installation_roots
from model_knowledge_checks import FIRST_FILES,GUIDE,GUIDE_A,GUIDE_B,RULE,EXTERNAL,NOTE_A,NOTE_B,PROMPTS,KnowledgeChecks,scope_for
from evolve_core.apply import implement
from evolve_core.archive import archive
from evolve_core.connect import connect
from evolve_core.errors import EvolveError
from evolve_core.formal import apply_knowledge,verify_knowledge
from evolve_core.knowledge import propose_baseline,apply_baseline
from evolve_core.knowledge_proposals import propose_knowledge,check_candidate,review_candidates
from evolve_core.learning import learn,search
from evolve_core.package import check_package,digest
from evolve_core.plans import propose
from evolve_core.reading import current_state
from evolve_core.structured import document,whole_definition
from evolve_core.verify import verify
from evolve_core.work import fingerprint


class KnowledgeParentFixture:
    def __init__(self,lab):
        self.lab=lab;self.root=lab/'business';self.root.mkdir();self.evidence=lab/'evidence';self.evidence.mkdir()
        for name,body in FIRST_FILES.items():(self.root/name).write_text(body)
        self.package=self.root/'.agents/evolve-acceptance/package';self.package.mkdir(parents=True)
        manifest=check_package()
        # Unit fixture copies the checked source resource set. Actual native preparation
        # separately installs the frozen rendered distribution through both hosts.
        for name in [*manifest['files'],'evolve-package.json']:
            target=self.package/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(fixture.ROOT/name,target)
        self.registered_root=self.root/'.agents/evolve-acceptance/registered';shutil.copytree(self.package,self.registered_root)
        self.scope=scope_for(manifest,'codex',None,fixture.ROOT/'scripts/model_acceptance.py')
        self.checker=KnowledgeChecks(self.root,self.scope,self.evidence,package=self.package,registered_root=self.registered_root)
        self.f=fixture.FormalApplicationTests();self.f.root=self.root
        self.f.auth={'source':'controlled-native-parent-without-models','text':'Exercise these exact temporary scope boundaries with controlled observations.',
            'effect_kinds':['project_records','knowledge','business_files','checks'],'paths':['policy.py','guide.md']}
        self.plans={};self.candidates={};self.approvals={};self.results={};self.observations=[]

    def select(self,name,key=None):
        self.f.plan=copy.deepcopy(self.plans[name])
        if self.f.plan.get('tasks'):
            task=next(t for t in self.f.plan['tasks'] if t['local_key']==key) if key else self.f.plan['tasks'][0]
            self.f.plan.update(task_id=task['id'],definition_digest=task['definition_digest'])

    def content_observations(self):
        return [{'criterion_key':'term','status':'passed','observer':'controlled-actual-label-document-reader','basis':'Read the actual complete candidate or applied text against its declared label, rule and scope.'}]

    def check(self,item):return check_candidate(self.root,self.f.request({'proposal':self.f.ref(item),'observations':self.content_observations()}))

    def approve(self,item):
        self.check(item)
        return review_candidates(self.root,self.f.request({'decisions':[{'proposal':self.f.ref(item),'decision':'approved','source':'controlled-specific-content-acceptance',
            'text':'Approve only this presented exact candidate and original baseline.','reason':'Read actual full content and declared scope.'}]}))['decisions'][0]['decision_event_id']

    def verify(self,name,key=None):
        self.select(name,key);change=self.f.rows('SELECT * FROM changes WHERE id=?',(self.f.plan['change_id'],))[0]
        whole=change['complexity']=='complex' and key is None
        request=self.f.change_request({},whole)
        if whole:
            with fixture.sqlite3.connect(self.root/'evolve/history.db') as c:
                c.row_factory=fixture.sqlite3.Row
                revision=c.execute('SELECT * FROM plan_revisions WHERE id=?',(change['current_revision'],)).fetchone()
                definition=whole_definition(revision,c.execute('SELECT * FROM tasks WHERE revision_id=?',(revision['id'],)).fetchall())
        else:definition=json.loads(self.f.rows('SELECT definition_json FROM tasks WHERE id=?',(self.f.plan['task_id'],))[0]['definition_json'])
        snapshot=fingerprint(self.root,definition)
        reviews=[{'axis':axis,'observer':'controlled-actual-label-and-document-observer','summary':'Read actual declared label/document scope and actual independent literal command results.',
            'findings':[],'fingerprint_digest':snapshot['digest']} for axis in ('spec','standards')]
        reviews[0]['acceptance_results']=[{'ac_id':a['id'],'status':'passed','basis':'Actual declared file and applicable independent command satisfy: '+a['text']} for a in definition['acceptance']]
        request['input']['reviews']=reviews;return verify(self.root,request)

    def delivery(self,name,key):
        self.select(name,key)
        ids=[a['id'] for a in self.f.plan['acceptance'] if not key or a['key']==key]
        return {'role':'required',**{k:self.f.plan[k] for k in ('change_id','revision_id','task_id','definition_digest')},'acceptance_ids':ids}

    def data(self,content,topic,*,edits=None,delivery=None,basis=None):
        result={'path':'guide.md','content':content,'expected_digest':digest((self.root/'guide.md').read_bytes()),'topic':topic,'reason':'Deliver only the specifically declared bounded meaning.',
            'presentation':{'source':'controlled-full-content-presentation','text':content},'acceptance':[{'key':'term','text':'The declared exact content and scope are present.'}]}
        if edits:result['edits']=edits
        if delivery:result['delivery']=delivery
        if basis:result['implementation_basis']={'verification_id':basis['verification_id'],'purpose':'Reflect the actual applicable policy result.'}
        return result

    def edit(self,base,before,after,target):
        start=base.encode().index(before.encode()) if before else len(base.encode())
        return {'start':start,'end':start+len(before.encode()),'before':before,'after':after,'semantic_target':target}

    def apply_doc(self,item,approval,*,name=None,key=None,owner='sync'):
        if name:self.select(name,key)
        request=self.f.application_request(item,approval,bool(name))
        effective=current_state(self.root,item['proposal_id'])['knowledge_proposals'][0]['effective_candidate']
        if effective['chain']:
            review={k:effective[k] for k in ('base_digest','result_digest','semantic_targets')};review.update(status='passed',observer='controlled-actual-composition-observer',basis='Read full actual composed text and both independently approved meanings.')
            request['input']['composition_review']=review
        if owner=='learn':request['input']['stage']='apply';return learn(self.root,request,method='promote')
        return apply_knowledge(self.root,request)

    def simple(self,name,owner,scope,checks):
        text='Deliver the declared '+name+' result through '+owner+'.'
        self.plans[name]=propose(self.root,self.f.request({'title':name,'plan':text,'completion':text,'scope':scope,'required_checks':checks,
            'responsible_action':owner,'acceptance':[text],'presentation':{'source':'controlled-complete-specific-plan','text':text}}))
        self.select(name)

    def run(self,case):
        self.checker.before(case)
        if case=='baseline':
            checks=[{'id':'policy_'+value.lower(),'argv':[sys.executable,'-B','-m','unittest','test_policy_'+value.lower(),'-v'],'cwd':'.','timeout':10} for value in ('A','B')]
            self.f.project=connect(self.root,{'authorization':self.f.auth,'input':{'checks':checks}})
            self.simple('initial-guide','init',['guide.md'],[])
            d=self.data(GUIDE,'initial-guide');d['delivery']={'role':'required',**{k:self.f.plan[k] for k in ('change_id','revision_id','task_id','definition_digest')},'acceptance_ids':[self.f.plan['acceptance'][0]['id']]}
            item=propose_baseline(self.root,self.f.request(d));approval=self.approve(item)
            apply_baseline(self.root,self.f.application_request(item,approval,True))
            v=self.verify('initial-guide');archive(self.root,self.f.change_request({'verification_id':v['verification_id']}))
        elif case=='deliver_a':
            d={'complexity':'complex','title':'标签 A 与正式约定','plan':'Implement A then specifically approved formal specification and review rule.',
                'completion':'All A code, formal specification and rule results are actually accepted.','scope':['policy.py','guide.md'],'required_checks':['policy_a'],
                'acceptance':[{'key':key,'text':text} for key,text in [('CODE','POLICY equals A and its independent literal passes.'),('SPEC','Formal label is A.'),('RULES','Formal rule states current-phase independent literal review and scope.')]],
                'spec':{'problem':'No actual A policy or specific formal review rule.','goals':['Deliver the declared actual A results.'],'non_goals':[],
                    'behavior':['Keep separate owner and acceptance facts.'],'constraints':['Read-only independent tests.'],'tradeoffs':[],
                    'test_decisions':['Run only the applicable stage literal and inspect actual formal content.'],'open_questions':[]},'tasks':[]}
            for index,(key,owner) in enumerate([('CODE','apply'),('SPEC','sync'),('RULES','learn')]):
                d['tasks'].append({'local_key':key,'title':key,'completion':d['acceptance'][index]['text'],'validation':'Actual literal command or declared content observation.',
                    'scope':['policy.py'] if key=='CODE' else ['guide.md'],'required_checks':['policy_a'] if key=='CODE' else [],'responsible_action':owner,'acceptance':[key],
                    'context_paths':['test_policy_a.py'] if key=='CODE' else [],'exclusions':[],'test_decision_refs':['spec.test_decisions/0'],
                    'dependencies':[] if index==0 else [{'upstream_task':('CODE','SPEC')[index-1],'condition_kind':'verification_passed','basis':'The actual preceding result must be accepted.'}]})
            d['presentation']={'source':'controlled-full-owner-plan','document':document(d)};self.plans['A']=propose(self.root,self.f.request(d));self.select('A','CODE')
            implement(self.root,self.f.change_request({'accepted_plan_digest':self.f.plan['plan_digest'],'files':[{'path':'policy.py','expected_digest':digest((self.root/'policy.py').read_bytes()),'content':'POLICY = "A"\n'}]}))
            self.code_ver=self.verify('A','CODE');row=self.f.rows('SELECT * FROM phase_runs WHERE id=?',(self.code_ver['run_id'],))[0]
            evidence=[r['id'] for r in self.f.rows('SELECT id FROM evidence WHERE source_run_id=?',(row['id'],))]
            learn(self.root,self.f.request({'experience':{'topic':'标签交付核查','problem':'The local label needs the current-stage literal criterion.',
                'cause':{'statement':'Observed actual correction from unset to A and the independent A literal passing.','confidence':'observed'},'advice':RULE,
                'applicability':'Only this temporary project label delivery.','version_context':'Controlled A fixture.','observer':'controlled-actual-work-reader','scope':['临时项目标签交付'],
                'exclusions':['No universal causal benefit.'],'tags':['标签'],'limitations':['Only a bounded actual A example supports this observation.']},
                'sources':[{'run_id':row['id'],'result_digest':row['result_digest'],'evidence_ids':evidence}]}),method='record')
            self.experience=search(self.root,'标签交付核查')['results'][0]
        elif case=='candidates':
            da=self.data(GUIDE.replace('待定。','A。'),'policy-spec-a',edits=[self.edit(GUIDE,'待定。','A。','policy-label')],delivery=self.delivery('A','SPEC'),basis=self.code_ver)
            self.candidates['spec']=propose_knowledge(self.root,self.f.request(da))
            dr=self.data(GUIDE.replace('尚无。',RULE),'label-review-rule',edits=[self.edit(GUIDE,'尚无。',RULE,'label-review-rule')],delivery=self.delivery('A','RULES'))
            dr.update(stage='propose',rule_scope=['临时项目标签交付核查'],rule_sources=[{'experience_ref':self.experience['experience_ref'],'state_ref':self.experience['state_ref'],'counterexamples':[],'basis':'Read actual A work, its independent literal evidence and bounded applicability.'}])
            self.candidates['rule']=learn(self.root,self.f.request(dr),method='promote')
            note=self.data(GUIDE+NOTE_A,'policy-note',edits=[self.edit(GUIDE,'',NOTE_A,'policy-note')],delivery={'role':'followup','change_id':self.plans['A']['change_id']},basis=self.code_ver)
            self.candidates['old-note']=propose_knowledge(self.root,self.f.request(note))
            for item in self.candidates.values():self.check(item)
        elif case=='decisions':
            items=list(self.candidates.items());decisions=review_candidates(self.root,self.f.request({'batch':[self.f.ref(v) for _,v in items],
                'decisions':[{'proposal':self.f.ref(item),'decision':'deferred' if key=='old-note' else 'approved','source':'controlled-specific-three-item-user-decisions',
                    'text':'Approve this exact candidate only, or defer the actual old A note.','reason':'Read exact content and original scope.'} for key,item in items]}))['decisions']
            self.approvals={key:r['decision_event_id'] for (key,_),r in zip(items,decisions)}
        elif case=='finish_a':
            self.apply_doc(self.candidates['spec'],self.approvals['spec'],name='A',key='SPEC');self.verify('A','SPEC')
            self.apply_doc(self.candidates['rule'],self.approvals['rule'],name='A',key='RULES',owner='learn');self.verify('A','RULES')
            v=self.verify('A');archive(self.root,self.f.change_request({'verification_id':v['verification_id']},whole=True))
        elif case=='adopt_external':
            self.simple('external-guide','sync',['guide.md'],[]);formal=current_state(self.root)['knowledge_refs'][0]
            d=self.data(GUIDE_A+EXTERNAL,'external-scope',edits=[self.edit(GUIDE_A,'',EXTERNAL,'external-scope')])
            d['delivery']={'role':'required',**{k:self.f.plan[k] for k in ('change_id','revision_id','task_id','definition_digest')},'acceptance_ids':[self.f.plan['acceptance'][0]['id']]}
            d['adoption']={'formal_version_id':formal['artifact_version_id'],'registered_digest':formal['registered_digest'],'source':'controlled-parent-actual-edit',
                'observer':'controlled-actual-external-content-reader','observed_at':datetime.now(timezone.utc).isoformat(),'basis':'Read actual externally appended exact scope; editor identity unknown.'}
            item=propose_knowledge(self.root,self.f.request(d));approval=self.approve(item);self.apply_doc(item,approval,name='external-guide')
            v=self.verify('external-guide');archive(self.root,self.f.change_request({'verification_id':v['verification_id']}))
        elif case=='deliver_b':
            self.simple('B','apply',['policy.py'],['policy_b'])
            implement(self.root,self.f.change_request({'accepted_plan_digest':self.f.plan['plan_digest'],'files':[{'path':'policy.py','expected_digest':digest((self.root/'policy.py').read_bytes()),'content':'POLICY = "B"\n'}]}))
            bv=self.verify('B');base=GUIDE_A+EXTERNAL
            d=self.data(GUIDE_B,'policy-note',edits=[self.edit(base,'当前标签：A。','当前标签：B。','policy-label'),self.edit(base,'',NOTE_B,'policy-note')],
                delivery={'role':'followup','change_id':self.plans['B']['change_id']},basis=bv)
            self.candidates['new-note']=propose_knowledge(self.root,self.f.request(d));self.check(self.candidates['new-note'])
        elif case=='finish_b':
            item=self.candidates['new-note'];approval=self.approve(item);self.results['B']=self.apply_doc(item,approval)
            verify_knowledge(self.root,self.f.request({'application_id':self.results['B']['application_id'],'observations':self.content_observations()}))
            v=self.verify('B');archive(self.root,self.f.change_request({'verification_id':v['verification_id']}))
        elif case=='verify':
            verify_knowledge(self.root,self.f.request({'application_id':self.results['B']['application_id'],'observations':self.content_observations()}))
        result=self.checker.after(case);self.observations.append(result);return result

    def through(self,last):
        for case in list(PROMPTS)[self.checker.next_case:]:
            self.run(case)
            if case==last:break


class KnowledgeModelParentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='evolve-knowledge-parent-');self.addCleanup(self.temp.cleanup)
        self.lab=Path(self.temp.name).resolve();self.driver=KnowledgeParentFixture(self.lab)

    def test_all_nine_actual_parent_boundaries_pass_without_model_transport(self):
        self.driver.through('verify');self.assertEqual(len(self.driver.observations),9)
        self.assertTrue(all(r['passed_parent_checks'] for r in self.driver.observations))

    def test_parent_rejects_readonly_test_mutation(self):
        d=self.driver;d.through('baseline');d.checker.before('deliver_a');(d.root/'test_policy_a.py').write_text('')
        with self.assertRaises(AssertionError):d.checker.after('deliver_a')

    def test_parent_rejects_installation_alias_or_resource_change(self):
        d=self.driver;d.through('baseline');d.checker.before('deliver_a');(d.package/'shared/contract.md').write_text('changed')
        with self.assertRaises(EvolveError) as caught:d.checker.after('deliver_a')
        self.assertEqual(caught.exception.code,'PACKAGE_INCOMPLETE')

    def test_parent_rejects_check_configuration_replacement(self):
        d=self.driver;d.through('baseline');d.checker.before('deliver_a');path=d.root/'evolve/config.toml'
        path.write_text(path.read_text().replace('test_policy_a','unrelated_module'))
        with self.assertRaises(AssertionError):d.checker.after('deliver_a')

    def test_parent_also_protects_registered_source_when_host_cache_is_unchanged(self):
        d=self.driver;d.through('baseline');d.checker.before('deliver_a');(d.registered_root/'shared/contract.md').write_text('changed')
        with self.assertRaises(EvolveError) as caught:d.checker.after('deliver_a')
        self.assertEqual(caught.exception.code,'PACKAGE_INCOMPLETE')

    def test_parent_rejects_rewritten_prior_verification(self):
        d=self.driver;d.through('baseline');d.checker.before('deliver_a')
        with fixture.sqlite3.connect(d.root/'evolve/history.db') as c:c.execute("UPDATE verifications SET status='failed'")
        with self.assertRaises(AssertionError):d.checker.after('deliver_a')

    def test_parent_rejects_skipped_or_repeated_case_boundaries(self):
        with self.assertRaises(AssertionError):self.driver.checker.before('deliver_b')
        self.driver.through('baseline')
        with self.assertRaises(AssertionError):self.driver.checker.before('baseline')

    def test_parent_rejects_formal_write_in_decision_only_stage(self):
        d=self.driver;d.through('candidates');d.checker.before('decisions');(d.root/'guide.md').write_text(GUIDE_A)
        with self.assertRaises(AssertionError):d.checker.after('decisions')

    def test_source_scope_pins_four_files_nine_sessions_and_inside_project_layout(self):
        scope=self.driver.scope
        self.assertEqual(len(scope['first_files']),4);self.assertEqual(scope['maximum_sessions'],9)
        roots=installation_roots(self.lab/'new',knowledge=True)
        for path in roots[2:]:path.relative_to(roots[0])
        wrong=copy.deepcopy(check_package());wrong['protocol_version']=9
        with self.assertRaises(ValueError):scope_for(wrong,'codex',None,fixture.ROOT/'scripts/model_acceptance.py')
        with self.assertRaises(ValueError):scope_for(check_package(),'claude','unselected-model',fixture.ROOT/'scripts/model_acceptance.py')

    def run_cli(self,*args):
        return subprocess.run([sys.executable,'-B',str(fixture.ROOT/'scripts/model_acceptance.py'),'--host','codex','--package',str(fixture.ROOT),
            '--knowledge','--out',str(self.lab/'must-not-exist'),*args],text=True,capture_output=True,timeout=15)

    def test_actual_readonly_preflight_does_not_create_profile_or_dispatch_models(self):
        p=self.run_cli('--preflight-only');self.assertEqual(p.returncode,0,p.stderr)
        result=json.loads(p.stdout);self.assertFalse(result['model_requests_sent']);self.assertFalse(result['host_profile_created'])
        self.assertEqual(result['expanded_scope']['slice'],'IMP-007');self.assertFalse((self.lab/'must-not-exist').exists())

    def test_actual_dispatch_rejects_missing_authorization_or_wrong_scope_before_install(self):
        for extra in ([],['--authorization-text','controlled test does not authorize real models','--expected-scope-digest','incorrect']):
            p=self.run_cli(*extra);self.assertNotEqual(p.returncode,0);self.assertFalse((self.lab/'must-not-exist').exists())
