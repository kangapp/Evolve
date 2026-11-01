"""Recovery scope and actual parent boundaries are checked before native dispatch."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/model_recovery_acceptance.py'


class RecoveryScopeTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', str(RUNNER), '--package', str(ROOT), *args],
                              capture_output=True, text=True, timeout=20)

    def test_scope_pins_four_sessions_exact_initial_documents_and_no_business_restore(self):
        result = self.invoke('--preflight-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        scope = json.loads(result.stdout)['expanded_scope']
        self.assertEqual((scope['slice'], scope['protocol_version'], scope['maximum_sessions']), ('IMP-012', 17, 4))
        self.assertEqual(scope['readonly_paths'], ['test_total.py'])
        self.assertEqual(scope['business_write_paths'], ['total.py'])
        self.assertEqual(set(scope['formal_decisions']) - {'scope'}, {'terms.md', 'later.md'})
        self.assertIn('no actual dispatch', scope['parent_mutations']['before_restore']['external'])

    def test_missing_or_wrong_scope_stops_before_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'not-created'
            for fields in ([], ['--authorization-text', 'Actual uniform authorization', '--expected-scope-digest', 'old-scope']):
                result = self.invoke('--out', str(output), *fields)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(output.exists())

    def test_actual_four_parent_boundaries_and_test_tampering_rejection_without_models(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Path(directory)
            package = lab / 'cache'
            build = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_package.py'), '--out', str(package)],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            code = r'''import json,shutil,sys,uuid
from pathlib import Path
package,source,lab=map(Path,sys.argv[1:])
sys.path[:0]=[str(package/'runtime'),str(source/'scripts')]
from model_recovery_checks import RecoveryChecks,scope_for,FILES,CHECKS,TITLE,GUIDE,EXTRA
from evolve_core.connect import connect
from evolve_core.plans import propose
from evolve_core.apply import implement
from evolve_core.verify import verify
from evolve_core.archive import archive
from evolve_core.knowledge import propose_baseline,apply_baseline
from evolve_core.maintenance import backup,restore
from evolve_core.package import digest
from evolve_core.reading import current_state
from evolve_core.work import fingerprint
project=lab/'business';project.mkdir()
registered=lab/'installed-source';shutil.copytree(package,registered)
(lab/'profile').mkdir();(lab/'profile/config.toml').write_text('isolated=true\n')
(project/'.codex').mkdir();(project/'.codex/config.toml').write_text('isolated=true\n')
evidence=lab/'evidence';evidence.mkdir()
for name,text in FILES.items():(project/name).write_text(text)
parent=RecoveryChecks(project,evidence,scope_for(package),package,registered)
auth={'source':'actual-uniform-human-authorization-controlled-parent-fixture','text':'This exact temporary native fixture, including the listed Terms/Later baseline decisions; no model or real external dispatch.', 'effect_kinds':['project_records','business_files','checks','knowledge'],'paths':['total.py','terms.md','later.md']}
identity={}
def req(data):return {**identity,'request_id':str(uuid.uuid4()),'authorization':auth,'input':data}
def bound(data):
 state=current_state(project)['changes'][0];task=state['tasks'][0]
 return {**req({'change_id':state['id'],'revision_id':state['current_revision'],'definition_digest':task['definition_digest'],**data}), 'expected_versions':{'change':state['row_version'],'task':task['row_version']}}
def baseline(name,text):
 item=propose_baseline(project,req({'path':name,'expected_digest':None,'content':text,'presentation':{'source':'specific-controlled-fixture','text':text}}))
 return apply_baseline(project,req({'proposal_id':item['proposal_id'],'approval':{'proposal_version':item['proposal_version'],'candidate_digest':item['candidate_digest'],'expected_digest':None,'source':'uniform-human-authorization-exact-temporary-fixture','text':'Apply this exact temporary baseline.'}}))
def verification(passed):
 state=current_state(project)['changes'][0];task=state['tasks'][0]
 from evolve_core.reading import history_snapshot
 with history_snapshot(project) as (db,_):definition=json.loads(db.execute('SELECT definition_json FROM tasks WHERE id=?',(task['id'],)).fetchone()[0])
 snapshot=fingerprint(project,definition)
 reviews=[{'axis':axis,'observer':'controlled-parent-fixture-actual-observation','summary':'Actually inspected total and independent literal checks; this is controlled fixture review, not native/model review.','fingerprint_digest':snapshot['digest'],'findings':[]} for axis in ('spec','standards')]
 reviews[0]['acceptance_results']=[{'ac_id':ac['id'],'status':'passed' if passed or i==1 else 'failed','basis':'Actual total([2,3]), total([]), total([-2,3]) compared with literal 5,0,1.'} for i,ac in enumerate(plan['acceptance'])]
 return verify(project,bound({'reviews':reviews}))
parent.before('seed')
connected=connect(project,req({'checks':CHECKS}));identity={'project_id':connected['project_id'],'expected_workspace_epoch':connected['workspace_epoch']}
plan=propose(project,req({'title':TITLE,'plan':'Return integer sum; preserve the three literal tests.','completion':'Original total check and actual dual-axis review pass.','scope':['total.py'],'required_checks':['total'],'acceptance':['Positive gives five','Empty gives zero','Negative gives one'],'presentation':{'source':'controlled-exact-temporary-plan','text':'Return integer sum; preserve the three literal tests.'}}))
implement(project,bound({'accepted_plan_digest':plan['plan_digest'],'files':[{'path':'total.py','expected_digest':digest((project/'total.py').read_bytes()),'content':'def total(values):\n    return sum(values)\n'}]}))
verification_result=verification(True);archive(project,bound({'verification_id':verification_result['verification_id']}))
baseline('terms.md',GUIDE);backup(project,req({}));results=[parent.after('seed')]
parent.before('later');baseline('later.md',EXTRA);results.append(parent.after('later'))
parent.before('restore');selected=parent.selected
restore_plan=restore(project,req({'stage':'plan','bundle':selected['path'],'manifest_digest':selected['manifest_digest']}))
restored=restore(project,req({'stage':'apply','plan_id':restore_plan['plan']['plan_id'],'plan_digest':restore_plan['plan_digest']}));identity['expected_workspace_epoch']=restored['workspace_epoch'];results.append(parent.after('restore'))
parent.before('current_verify');verification(False);results.append(parent.after('current_verify'))
original=(project/'test_total.py').read_bytes();(project/'test_total.py').write_bytes(original+b'\n# forbidden readonly mutation\n')
try:parent.after('current_verify')
except AssertionError:rejected=True
else:rejected=False
assert rejected
print(json.dumps({'passed':True,'cases':results,'readonly_tamper_rejected':rejected,'model_requests_sent':False},ensure_ascii=False))
'''
            result = subprocess.run([sys.executable, '-B', '-c', code, str(package), str(ROOT), str(lab)],
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(len(summary['cases']), 4)
            self.assertTrue(summary['readonly_tamper_rejected'])
            self.assertFalse(summary['model_requests_sent'])
