#!/usr/bin/env python3
"""Consume actual prior fixture learning, pause, then continue via fresh CLI processes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def run_continuation(runtime, project, output, baseline):
    runtime, project, output = map(lambda p: Path(p).resolve(), (runtime, project, output))
    if not baseline.get('passed') or Path(baseline['project']) != project or output.is_relative_to(project):
        raise ValueError('Requires this runner\'s completed disposable baseline workflow and external evidence directory')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(project / 'arithmetic.py') != baseline['source_digest']:
        raise ValueError('Baseline source changed before the controlled continuation case')
    output.mkdir(parents=True, exist_ok=False)
    logs = []
    original = {name: (project / name).read_bytes() for name in ('arithmetic.py', 'test_arithmetic.py')}
    auth = {'source': 'controlled disposable project learning fixture', 'text': 'Record and review actual project-local findings only',
            'effect_kinds': ['project_records']}

    def snapshot():
        return {p.relative_to(project).as_posix(): sha(p) for p in project.rglob('*') if p.is_file()}

    def call(action, data=None, *, target=None, method=None, authorization=auth):
        owner = {'status': 'workflow', 'resume': 'workflow', 'next': 'workflow', 'analyze': 'propose'}.get(action, action)
        argv = [sys.executable, '-B', str(runtime), '--project', str(project), action]
        if target:
            argv += [target]
        argv += ['--owner', 'evolve-' + owner]
        if method:
            argv += ['--method', method]
        if data is not None:
            argv += ['--request', '-']
        before = snapshot() if data is None else None
        process = subprocess.run(argv, input=json.dumps({'authorization': authorization, 'input': data}) if data is not None else None,
                                 text=True, capture_output=True, cwd=output, timeout=60)
        response = json.loads(process.stdout)
        unchanged = snapshot() == before if before is not None else None
        logs.append({'argv': argv, 'exit_code': process.returncode, 'response': response, 'stderr': process.stderr,
                     'pure_query_project_files_unchanged': unchanged})
        (output / 'commands.json').write_text(json.dumps(logs, ensure_ascii=False, indent=2))
        if process.returncode or not response['ok'] or unchanged is False:
            raise AssertionError('Continuation fixture command failed or query wrote project data')
        return response['data']

    def run_ref(context, run_id, *, checks=False):
        run = next(r for r in context['runs'] if r['run_id'] == run_id)
        ref = {'run_id': run_id, 'result_digest': run['result_digest']}
        if checks:
            ref['evidence_ids'] = [r['id'] for r in run['evidence']]
        return ref

    first = call('resume', target=baseline['change_id'])['context']
    successful = next(r for r in first['runs'] if r['action'] == 'apply' and r['result']['outcome'] == 'implemented')
    source = run_ref(first, successful['run_id'], checks=True)
    source_refs = [source]
    if baseline.get('investigation'):
        analysis = call('status', target=baseline['investigation']['recorded_run_id'])['project']['analyses'][0]
        source_refs.append({'run_id': analysis['run_id'], 'result_digest': analysis['result_digest'],
                            'evidence_ids': [e['evidence_id'] for e in analysis['evidence']]})
    created = call('learn', {'experience': {
        'topic': 'Arithmetic count versus sum in this project',
        'problem': 'The original literal sum expectation failed under len(values), then passed with sum(values)',
        'cause': {'statement': 'The inspected arithmetic fixture counted instead of adding its integer inputs', 'confidence': 'observed'},
        'advice': 'Use sum(values) for this integer-total contract and retain independent literal expectations before checking closure',
        'applicability': 'The same simple integer-total contract, after checking the new source and literal expectations',
        'version_context': sys.version.split()[0] + '; controlled arithmetic fixture',
        'observer': 'controlled fixture source reader and actual check runner', 'scope': ['local Python integer totals'],
        'exclusions': ['No production-data or all-numeric-types claim'], 'tags': ['arithmetic', 'sum'],
        'limitations': ['Only actual retained local examples; fixture finding input is not an independent model judgment']},
        'sources': source_refs}, method='record')
    found = call('learn', target='arithmetic', method='search')
    entry = next(r for r in found['results'] if r['experience_ref']['run_id'] == created['run_id'])
    reference = entry['experience_ref']
    scope = ['arithmetic_second.py', 'test_arithmetic_second.py']
    if any((project / name).exists() or (project / name).is_symlink() for name in scope):
        raise ValueError('Refuse to overwrite an existing second-task fixture')
    (project / scope[0]).write_text('def total(values):\n    return len(values)\n')
    (project / scope[1]).write_text('import unittest\nfrom arithmetic_second import total\n'
        'class SecondArithmetic(unittest.TestCase):\n    def test_values(self):\n'
        '        self.assertEqual(total([5,7]),12)\n        self.assertEqual(total([]),0)\n        self.assertEqual(total([9,-2]),7)\n')
    second_tests = (project / scope[1]).read_bytes()
    red = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-v'], cwd=project, text=True, capture_output=True, timeout=15)
    (output / 'second-before.txt').write_text(red.stdout + red.stderr)
    if red.returncode != 1:
        raise AssertionError('The second real regression was not caught')
    grant = {'source': 'controlled second-task explicit grant',
             'text': 'Repair only the new second arithmetic fixture, preserve its literal assertions, pause before checks, then continue and verify',
             'effect_kinds': ['project_records', 'business_files', 'checks'], 'paths': scope}
    text = entry['experience']['advice'] + '; apply only to the inspected second arithmetic function, with its own literal values.'
    planned = call('propose', {'title': 'Second similar integer-total task', 'plan': text,
        'completion': 'The second arithmetic examples pass and original assertions remain unchanged', 'scope': scope,
        'required_checks': ['arithmetic-unit'], 'acceptance': ['Second literal examples total 12, 0 and 7'],
        'presentation': {'source': 'controlled actual retrieved-content plan presentation', 'text': text}}, authorization=grant)
    decided = call('learn', {'kind': 'decision', 'experience_ref': reference, 'search_ref': found['search_ref'],
        'decision': 'adopted', 'change_id': planned['change_id'], 'revision_id': planned['revision_id'],
        'definition_digest': planned['definition_digest'], 'observed_files': {name: sha(project / name) for name in scope},
        'applicability_basis': 'Actual second source counts the values; its unchanged independent literals require sums under the same narrow integer contract',
        'limitations': ['Controlled fixture inspection; no independent model judgment or formal rule']}, method='review')
    paused = call('apply', {'change_id': planned['change_id'], 'files': [{'path': scope[0], 'expected_digest': sha(project / scope[0]),
        'content': 'def total(values):\n    return sum(values)\n'}], 'pause': {'completed': ['Saved the actual second sum candidate'],
        'remaining': ['Run original checks, review and verify'], 'next_steps': ['Restore facts in a new process and continue'],
        'reason': 'Controlled normal conversation pause before checks'}}, authorization=grant)
    restored = call('resume', target=planned['change_id'])['context']
    if paused['outcome'] != 'partial' or restored['project']['pending_runs'] or restored['task_result']['checks'] != 'not_run':
        raise AssertionError('Normal pause was confused with unfinished execution or completed checks')
    application = next(a for a in restored['learning_context']['applications'] if a['decision']['run_id'] == decided['run_id'])
    if application['experience_ref'] != reference or application['decision']['effect'] != 'unknown':
        raise AssertionError('Fresh restoration lost the adopted version or invented its outcome')
    pause_ref = run_ref(restored, paused['run_id'])
    old_result = next(r for r in restored['runs'] if r['run_id'] == paused['run_id'])
    applied = call('apply', {'change_id': planned['change_id'], 'files': [], 'continuation': pause_ref}, authorization=grant)
    reviews = [{'axis': axis, 'observer': 'controlled fixture inspection, not model review',
                'summary': 'Inspected the second sum candidate and unchanged independent literals; actual required unittest ran',
                'fingerprint_digest': applied['fingerprint']['digest'], 'findings': []} for axis in ('spec', 'standards')]
    reviews[0]['acceptance_results'] = [{'ac_id': ac['id'], 'status': 'passed', 'basis': 'Actual independent second examples 12,0,7 ran under the registered command'} for ac in planned['acceptance']]
    verified = call('verify', {'change_id': planned['change_id'], 'reviews': reviews}, authorization=grant)
    closed = call('archive', {'change_id': planned['change_id'], 'verification_id': verified['verification_id']}, authorization=grant)
    latest = call('resume', target=planned['change_id'])['context']
    if next(r for r in latest['runs'] if r['run_id'] == paused['run_id'])['result'] != old_result['result']:
        raise AssertionError('Continuation rewrote the sealed normal pause result')
    decision_ref = application['decision']['decision_ref']
    feedback = call('learn', {'kind': 'feedback', 'decision_ref': decision_ref, 'outcome': 'unknown',
        'result_source': run_ref(latest, verified['run_id'], checks=True),
        'basis': 'The second real verification passed, but this scripted fixture does not prove causal improvement attributable to the suggestion',
        'limitations': ['No model-semantic or causal-benefit inference from task success']}, method='review')
    none = call('learn', {'source': run_ref(latest, closed['run_id']),
        'observer': 'controlled final fixture observer',
        'checked_basis': 'Inspected this narrow archive result; no additional reusable finding beyond the already recorded arithmetic experience'}, method='retro')
    final = call('learn', target='arithmetic', method='search')
    learned = next(r for r in final['results'] if r['experience_ref'] == reference)
    passed = (verified['status'] == 'passed' and closed['outcome'] == 'archived' and learned['state'] == 'candidate'
              and feedback['outcome'] == 'unknown' and none['outcome'] == 'no_new_learning'
              and all((project / name).read_bytes() == data for name, data in original.items())
              and (project / scope[1]).read_bytes() == second_tests)
    summary = {'passed': passed, 'evidence_kind': 'Actual installed-runtime CLI processes with controlled fixture inputs, not native model-semantic acceptance',
        'runtime': str(runtime), 'project': str(project), 'model_requests_sent': False, 'experience_ref': reference,
        'experience_produced_from_actual_work': True, 'second_change_id': planned['change_id'], 'second_real_red_exit_code': red.returncode,
        'normal_pause': {'run_id': paused['run_id'], 'outcome': paused['outcome'], 'checks': paused['checks'], 'new_run_id': applied['run_id']},
        'fresh_context_restored_prior_adoption': True, 'old_run_result_unchanged': True,
        'feedback': {'run_id': feedback['run_id'], 'outcome': feedback['outcome']}, 'final_state': learned['state'],
        'new_discovery_status_after_archive': none['outcome'], 'verification': verified['status'], 'closure': closed['outcome'],
        'original_and_second_literal_assertions_unchanged': True, 'learning_did_not_approve_formal_knowledge': not learned['formal_rule']}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    if not passed:
        raise AssertionError('Continuation and learning workflow did not pass')
    return summary
