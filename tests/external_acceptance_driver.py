"""Private disposable public protocol driver; no model calls or production targets."""
import json,shutil,sys
from pathlib import Path
package,source,lab=map(Path,sys.argv[1:4])
sys.path[:0]=[str(package/'runtime'),str(source/'scripts')]
from model_external_checks import ExternalChecks,scope_for,FILES,CHECKS,TARGET,MECHANISM,recipe
from evolve_core.package import canonical,digest
from evolve_core.reading import current_state
from evolve_core.work import fingerprint
project=lab/'business';project.mkdir()
evidence=lab/'evidence';evidence.mkdir()
base=project/'.agents/evolve-acceptance';base.mkdir(parents=True)
registered=base/'installed-source';shutil.copytree(package,registered)
(base/'profile').mkdir();(base/'profile/config.toml').write_text('isolated=true\n')
(project/'.codex').mkdir();(project/'.codex/config.toml').write_text('isolated=true\n')
for name,text in FILES.items():(project/name).write_text(text)
parent=ExternalChecks(project,evidence,scope_for(package),package,registered)
auth={'source':'actual-human-unified-authorization-and-specific-controlled-parent-fixture','text':'This exact temporary six-case public protocol exercise; no model dispatched, production, personal configuration or formal knowledge decisions.', 'effect_kinds':['project_records','external_read','external_write','checks'],'external_targets':[{**{k:TARGET[k] for k in ('kind','path','environment','objects','scope')},'provider_identity':TARGET['identity']['expected']}]}
commands=[]
def cli(action,method,data):
 import subprocess
 request={'authorization':auth,'input':data}
 child=subprocess.run([sys.executable,'-B',str(package/'runtime/evolve.py'),'--project',str(project),action,'--method',method,'--request','-'],input=json.dumps(request),capture_output=True,text=True,timeout=40)
 value=json.loads(child.stdout);commands.append({'action':action,'method':method,'request':request,'response':value,'exit_code':child.returncode})
 assert value['ok'],value
 return value['data']
def plan(title,n):
 text='Use the fixed synchronous Python/helper/alias/SQL mechanism to change only isolated ledger id=1 to '+str(n)+'; preserve all mechanism and original literal test bytes.'
 return cli('propose','create',{'title':title,'plan':text,'completion':'Actual provider/data effects and independent final verification pass.','scope':MECHANISM+['test_target'+str(n)+'.py'],'required_checks':['data'+str(n)],'execution_kind':'external_write','external_target':TARGET,'acceptance':['Actual target row is (1,'+str(n)+') after the exact approved operation.'],'presentation':{'source':'actual-controlled-public-fixture-specific-plan','text':text}})
def apply(plan,before,after,method='external.execute',original=None):
 data=recipe(before,after);data['change_id']=plan['change_id']
 data['execution']['closure']['observer']='actual-controlled-parent-source-review'
 data['execution']['closure']['basis']='Actually read all four fixed files: synchronous unique receipt, stable target identity and prior value tested in the same BEGIN IMMEDIATE; only ledger id1 and own receipt mutate. No background work.'
 data['idempotency']['basis']='Actual helper tests unique operation_receipts key in the same transaction before update.'
 data['reconciliation']['coverage_basis']='Actual complete finite source and schema inspection; ledger id1 and own receipt are all writable scope.'
 if original:data['compensates_operation_id']=original
 candidate=cli('apply',method,data)
 return cli('apply',method,{'change_id':plan['change_id'],'stage':'apply','candidate_ref':{'run_id':candidate['run_id'],'result_digest':candidate['result_digest']},'approval':{'candidate_digest':candidate['candidate_digest'],'target_digest':candidate['candidate']['target_snapshot']['digest'],'source':'actual-unified-human-authorization-exact-controlled-public-candidate','text':'Approve only this exact saved candidate/target for the concrete isolated business plan and declared task checks.'}})
def verification(change_id,passed=True):
 state=next(c for c in current_state(project)['changes'] if c['id']==change_id)
 task=state['tasks'][0]
 with __import__('evolve_core.reading',fromlist=['history_snapshot']).history_snapshot(project) as (db,_):
  definition=json.loads(db.execute('SELECT definition_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])
 fp=fingerprint(project,definition)
 reviews=[{'axis':axis,'observer':'actual-controlled-public-fixture-review','summary':'Actually inspected fixed source, unique provider receipt, current row and original literal check. Controlled fixture review, not native or independent-agent review.','fingerprint_digest':fp['digest'],'findings':[]} for axis in ('spec','standards')]
 reviews[0]['acceptance_results']=[{'ac_id':ac['id'],'status':'passed' if passed else 'failed','basis':'Actually queried the literal ledger row and corresponding original independent target check.'} for ac in definition['acceptance']]
 return cli('verify','run',{'change_id':change_id,'reviews':reviews})
observations=[]
parent.before('seed')
cli('init','connect',{'checks':CHECKS})
seed=plan('Controlled ledger to 20',20)
assert apply(seed,10,20)['effect_outcome']=='succeeded'
seed_ver=verification(seed['change_id']);assert seed_ver['status']=='passed'
cli('archive','close',{'change_id':seed['change_id'],'verification_id':seed_ver['verification_id']})
cli('maintain','backup',{})
observations.append(parent.after('seed'))
parent.before('unknown')
second=plan('Controlled ledger to 30',30)
unknown=apply(second,20,30)
assert unknown['effect_outcome']=='unknown'
observations.append(parent.after('unknown'))
parent.before('reconcile')
cli('apply','external.reconcile',{'operation_id':unknown['operation_id']})
cli('apply','external.execute',{'change_id':second['change_id'],'stage':'checks','operation_id':unknown['operation_id']})
second_ver=verification(second['change_id']);assert second_ver['status']=='passed'
cli('archive','close',{'change_id':second['change_id'],'verification_id':second_ver['verification_id']})
observations.append(parent.after('reconcile'))
parent.before('compensate')
third=plan('Controlled compensation to 20',20)
comp=apply(third,30,20,'external.compensate',unknown['operation_id'])
assert comp['effect_outcome']=='unknown'
observations.append(parent.after('compensate'))
parent.before('restore_reconcile')
saved=parent.selected
prepared=cli('maintain','restore',{'stage':'plan','bundle':saved['path'],'manifest_digest':saved['manifest_digest']})
cli('maintain','restore',{'stage':'apply','plan_id':prepared['plan']['plan_id'],'plan_digest':prepared['plan_digest']})
cli('apply','external.reconcile',{'operation_id':comp['operation_id']})
observations.append(parent.after('restore_reconcile'))
parent.before('current_verify')
assert verification(seed['change_id'],False)['status'] in ('failed','blocked')
observations.append(parent.after('current_verify'))
(project/'test_target20.py').write_text('tampered literal guard\n')
try:parent.after('current_verify')
except AssertionError:pass
else:raise AssertionError('Parent accepted literal-test tampering')
summary={'model_requests_sent':False,'commands':len(commands),'observations':observations,'tampering_rejected':True}
if len(sys.argv)>4:
 destination=Path(sys.argv[4]);destination.mkdir(parents=True,exist_ok=True)
 (destination/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
 (destination/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary))
