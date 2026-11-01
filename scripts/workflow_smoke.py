#!/usr/bin/env python3
"""Run a real arithmetic fix through an installed runtime; uses a disposable fixture."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def run_workflow(runtime, project, output, *, diagnostic=False):
    project, output, runtime = Path(project).resolve(), Path(output).resolve(), Path(runtime).resolve()
    if any(p.name not in ('.codex', '.claude') for p in project.iterdir()):
        raise ValueError('Workflow fixture requires an empty project except host configuration')
    if output.is_relative_to(project):
        raise ValueError('Acceptance evidence must be outside the business fixture')
    output.mkdir(parents=True, exist_ok=False)
    (project / 'arithmetic.py').write_text('def total(values):\n    return len(values)\n')
    (project / 'test_arithmetic.py').write_text(
        'import unittest\nfrom arithmetic import total\nclass Arithmetic(unittest.TestCase):\n'
        '    def test_independent_examples(self):\n'
        '        self.assertEqual(total([8,3]),11)\n'
        '        self.assertEqual(total([]),0)\n'
        '        self.assertEqual(total([-4,3]),-1)\n')
    check = {'id': 'arithmetic-unit', 'argv': [sys.executable, '-B', '-m', 'unittest', 'discover', '-v'], 'cwd': '.', 'timeout': 15}
    before = subprocess.run(check['argv'], cwd=project, capture_output=True, text=True)
    (output / 'before.txt').write_text(before.stdout + before.stderr)
    if before.returncode != 1:
        raise AssertionError('The independent examples did not catch the original bug')
    auth = {'source': 'controlled-disposable-workflow-fixture',
            'text': 'Within this test fixture, repair the arithmetic total and complete actual checks and closure.',
            'effect_kinds': ['project_records', 'business_files', 'checks'],
            'paths': ['arithmetic.py', 'test_arithmetic.py']}
    logs = []

    def call(action, data=None, *, method=None, authorization=auth):
        owner = {'analyze': 'propose', 'status': 'workflow'}.get(action, action)
        argv = [sys.executable, str(runtime), '--project', str(project), action, '--owner', 'evolve-' + owner]
        if data is not None:
            argv += ['--request', '-']
        if method:
            argv += ['--method', method]
        result = subprocess.run(argv, input=json.dumps({'authorization': authorization, 'input': data}) if data is not None else None,
                                cwd=output, capture_output=True, text=True, timeout=60)
        response = json.loads(result.stdout)
        logs.append({'argv': argv, 'exit_code': result.returncode, 'response': response, 'stderr': result.stderr})
        (output / 'commands.json').write_text(json.dumps(logs, ensure_ascii=False, indent=2))
        if result.returncode or not response['ok']:
            raise AssertionError('Runtime workflow failed: ' + json.dumps(response, ensure_ascii=False))
        return response['data']

    analysis_data, analysis_basis = None, None
    if diagnostic:
        observed_at = datetime.now(timezone.utc).isoformat()
        analysis_data = {'question': 'Why does the total count values instead of summing them?',
            'scope': auth['paths'], 'business_effect': 'read_only', 'record_intent': 'answer_only',
            'sources': [{'id': key, 'kind': 'file', 'path': name,
                         'expected_digest': hashlib.sha256((project / name).read_bytes()).hexdigest(),
                         'observer': 'actual-fixture-source-reader', 'observed_at': observed_at, 'limitations': []}
                        for key, name in (('S1', 'arithmetic.py'), ('S2', 'test_arithmetic.py'))] + [
                {'id': 'S3', 'kind': 'observation', 'object': 'arithmetic fixture', 'version': 'initial fixed fixture bytes',
                 'method': 'Actual existing unittest command', 'observer': 'actual-fixture-subprocess', 'observed_at': observed_at,
                 'content': before.stdout + before.stderr, 'limitations': []}],
            'analysis': {'observations': [{'local_key': 'F1', 'statement': 'The independent sum expectation fails with count two.', 'sources': ['S2', 'S3']}],
                'hypotheses': [{'local_key': 'H1', 'statement': 'The one-line len implementation explains this selected symptom.',
                                'status': 'supported', 'observations': ['F1'], 'basis': 'Actual failing output and the observed implementation.'}],
                'answer_status': 'answered', 'conclusion': 'The selected implementation counts rather than sums values.',
                'coverage': auth['paths'], 'limitations': ['Controlled fixture, no production claim.'], 'remaining_questions': [],
                'next_steps': ['Repair only under the separately supplied modification authorization.'],
                'symptom': {'criterion': {'method': 'Original registered arithmetic unittest', 'check': check,
                    'environment': 'Disposable Python fixture', 'input': [[8, 3], [], [-4, 3]], 'expected': [11, 0, -1],
                    'expected_source': 'S2', 'side_effects': 'Business read only; bytecode disabled'},
                    'status': 'reproduced', 'attempts': 1, 'failures': 1, 'sources': ['S3'], 'limitations': []}}}
        answer = call('analyze', analysis_data, authorization={**auth, 'effect_kinds': ['read_only']})
        if answer['committed'] or (project / 'evolve').exists() or (project / '.evolve-local').exists():
            raise AssertionError('Answer-only query initialized the project')
    connected = call('init', {'checks': [check]})
    config = project / 'evolve/config.toml'
    extra = '\n# Controlled fixture extension\n[fixture_extension]\nvalue = "preserve these bytes"\n'
    config.write_text(config.read_text() + extra)
    before_config = config.read_bytes()
    marker = project / '.evolve-local/unexpected-check'
    incremental = {'checks': [{'id': 'configured-only', 'argv': [sys.executable, '-c',
        'from pathlib import Path; Path(".evolve-local/unexpected-check").write_text("unexpected")']}]}
    candidate = call('init', incremental)
    if candidate['outcome'] != 'config_candidate' or config.read_bytes() != before_config:
        raise AssertionError('Incremental configuration did not preserve presentation-before-application')
    configured = call('init', {**incremental, 'expected_config_digest': candidate['expected_config_digest'],
                             'presentation': {'source': 'controlled-fixture-config-presentation', 'text': candidate['candidate']}})
    if configured['outcome'] != 'configuration_updated' or configured['checks_run'] or extra not in config.read_text() or marker.exists():
        raise AssertionError('Incremental configuration reset existing bytes or executed a configured command')
    text = 'Correct the total by adding values; preserve empty and negative arithmetic cases and existing tests.'
    if diagnostic:
        analysis_data['record_intent'] = 'record'
        investigation = call('analyze', analysis_data, authorization={**auth, 'effect_kinds': ['project_records']})
        state = call('status')['project']
        if state['changes']:
            raise AssertionError('Independent investigation created a business Change')
        observed = next(item for item in state['analyses'] if item['run_id'] == investigation['run_id'])
        analysis_basis = {'run_id': investigation['run_id'], 'result_digest': observed['result_digest'],
                          'criterion_digest': investigation['criterion_digest'],
                          'adoption_basis': 'Same fixture, unchanged literal expectation and original registered command.'}
    plan_data = {'title': 'Correct fixture total', 'plan': text,
                              'completion': 'All independent arithmetic examples pass.',
                              'scope': auth['paths'], 'required_checks': [check['id']],
                              'acceptance': ['8 and 3 total 11', 'Empty input totals 0', '-4 and 3 total -1'],
                 'presentation': {'text': text, 'source': 'controlled-fixture-plan-presentation'}}
    if diagnostic:
        plan_data['analysis_basis'] = analysis_basis
    planned = call('propose', plan_data)
    applied = call('apply', {'change_id': planned['change_id'], 'files': [{
        'path': 'arithmetic.py', 'expected_digest': hashlib.sha256((project / 'arithmetic.py').read_bytes()).hexdigest(),
        'content': 'def total(values):\n    return sum(values)\n'}]})
    if applied['outcome'] != 'implemented':
        raise AssertionError('Actual implementation checks did not pass')
    reviews = [{'axis': axis, 'observer': 'controlled-acceptance-fixture',
                'summary': 'Fixture review input for the narrow sum implementation and independent literal examples; not an LLM evaluation.',
                'fingerprint_digest': applied['fingerprint']['digest'], 'findings': []}
               for axis in ('spec', 'standards')]
    reviews[0]['acceptance_results'] = [{'ac_id': ac['id'], 'status': 'passed',
                                       'basis': 'The independent examples in test_arithmetic.py ran successfully'}
                                      for ac in planned['acceptance']]
    verification_data = {'change_id': planned['change_id'], 'reviews': reviews}
    if diagnostic:
        after = subprocess.run(check['argv'], cwd=project, capture_output=True, text=True)
        if after.returncode:
            raise AssertionError('The original criterion still fails after repair')
        verification_data['symptom_result'] = {'criterion_digest': analysis_basis['criterion_digest'],
            'fingerprint_digest': applied['fingerprint']['digest'], 'status': 'passed', 'observer': 'actual-fixture-subprocess',
            'observed_at': datetime.now(timezone.utc).isoformat(), 'basis': 'Repeated the unchanged original check and independent expected values.',
            'evidence': after.stdout + after.stderr, 'attempts': 1, 'failures': 0, 'limitations': ['Fixed local criterion only.']}
    verified = call('verify', verification_data)
    if verified['status'] != 'passed':
        raise AssertionError('Independent verification did not pass')
    archived = call('archive', {'change_id': planned['change_id'], 'verification_id': verified['verification_id']})
    baseline_text = '# Arithmetic fixture\n\nThe total is the sum of its input values.\n'
    proposal = call('init', {'path': 'evolve/project.md', 'expected_digest': None, 'content': baseline_text,
                            'presentation': {'text': baseline_text, 'source': 'controlled-fixture-baseline-presentation'}},
                    method='baseline.propose')
    if (project / 'evolve/project.md').exists():
        raise AssertionError('Presenting a knowledge candidate unexpectedly changed the formal file')
    knowledge = call('init', {'proposal_id': proposal['proposal_id'], 'approval': {
        'proposal_version': proposal['proposal_version'], 'candidate_digest': proposal['candidate_digest'],
        'expected_digest': proposal['expected_digest'], 'source': 'controlled-fixture-specific-approval',
        'text': 'In this isolated fixture, approve exactly the presented baseline candidate.'}}, method='baseline.apply',
        authorization={**auth, 'effect_kinds': ['project_records', 'knowledge'], 'paths': ['evolve/project.md']})
    summary = {'passed': archived['outcome'] == 'archived' and knowledge['outcome'] == 'baseline_applied',
               'runtime': str(runtime), 'project': str(project), 'project_id': connected['project_id'],
               'change_id': planned['change_id'], 'original_test_exit_code': before.returncode,
               'task_check_status': applied['task_checks'][0]['status'], 'verification_status': verified['status'],
               'completion_outcome': archived['outcome'], 'formal_baseline': knowledge['outcome'],
               'incremental_configuration': configured['outcome'], 'unrequested_check_executed': marker.exists(),
               'model_requests_sent': False, 'review_inputs': 'controlled fixture observations, not independent model review',
               'source_digest': hashlib.sha256((project / 'arithmetic.py').read_bytes()).hexdigest()}
    if diagnostic:
        summary['investigation'] = {'answer_only_created_records': False, 'recorded_run_id': analysis_basis['run_id'],
                                   'criterion_digest': analysis_basis['criterion_digest'], 'original_red_saved': True,
                                   'post_repair_original_criterion': 'passed', 'investigation_created_change': False}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    if marker.exists():
        raise AssertionError('A configured but unrelated check was executed')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run_workflow(args.runtime, args.project, args.out, diagnostic=args.diagnostic), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
