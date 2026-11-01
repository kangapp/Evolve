"""Actual work evidence feeds specifically approved Learn rules and real file outputs."""
import copy
import json
import subprocess
import sys
import unittest
import zipfile
from unittest.mock import patch

import test_formal_application as formal_fixture
import test_learning as learning_fixture
from evolve_core.archive import archive
from evolve_core.errors import EvolveError
from evolve_core.formal import apply_knowledge, verify_knowledge
from evolve_core.knowledge_proposals import check_candidate, propose_knowledge, review_candidates
from evolve_core.learning import learn, search
from evolve_core.package import digest
from evolve_core.plans import propose
from evolve_core.reading import current_state
from evolve_core.recover import recover


RULE = '\n核对整数求和时使用独立字面量样例，注明观察范围。\n'


class RuleOwnerTests(unittest.TestCase):
    def setUp(self):
        self.l = learning_fixture.LearningTests(); self.l.setUp(); self.addCleanup(self.l.doCleanups)
        self.l.produce(); self.root = self.l.root
        self.f = formal_fixture.FormalApplicationTests()
        self.f.root, self.f.project, self.f.plan = self.root, self.l.project, None
        self.f.auth = copy.deepcopy(self.l.auth); self.f.auth['effect_kinds'].append('knowledge'); self.f.auth['paths'].append('terms.md')
        self.f.baseline('terms.md')

    def sources(self):
        item = search(self.root, 'arithmetic')['results'][0]
        return [{'experience_ref': item['experience_ref'], 'state_ref': item['state_ref'],
                 'counterexamples': [f['feedback_ref'] for f in item['counterexamples']],
                 'basis': 'Read the actual failed and passed literal checks; this is a scoped review rule, not an expanded numeric guarantee.'}]

    def data(self, *, required=False):
        base = (self.root / 'terms.md').read_bytes()
        data = {'stage': 'propose', 'path': 'terms.md', 'expected_digest': digest(base), 'content': base.decode()+RULE,
                'presentation': {'source': 'controlled-full-rule-candidate', 'text': base.decode()+RULE}, 'topic': 'literal-check-rule',
                'reason': 'Capture the supported bounded review practice.', 'acceptance': [{'key': 'term', 'text': 'Review uses independent literal examples and states its scope.'}],
                'rule_scope': ['local integer arithmetic review'], 'rule_sources': self.sources(),
                'edits': [{'start': len(base), 'end': len(base), 'before': '', 'after': RULE, 'semantic_target': 'literal-review-rule'}]}
        if required:
            data['delivery'] = {'role': 'required', **{k: self.f.plan[k] for k in ('change_id','revision_id','task_id','definition_digest')},
                                'acceptance_ids': [self.f.plan['acceptance'][0]['id']]}
        return data

    def candidate(self, **kwargs):
        return learn(self.root, self.f.request(self.data(**kwargs)), method='promote')

    def apply(self, item, approval, required=False, **extra):
        request = self.f.application_request(item, approval, required)
        request['input'].update(stage='apply', **extra)
        return learn(self.root, request, method='promote')

    def counterexample(self):
        self.l.second_task(); decision = self.l.decide(); self.l.give_feedback(decision, 'counterexample')

    def required_plan(self):
        plan = 'Deliver only the specifically approved scoped literal-review rule through learn, then inspect actual wording.'
        self.f.plan = propose(self.root,self.f.request({'title':'必需规则交付','plan':plan,'completion':'Actual rule states its bounded review practice.',
            'scope':['terms.md'],'required_checks':[],'responsible_action':'learn','acceptance':['Actual rule states independent literal examples and scope.'],
            'presentation':{'source':'controlled-rule-task','text':plan}}))

    def test_specific_rule_proposal_application_and_binding_do_not_promote_experience_state(self):
        before = (self.root/'terms.md').read_bytes(); item = self.candidate()
        self.assertEqual((self.root/'terms.md').read_bytes(), before)
        approval = self.f.approve(item); self.assertEqual((self.root/'terms.md').read_bytes(), before)
        actual = self.apply(item, approval)
        self.assertEqual((self.root/'terms.md').read_text(), before.decode()+RULE)
        binding = self.f.rows('SELECT * FROM rule_bindings')[0]
        self.assertEqual(binding['application_id'], actual['application_id'])
        self.assertEqual(binding['artifact_version_id'], actual['artifact']['entity_id'])
        self.assertEqual(json.loads(binding['sources_json']), self.sources())
        self.assertEqual(self.f.rows('SELECT action,method,owner_skill FROM phase_runs WHERE id=?',(actual['run_id'],))[0],
                         {'action':'learn','method':'promote','owner_skill':'evolve-learn'})
        self.assertEqual(verify_knowledge(self.root, self.f.request({'application_id':actual['application_id'],'observations':self.f.observations()}))['status'],'passed')
        entry = search(self.root,'arithmetic')['results'][0]
        self.assertEqual(entry['state'],'candidate'); self.assertFalse(entry['formal_rule']); self.assertFalse(entry['modification_authorization'])
        before_query = self.l.snapshot(); view = current_state(self.root, item['proposal_id'])
        self.assertEqual(view['knowledge_proposals'][0]['rule_state']['applicability'],'supported_basis')
        self.assertEqual(view['knowledge_refs'][0]['rule_bindings'][0]['application_id'],actual['application_id'])
        self.assertEqual(self.l.snapshot(),before_query)

    def test_required_rule_task_needs_actual_application_and_target_acceptance(self):
        self.required_plan()
        item = self.candidate(required=True); approval = self.f.approve(item); self.apply(item,approval,True)
        with self.assertRaises(EvolveError) as caught: archive(self.root,self.f.change_request({'verification_id':'not-yet'}))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_VERIFICATION')
        verified = self.f.verify_change(); self.assertEqual(verified['status'],'passed')
        self.assertEqual(archive(self.root,self.f.change_request({'verification_id':verified['verification_id']}))['outcome'],'archived')

    def test_counterexample_invalidates_required_rule_completion_but_keeps_actual_history(self):
        self.required_plan();item=self.candidate(required=True);approval=self.f.approve(item);self.apply(item,approval,True)
        verified=self.f.verify_change();self.assertEqual(verified['status'],'passed')
        before=(self.root/'terms.md').read_bytes();self.counterexample()
        with self.assertRaises(EvolveError) as caught:archive(self.root,self.f.change_request({'verification_id':verified['verification_id']}))
        self.assertEqual(caught.exception.code,'INCOMPLETE_TASK')
        self.assertEqual(self.f.rows('SELECT status FROM verifications WHERE id=?',(verified['verification_id'],))[0]['status'],'passed')
        self.assertEqual((self.root/'terms.md').read_bytes(),before);self.assertEqual(len(self.f.rows('SELECT * FROM rule_bindings')),1)

    def test_sync_and_learn_same_original_base_complete_required_tasks_by_real_chain(self):
        data={'complexity':'complex','title':'术语与规则','plan':'Sync defines numeric sum, then Learn delivers the independent bounded review rule.',
            'completion':'Both formal meanings are applied and accepted.','scope':['terms.md'],'required_checks':[],
            'acceptance':[{'key':'DOC','text':'Total means numeric sum.'},{'key':'RULE','text':'Review uses independent literal examples and states scope.'}],
            'spec':{'problem':'Formal definition and bounded review practice are missing.','goals':['Deliver both approved meanings.'],'non_goals':[],
                'behavior':['Keep independent owner scopes.'],'constraints':['No automatic rule authority from experience.'],'tradeoffs':[],
                'test_decisions':['Read actual full formal text and inspect existing work evidence.'],'open_questions':[]},'tasks':[]}
        for key,owner in [('DOC','sync'),('RULE','learn')]:
            data['tasks'].append({'local_key':key,'title':key,'completion':data['acceptance'][len(data['tasks'])]['text'],'validation':'Read actual declared content.',
                'scope':['terms.md'],'required_checks':[],'responsible_action':owner,'acceptance':[key],'context_paths':[],'exclusions':[],
                'test_decision_refs':['spec.test_decisions/0'],'dependencies':[] if key=='DOC' else [{'upstream_task':'DOC','condition_kind':'verification_passed','basis':'Establish the actual numeric meaning first.'}]})
        from evolve_core.structured import document
        data['presentation']={'source':'controlled-complete-two-owner-plan','document':document(data)}
        self.f.plan=propose(self.root,self.f.request(data));tasks=self.f.plan['tasks']
        def select(index):self.f.plan.update(task_id=tasks[index]['id'],definition_digest=tasks[index]['definition_digest'])
        select(0);base=(self.root/'terms.md').read_bytes();start=base.index('计数。'.encode())
        d={'path':'terms.md','expected_digest':digest(base),'content':base.decode().replace('计数。','数值之和。'),
            'topic':'numeric-definition','reason':'Correct only the declared business term.','acceptance':[{'key':'term','text':'Total means numeric sum.'}],
            'edits':[{'start':start,'end':start+len('计数。'.encode()),'before':'计数。','after':'数值之和。','semantic_target':'sum-definition'}],
            'delivery':{'role':'required',**{k:self.f.plan[k] for k in ('change_id','revision_id','task_id','definition_digest')},'acceptance_ids':[self.f.plan['acceptance'][0]['id']]}}
        d['presentation']={'source':'controlled-full-business-candidate','text':d['content']};a=propose_knowledge(self.root,self.f.request(d))
        select(1);rule=self.data(required=True);rule['delivery']['acceptance_ids']=[self.f.plan['acceptance'][1]['id']]
        b=learn(self.root,self.f.request(rule),method='promote');batch=[self.f.ref(a),self.f.ref(b)]
        for item in (a,b):check_candidate(self.root,self.f.request({'proposal':self.f.ref(item),'batch':batch,'observations':self.f.observations()}))
        decisions=review_candidates(self.root,self.f.request({'batch':batch,'decisions':[{'proposal':self.f.ref(item),'decision':'approved','source':'controlled-exact-two-owner-approval',
            'text':'Approve this exact independently scoped candidate.','reason':'Read full text, actual sources and bounded meanings.'} for item in (a,b)]}))['decisions']
        select(0);apply_knowledge(self.root,self.f.application_request(a,decisions[0]['decision_event_id'],True));self.assertEqual(self.f.verify_change()['status'],'passed')
        effect=current_state(self.root,b['proposal_id'])['knowledge_proposals'][0]['effective_candidate']
        composition={k:effect[k] for k in ('base_digest','result_digest','semantic_targets')}
        composition.update(status='passed',observer='controlled-actual-composed-content-reader',basis='Actual full text retains numeric sum and the independent bounded review rule.')
        select(1);actual=self.apply(b,decisions[1]['decision_event_id'],True,composition_review=composition)
        select(0);self.assertEqual(self.f.verify_change()['status'],'passed')
        whole=self.f.verify_change(whole=True);self.assertEqual(whole['status'],'passed')
        self.assertEqual(archive(self.root,self.f.change_request({'verification_id':whole['verification_id']},whole=True))['outcome'],'archived')
        self.assertEqual((self.root/'terms.md').read_text(),base.decode().replace('计数。','数值之和。')+RULE)
        self.assertEqual(self.f.rows('SELECT approved_event_id FROM knowledge_proposals WHERE id=?',(a['proposal_id'],))[0]['approved_event_id'],decisions[0]['decision_event_id'])
        self.assertEqual(self.f.rows('SELECT application_id FROM rule_bindings')[0]['application_id'],actual['application_id'])

    def test_other_owner_cannot_propose_or_apply_experience_rule(self):
        with self.assertRaises(EvolveError) as caught: propose_knowledge(self.root,self.f.request(self.data()))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_OWNER')
        item=self.candidate();approval=self.f.approve(item)
        with self.assertRaises(EvolveError) as caught: apply_knowledge(self.root,self.f.application_request(item,approval))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_OWNER');self.assertEqual(self.f.rows('SELECT * FROM rule_bindings'),[])

    def test_rule_requires_explicit_stage_and_actual_sources(self):
        for data,code in [({},'LEARNING_INPUT'),({**self.data(),'rule_sources':[]},'RULE_SOURCE')]:
            with self.subTest(code=code),self.assertRaises(EvolveError) as caught: learn(self.root,self.f.request(data),method='promote')
            self.assertEqual(caught.exception.code,code)

    def test_unconfirmed_hypothesis_cannot_become_a_rule_by_specific_approval(self):
        data=copy.deepcopy(self.l.record_request['input']);data['experience']['topic']='Unconfirmed cause hypothesis'
        data['experience']['cause']['confidence']='hypothesis';record=self.l.write(data)
        ref=self.l.ref(record['run_id']);source={'experience_ref':ref,'state_ref':ref,'counterexamples':[],'basis':'Hypothesis is not observed support.'}
        with self.assertRaises(EvolveError) as caught: learn(self.root,self.f.request({**self.data(),'rule_sources':[source]}),method='promote')
        self.assertEqual(caught.exception.code,'RULE_REVIEW_REQUIRED')

    def test_citation_without_retained_observation_is_not_rule_support(self):
        data=copy.deepcopy(self.l.record_request['input']);data['experience']['topic']='Citations without retained evidence'
        data['sources']=[{k:v for k,v in r.items() if k!='evidence_ids'} for r in data['sources']];record=self.l.write(data)
        ref=self.l.ref(record['run_id'])
        with self.assertRaises(EvolveError) as caught:
            learn(self.root,self.f.request({**self.data(),'rule_sources':[{'experience_ref':ref,'state_ref':ref,'counterexamples':[],'basis':'Only citations.'}]}),method='promote')
        self.assertEqual(caught.exception.code,'RULE_REVIEW_REQUIRED')

    def test_new_state_after_approval_does_not_inherit_old_rule_basis(self):
        item=self.candidate();approval=self.f.approve(item);before=(self.root/'terms.md').read_bytes();self.l.state('active')
        with self.assertRaises(EvolveError) as caught:self.apply(item,approval)
        self.assertEqual(caught.exception.code,'RULE_SOURCE_CHANGED');self.assertEqual((self.root/'terms.md').read_bytes(),before)

    def test_new_counterexample_blocks_approved_but_unapplied_rule(self):
        item=self.candidate();approval=self.f.approve(item);before=(self.root/'terms.md').read_bytes();self.counterexample()
        with self.assertRaises(EvolveError) as caught:self.apply(item,approval)
        self.assertEqual(caught.exception.code,'RULE_SOURCE_CHANGED');self.assertEqual((self.root/'terms.md').read_bytes(),before)

    def test_counterexample_marks_actual_rule_for_review_without_rewriting_it(self):
        item=self.candidate();approval=self.f.approve(item);actual=self.apply(item,approval);before=(self.root/'terms.md').read_bytes();self.counterexample()
        view=current_state(self.root,item['proposal_id'])
        self.assertEqual(view['knowledge_proposals'][0]['rule_state']['applicability'],'needs_review')
        self.assertEqual(view['knowledge_refs'][0]['rule_bindings'][0]['applicability'],'needs_review')
        verified=verify_knowledge(self.root,self.f.request({'application_id':actual['application_id'],'observations':self.f.observations()}))
        self.assertEqual(verified['status'],'blocked');self.assertEqual((self.root/'terms.md').read_bytes(),before)

    def test_changed_rule_scope_forms_new_candidate_without_old_approval(self):
        item=self.candidate();approval=self.f.approve(item);data=self.data();data['rule_scope']=['narrower explicit arithmetic scope']
        second=learn(self.root,self.f.request(data),method='promote');self.assertNotEqual(second['proposal_id'],item['proposal_id'])
        with self.assertRaises(EvolveError):self.apply(second,approval)
        self.assertEqual(self.f.rows('SELECT * FROM rule_bindings'),[])

    def test_reviewed_new_basis_can_rebind_unchanged_rule_without_replaying_old_delta(self):
        item=self.candidate();approval=self.f.approve(item);original=self.apply(item,approval)
        self.l.state('active');body=(self.root/'terms.md').read_bytes();data=self.data()
        data.update(content=body.decode(),presentation={'source':'controlled-exact-unchanged-rule-new-basis','text':body.decode()});data.pop('edits')
        second=learn(self.root,self.f.request(data),method='promote');new_approval=self.f.approve(second);actual=self.apply(second,new_approval)
        self.assertEqual((self.root/'terms.md').read_bytes(),body);self.assertNotEqual(actual['delta_id'],original['delta_id'])
        self.assertEqual(len(self.f.rows('SELECT * FROM rule_bindings')),2)
        self.assertEqual(verify_knowledge(self.root,self.f.request({'application_id':actual['application_id'],'observations':self.f.observations()}))['status'],'passed')
        with self.assertRaises(EvolveError) as caught:learn(self.root,self.f.request(data),method='promote')
        self.assertEqual(caught.exception.code,'KNOWLEDGE_NO_CHANGE')

    def test_rejected_rule_body_cannot_be_recreated_under_sync_owner(self):
        item=self.candidate();review_candidates(self.root,self.f.request({'decisions':[{'proposal':self.f.ref(item),'decision':'rejected','source':'controlled-rejection','text':'Reject this exact rule.','reason':'Do not establish this authority.'}]}))
        data=self.data();data.pop('rule_sources');data.pop('rule_scope');data['topic']='Different owner and heading'
        with self.assertRaises(EvolveError) as caught:propose_knowledge(self.root,self.f.request(data))
        self.assertEqual(caught.exception.code,'KNOWLEDGE_REJECTED')

    def test_rejected_sync_body_cannot_be_recreated_under_learn_owner(self):
        data=self.data();data.pop('rule_sources');data.pop('rule_scope');item=propose_knowledge(self.root,self.f.request(data))
        review_candidates(self.root,self.f.request({'decisions':[{'proposal':self.f.ref(item),'decision':'rejected','source':'controlled-rejection','text':'Reject this exact text.','reason':'Do not establish this authority.'}]}))
        with self.assertRaises(EvolveError) as caught:self.candidate()
        self.assertEqual(caught.exception.code,'KNOWLEDGE_REJECTED')

    def crash(self,request,point,code):
        script="""import json,os,sys
sys.path.insert(0,sys.argv[1])
from evolve_core import formal
from evolve_core.learning import learn
from evolve_core.store import Store
point=sys.argv[3];code=int(sys.argv[4])
def stop(*args,**kwargs):os._exit(code)
if point=='facts':formal._commit_application=stop
elif point=='metadata':Store.finish=stop
learn(sys.argv[2],json.load(sys.stdin),method='promote')
"""
        p=subprocess.run([sys.executable,'-B','-c',script,str(formal_fixture.ROOT/'runtime'),str(self.root),point,str(code)],input=json.dumps(request),text=True,capture_output=True,timeout=20)
        self.assertEqual(p.returncode,code,p.stderr)
        return self.f.rows('SELECT id FROM phase_runs WHERE request_id=?',(request['request_id'],))[0]['id']

    def test_real_rule_file_commit_recovery_creates_one_actual_binding(self):
        item=self.candidate();approval=self.f.approve(item);request=self.f.application_request(item,approval);request['input']['stage']='apply'
        run=self.crash(request,'facts',58);before=(self.root/'terms.md').read_bytes();result=recover(self.root,self.f.request({'run_id':run}))
        self.assertFalse(result['business_commands_run']);self.assertEqual((self.root/'terms.md').read_bytes(),before)
        self.assertEqual(len(self.f.rows('SELECT * FROM rule_bindings')),1)
        self.assertEqual(verify_knowledge(self.root,self.f.request({'application_id':result['application_id'],'observations':self.f.observations()}))['status'],'passed')
        self.assertEqual(len(search(self.root,'arithmetic')['results']),1)

    def test_real_rule_metadata_recovery_retains_candidate_and_experience_catalog(self):
        run=self.crash(self.f.request(self.data()),'metadata',59)
        result=recover(self.root,self.f.request({'run_id':run}));self.assertTrue(result['original_facts_committed'])
        item=self.f.rows('SELECT * FROM knowledge_proposals WHERE owner_skill=?',('evolve-learn',))[0]
        self.assertFalse(current_state(self.root,item['id'])['knowledge_proposals'][0]['source_pending'])
        self.assertEqual(len(search(self.root,'arithmetic')['results']),1);self.assertEqual(self.f.rows('SELECT * FROM rule_bindings'),[])

    def test_unresolved_rule_journal_blocks_other_records_until_original_recovery(self):
        item=self.candidate();approval=self.f.approve(item);request=self.f.application_request(item,approval);request['input']['stage']='apply'
        with patch('evolve_core.formal.install_files',side_effect=EvolveError('NEEDS_RECOVERY','Controlled stopped writer before file installation',exit_code=4)):
            with self.assertRaises(EvolveError):learn(self.root,request,method='promote')
        run=self.f.rows('SELECT id FROM phase_runs WHERE request_id=?',(request['request_id'],))[0]['id']
        before=(self.root/'terms.md').read_bytes()
        with self.assertRaises(EvolveError) as caught:self.l.write({'source':self.l.successful,'checked_basis':'Actual source inspection.','observer':'controlled-observer'},'retro')
        self.assertEqual(caught.exception.code,'NEEDS_RECOVERY');self.assertEqual((self.root/'terms.md').read_bytes(),before)
        result=recover(self.root,self.f.request({'run_id':run}));self.assertFalse(result['business_commands_run'])
        self.assertEqual((self.root/'terms.md').read_bytes(),before+RULE.encode());self.assertEqual(len(self.f.rows('SELECT * FROM rule_bindings')),1)

    def test_preserved_alpha10_writer_rejects_rule_protocol_without_mutation(self):
        package=self.root/'old-alpha10'
        with zipfile.ZipFile(formal_fixture.ROOT/'docs/evidence/imp007/initial-owner-package-alpha10.zip') as z:z.extractall(package)
        before=(self.root/'evolve/history.db').read_bytes()
        p=subprocess.run([sys.executable,'-B',str(package/'package/runtime/evolve.py'),'--project',str(self.root),'init','--request','-'],
            input=json.dumps({'authorization':self.f.auth,'input':{}}),text=True,capture_output=True,timeout=15)
        self.assertEqual(json.loads(p.stdout)['error']['code'],'SCHEMA_VERSION');self.assertEqual((self.root/'evolve/history.db').read_bytes(),before)
