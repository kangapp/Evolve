"""Advance only the two already-authorized next turns after a headless question stop."""
import json
import os
from pathlib import Path
import sys
import hashlib

BASE = json.loads(Path('docs/evidence/imp014/frozen-package-010-r3.json').read_text())
LAB = Path(BASE['lab'])
PROJECT = LAB / 'claude-native-r2/business'
OLD_EVIDENCE = LAB / 'claude-native-r2/evidence'
EVIDENCE = LAB / 'claude-mean-tail/evidence'
SCOPE_DIGEST = '89d314042a3afce530183de0d39f6396c05368c392c5b3b20c73ca7efbcaeab7'
CANDIDATE = '7b77bc02394d207b78bf66d5f18babaeb1b6521820342f1d94b8662cb3735f60'
sys.path.insert(0, str(Path(BASE['package']) / 'runtime'))
sys.path.insert(0, str(Path(BASE['controller']) / 'scripts'))
from evolve_core.package import canonical, digest, check_package
from evolve_core.privacy import redact
from evolve_core.reading import history_snapshot
from model_complex_checks import ComplexChecks
import model_acceptance as host
host.redact = redact


def save(path, value):
    path.write_text(redact(json.dumps(value, ensure_ascii=False, indent=2)) + '\n')


def main():
    scope = json.loads((OLD_EVIDENCE / 'expanded-scope.json').read_text())
    assert scope['scope_digest'] == SCOPE_DIGEST
    assert digest(canonical({k:v for k,v in scope.items() if k!='scope_digest'})) == SCOPE_DIGEST
    old = json.loads((OLD_EVIDENCE / 'summary.json').read_text())
    assert [c['case'] for c in old['cases']] == ['propose','refactor_pause','cosmetic_revision','continue']
    assert old['error'] == 'Claude permission boundary stopped the native batch; inspect its saved result'
    audit = json.loads(Path('docs/evidence/imp014/claude-question-boundary-candidate-audit.json').read_text())
    assert audit['passed_business_state_audit'] and audit['actual_denied_tool']=='AskUserQuestion' and not audit['other_security_permission_denials']
    EVIDENCE.mkdir(parents=True, exist_ok=False)
    setup = old
    cache, registered = Path(setup['host_cache_root']), Path(setup['registered_installation_root'])
    checker = ComplexChecks(PROJECT,scope,EVIDENCE,package=cache,registered_root=registered)
    checker.allowed.update(scope['second_files'])
    with history_snapshot(PROJECT) as (c,_):
        change,rev,tasks,definitions=checker.work(c,mean_required=False)
        checker.original_proof(c,tasks['CORE'])
        checker.core_digest,checker.core_result=tasks['CORE']['definition_digest'],tasks['CORE']['result_json']
        pending=[json.loads(r['result_json']) for r in c.execute("SELECT * FROM phase_runs WHERE action='update'") if json.loads(r['result_json']).get('outcome')=='scope_confirmation_required']
        assert len(pending)==1 and pending[0]['candidate_digest']==CANDIDATE
        assert digest(canonical(pending[0]['candidate']))==CANDIDATE
        checker.pending_revision={'candidate_digest':CANDIDATE,'document':pending[0]['candidate']['document']}
    summary={'status':'running_two_pre_authorized_next_turns','source_scope_digest':SCOPE_DIGEST,
        'package_digest':BASE['package_digest'],'candidate_digest':CANDIDATE,'model':'MiniMax-M3.1-Flash',
        'authorization':'Actual uniform human authorization; exact finish_revision and verify prompts from the previously reviewed scope, not a fabricated response to AskUserQuestion.',
        'permission_settings_and_guard_unchanged':True,'denied_tool_not_retried':True,
        'original_raw_batch_left_failed':True,'cases':[],'automated_checks_passed':False,'review_status':'pending'}
    save(EVIDENCE/'summary.json',summary)
    (EVIDENCE/'empty-mcp.json').write_text('{"mcpServers":{}}')
    try:
        for case in ('finish_revision','verify'):
            checker.before(case)
            save(EVIDENCE/(case+'-true-before-rows.json'),checker.before_rows)
            save(EVIDENCE/(case+'-true-before-files.json'),{k:hashlib.sha256(v).hexdigest() for k,v in checker.before_files.items()})
            prompt=scope['cases'][case]
            (EVIDENCE/(case+'-prompt.txt')).write_text(prompt)
            argv=['claude','--print','--verbose','--output-format','stream-json','--no-session-persistence',
                '--setting-sources','project','--permission-mode','acceptEdits','--strict-mcp-config',
                '--mcp-config',str(EVIDENCE/'empty-mcp.json'),'--disallowedTools','Agent,Task',
                '--allowedTools','Read,Write,Edit,Glob,Grep,Skill,Bash(python3:*),Bash(ls:*),Bash(cat:*),Bash(rg:*)',
                '--model','MiniMax-M3.1-Flash']
            print(json.dumps({'case':case,'state':'started','operation':'next authorized turn; not retrying denied question'}),flush=True)
            result=host.claude_case(argv,host.claude_input(prompt,PROJECT,cache),
                env={**os.environ,'CLAUDE_CONFIG_DIR':str(PROJECT/'.agents/evolve-acceptance/profile'),'CLAUDE_CODE_DISABLE_AUTO_MEMORY':'1'},
                project=PROJECT,log=EVIDENCE/(case+'-model.json'))
            observed=checker.after(case)
            save(EVIDENCE/(case+'-parent-observation.json'),observed)
            summary['cases'].append({'case':case,'model_result':result,'parent_observation':observed})
            save(EVIDENCE/'summary.json',summary)
            print(json.dumps({'case':case,'state':'observed'}),flush=True)
        summary['automated_checks_passed']=True;summary['status']='two_next_turns_observed_primary_review_pending'
    except Exception as error:
        summary['error']=redact(str(error))
    finally:
        save(EVIDENCE/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if not summary['automated_checks_passed']:raise SystemExit(1)

if __name__=='__main__':main()
