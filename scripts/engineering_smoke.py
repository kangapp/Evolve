#!/usr/bin/env python3
"""Run the fixed Next fixture through real checks, reuse, archive and copy cleanup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/engineering-next'
READONLY = ('README.md', 'package.json', 'package-lock.json', 'tsconfig.json', 'next-env.d.ts',
            'app/layout.tsx', 'app/page.tsx', 'tests/total.test.ts')
VIEWS = ['codemap', 'domain', 'spec', 'decision', 'development', 'architecture', 'data', 'rule']


def sha(content):
    return hashlib.sha256(content).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def fixture_files():
    return {p.relative_to(FIXTURE).as_posix(): p.read_bytes() for p in sorted(FIXTURE.rglob('*')) if p.is_file()}


def prepare_project(project, evidence, *, offline=False):
    for name, content in fixture_files().items():
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError('Fixture preparation does not overwrite: ' + name)
        target.write_bytes(content)
    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED': '1'}
    argv = ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'] + (['--offline'] if offline else [])
    installed = subprocess.run(argv, cwd=project, env=env, capture_output=True, text=True, timeout=180)
    save(evidence / 'npm-install.json', {'argv': argv, 'exit_code': installed.returncode,
        'stdout': installed.stdout, 'stderr': installed.stderr})
    if installed.returncode:
        raise RuntimeError('Fixture dependency setup failed; preserve npm-install.json')
    before = {name: (project / name).read_bytes() for name in READONLY}
    built = subprocess.run(['npm', 'run', 'build'], cwd=project, env=env, capture_output=True, text=True, timeout=180)
    save(evidence / 'baseline-build.json', {'exit_code': built.returncode, 'stdout': built.stdout, 'stderr': built.stderr})
    if built.returncode or any((project / name).read_bytes() != content for name, content in before.items()):
        raise RuntimeError('Baseline build failed or changed fixed inputs; inspect original output before dispatch')
    return before


class Runtime:
    def __init__(self, package, project, evidence, auth):
        self.package, self.project, self.evidence, self.auth = package, project, evidence, auth
        self.calls = []

    def call(self, action, data=None, *, target=None, method=None):
        argv = [sys.executable, '-B', str(self.package / 'runtime/evolve.py'), '--project', str(self.project), action]
        if target:
            argv.append(target)
        if method:
            argv += ['--method', method]
        request = None
        if data is not None:
            request = {'authorization': self.auth, 'input': data}
            argv += ['--request', '-']
        completed = subprocess.run(argv, input=json.dumps(request) if request else None,
            capture_output=True, text=True, timeout=300, env={**os.environ, 'NEXT_TELEMETRY_DISABLED': '1'})
        response = json.loads(completed.stdout)
        self.calls.append({'argv': argv, 'request': request, 'response': response,
                           'exit_code': completed.returncode, 'stderr': completed.stderr})
        save(self.evidence / 'calls.json', self.calls)
        if completed.returncode or not response['ok']:
            raise AssertionError(response)
        return response['data']

    def reference(self, run_id):
        data = self.call('history', target=run_id)
        # history_view returns a selected immutable run in the public response.
        with self.snapshot() as connection:
            row = connection.execute('SELECT result_digest FROM phase_runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise AssertionError(data)
        return {'run_id': run_id, 'result_digest': row[0]}

    def snapshot(self):
        from contextlib import contextmanager
        @contextmanager
        def connection():
            # The parent inspects a temporary snapshot and never edits runtime tables.
            with self.history_snapshot(self.project) as (db, _):
                yield db
        return connection()

    def review(self, plan):
        observed = self.call('next', target=plan['change_id'])
        subject = observed['execution'].get('review_subject')
        fingerprint = (subject['fingerprint_digest'] if subject else
                       observed['context']['workspace_observation']['current']['digest'])
        reviews = [{'axis': axis, 'mode': 'self', 'observer': 'controlled-engineering-fixture-parent',
            'summary': 'Inspected the sum loop, retained independent literals and actual Next/TypeScript outputs; native Codex semantic review is separate.',
            'fingerprint_digest': fingerprint, 'findings': []}
            for axis in ('spec', 'standards')]
        reviews[0]['acceptance_results'] = [{'ac_id': item['id'], 'status': 'passed',
            'basis': 'Original positive, empty and negative literals plus actual types and Next build.',
            'check_ids': ['unit', 'types', 'build']} for item in plan['acceptance']]
        return reviews


def checks():
    return [{'id': 'environment', 'argv': ['node', '--version'], 'preflight': True, 'timeout': 20,
             'environment_tools': ['npm', 'node_modules/.bin/tsc'], 'environment_files': ['package-lock.json']},
        *[{'id': name, 'argv': ['npm', 'run', command], 'timeout': 150, 'reuse': name in ('types', 'build'),
           'environment_tools': ['node', 'node_modules/.bin/tsc'],
           'environment_files': ['package-lock.json'], 'environment_variables': ['NEXT_TELEMETRY_DISABLED']}
          for name, command in [('unit', 'test'), ('types', 'typecheck'), ('build', 'build')]]]


def run_faults(runtime, original, content_digest):
    """Exercise expected failures with real Node/TypeScript processes, never models."""
    call, project = runtime.call, runtime.project
    source = project / 'src/total.ts'
    good = 'export function total(values: number[]): number { let sum = 0; for (const value of values) { sum += value; } return sum; }\n'
    outcomes = []

    def configure(configured):
        data = {'checks': configured}
        candidate = call('init', data)
        assert candidate['outcome'] == 'config_candidate'
        call('init', {**data, 'expected_config_digest': candidate['expected_config_digest'],
            'presentation': {'source': 'controlled-exact-fault-check-configuration', 'text': candidate['candidate']}})

    def plan(title, required):
        text = 'Controlled temporary failure rehearsal: ' + title + '; preserve original inputs and retain actual failures.'
        return call('propose', {'title': title, 'plan': text,
            'completion': 'Observe the declared failure and stop or repair within the same exact scope.',
            'scope': ['src/total.ts'], 'context_paths': list(READONLY), 'required_checks': required,
            'acceptance': ['The declared failure and physical source state are reported accurately.'],
            'knowledge_review': [{'views': VIEWS, 'result': 'not_applicable', 'source_paths': list(READONLY),
                'basis': 'Disposable execution-boundary rehearsal, not product delivery; stop after the observed failure or repair. No formal knowledge is adopted.'}],
            'presentation': {'source': 'controlled-exact-fault-plan', 'text': text}})

    def apply(change, content):
        return call('apply', {'files': [{'path': 'src/total.ts', 'expected_digest': sha(source.read_bytes()),
                                       'content': content}]}, target=change['change_id'])

    def failed(change, content, code):
        try:
            apply(change, content)
        except AssertionError:
            response = runtime.calls[-1]['response']
            assert not response['ok'] and response['error']['code'] == code, response
            return response['error']['details']
        raise AssertionError('Expected controlled ' + code + ' was not observed')

    def retire(change):
        result = call('maintain', {'change_id': change['change_id'],
            'reason': 'Expected isolated fault observed; retain its actual results and physical effects, then stop this rehearsal.'}, method='cancel')
        assert result['outcome'] == 'cancelled' and result['completed_results_preserved']
        assert all((project / name).read_bytes() == value for name, value in original.items())

    print(json.dumps({'fault': 'missing_environment', 'state': 'started'}), flush=True)
    configured = checks()
    configured[0] = {**configured[0], 'argv': ['evolve-missing-node-fixture', '--version']}
    configure(configured)
    change = plan('Missing Node executable before dispatch', ['environment', 'unit', 'types', 'build'])
    before = source.read_bytes()
    with runtime.snapshot() as db:
        count = db.execute("SELECT COUNT(*) FROM events WHERE kind='check_dispatch_prepared'").fetchone()[0]
    details = failed(change, good, 'CHECK_ENVIRONMENT')
    assert source.read_bytes() == before and details['execution']['business_files'] == 'not_dispatched'
    with runtime.snapshot() as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE kind='check_dispatch_prepared'").fetchone()[0] == count
    retire(change)
    outcomes.append({'case': 'missing_environment', 'error': 'CHECK_ENVIRONMENT', 'files_dispatched': False, 'checks_dispatched': False})

    print(json.dumps({'fault': 'post_write_typescript_failure', 'state': 'started'}), flush=True)
    configure(checks())
    change = plan('Actual TypeScript and Next failure after writing', ['unit', 'types', 'build'])
    bad = 'export function total(values: number[]): number { return values.join(","); }\n'
    result = apply(change, bad)
    assert result['outcome'] == 'checks_not_passed' and source.read_text() == bad
    states = {item['check_id']: item['status'] for item in result['task_checks']}
    assert states['types'] == states['build'] == 'failed' and states['unit'] == 'failed', states
    with runtime.snapshot() as db:
        saved_failure = tuple(db.execute('SELECT result_json,result_digest FROM phase_runs WHERE id=?', (result['run_id'],)).fetchone())
    continuation = call('next', target=change['change_id'])['execution']
    assert continuation['action'] == 'apply', continuation
    repaired = apply(change, good)
    assert repaired['outcome'] == 'implemented' and all(item['executed'] for item in repaired['task_checks'])
    with runtime.snapshot() as db:
        assert tuple(db.execute('SELECT result_json,result_digest FROM phase_runs WHERE id=?', (result['run_id'],)).fetchone()) == saved_failure
    retire(change)
    outcomes.append({'case': 'post_write_typescript_failure', 'checks': states, 'source_was_written': True,
                     'same_plan_repair': 'implemented', 'failed_receipt_preserved': True})

    print(json.dumps({'fault': 'check_source_mutation', 'state': 'started'}), flush=True)
    command = ("const p=require('node:child_process').spawnSync('npm',['run','typecheck'],{stdio:'inherit'});"
               "if(p.status!==0)process.exit(p.status||1);"
               "require('node:fs').appendFileSync('src/total.ts','\\n// controlled check-side mutation\\n');")
    mutation = {'id': 'mutates-source', 'argv': ['node', '--input-type=commonjs', '-e', command],
                'timeout': 150, 'environment_tools': ['npm', 'node_modules/.bin/tsc'],
                'environment_files': ['package-lock.json']}
    configure([*checks(), mutation])
    change = plan('Type check unexpectedly mutates source after dispatch', ['mutates-source'])
    candidate = good.replace('sum', 'result')
    details = failed(change, candidate, 'WORKSPACE_CHANGED')
    assert details['workspace_change']['check_id'] == 'mutates-source'
    assert any(item['path'] == 'src/total.ts' and item['change'] == 'modified' for item in details['workspace_change']['paths'])
    assert details['execution']['business_files'] == 'committed'
    assert details['execution']['files_stage_committed'] and details['execution']['checks_only_continuation_available']
    assert source.read_text() == candidate + '\n// controlled check-side mutation\n'
    retire(change)
    outcomes.append({'case': 'check_source_mutation', 'error': 'WORKSPACE_CHANGED',
                     'business_files': 'committed', 'original_side_effect_preserved': True, 'path_and_check_reported': True})
    with runtime.snapshot() as db:
        assert not db.execute("SELECT 1 FROM phase_runs WHERE status='started'").fetchone()
        assert not db.execute('SELECT 1 FROM resource_claims').fetchone()
        assert all(row[0] == 'cancelled' for row in db.execute('SELECT state FROM changes'))
    save(runtime.evidence / 'summary.json', {'passed': True, 'kind': 'controlled_engineering_faults',
        'content_digest': content_digest, 'outcomes': outcomes, 'original_inputs_preserved': True,
        'business_goal_completed': False, 'model_requests_sent': False,
        'scope': 'Expected execution-boundary failures, their actual physical effects and same-plan repair; not final model acceptance.'})
    print(json.dumps({'passed': True, 'faults': len(outcomes), 'evidence': str(runtime.evidence)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--offline', action='store_true', help='Use only the existing npm cache')
    parser.add_argument('--faults-only', action='store_true', help='Rehearse missing tools, real post-write compile failure, and check-side source mutation')
    args = parser.parse_args()
    package = args.package.resolve()
    sys.path.insert(0, str(package / 'runtime'))
    from evolve_core.package import check_package
    from evolve_core.reading import history_snapshot
    manifest = check_package(package)
    lab = args.out.resolve()
    lab.mkdir(parents=True, exist_ok=False)
    project, evidence = lab / 'project', lab / 'evidence'
    project.mkdir(); evidence.mkdir()
    original = prepare_project(project, evidence, offline=args.offline)
    auth = {'source': 'controlled-temporary-engineering-regression',
        'text': ('Rehearse only declared missing-tool, post-write compile and check-side source-mutation failures in the disposable fixture, retaining original inputs and actual failures.' if args.faults_only else
                 'Run the isolated fixture through the exact total.ts refactor, real checks, archive and cleanup of its reproducible review copy.'),
        'effect_kinds': ['project_records', 'business_files', 'checks'], 'paths': ['src/total.ts']}
    runtime = Runtime(package, project, evidence, auth)
    runtime.history_snapshot = history_snapshot
    call = runtime.call
    call('init', {'checks': checks()})
    if args.faults_only:
        run_faults(runtime, original, manifest['content_digest'])
        return
    review = [{'views': VIEWS, 'result': 'unchanged', 'source_paths': list(READONLY),
        'basis': 'Only the existing private algorithm changes; public sum, module location, page, domain, dependencies and original checks retain their meanings.'}]
    text = 'Replace reduce with an explicit sum loop, retaining original literals and all page and tool inputs.'
    plan = call('propose', {'title': 'Next engineering regression', 'plan': text, 'completion': 'Original literal examples, types and Next build pass.',
        'scope': ['src/total.ts'], 'required_checks': ['environment', 'unit', 'types', 'build'],
        'acceptance': ['Positive, empty and negative sums remain unchanged.', 'Types and Next production build pass.'],
        'knowledge_review': review, 'review_policy': 'self_allowed', 'pre_refactor': True,
        'preservation_checks': ['unit', 'types', 'build'], 'preservation_inputs': list(READONLY),
        'presentation': {'source': 'controlled-exact-engineering-plan', 'text': text}})
    applied = call('apply', {'files': [{'path': 'src/total.ts', 'expected_digest': sha((project / 'src/total.ts').read_bytes()),
        'content': 'export function total(values: number[]): number { let sum = 0; for (const value of values) { sum += value; } return sum; }\n'}]}, target=plan['change_id'])
    assert applied['preservation']['status'] == 'passed'
    assert all(item['executed'] for item in applied['task_checks'])
    verified = call('verify', {'reviews': runtime.review(plan)}, target=plan['change_id'])
    assert verified['status'] == 'passed'
    assert {item['check_id'] for item in verified['checks'] if item['reused']} == {'types', 'build'}
    fresh = call('verify', {'reviews': runtime.review(plan), 'fresh_checks': ['types', 'build']}, target=plan['change_id'])
    assert fresh['status'] == 'passed' and all(item['executed'] for item in fresh['checks'])
    call('sync', {'change_id': plan['change_id'], 'revision_id': plan['revision_id'], 'observations': [], 'knowledge_review': review}, method='assess')
    closed = call('archive', {'verification_id': fresh['verification_id']}, target=plan['change_id'])
    assert closed['outcome'] == 'archived' and closed['change_view']['status'] == 'ready'
    source = runtime.reference(fresh['run_id'])
    copied = call('maintain', {'kind': 'review_copy', 'source': source}, method='export')
    assert copied['index_status'] == 'written'
    unknown = project / '.evolve-local/review/manual.md'
    unknown.write_text('Manual observation retained outside automatic cleanup.\n')
    inventory = call('maintain', method='materials')['materials']
    assert any(item['path'] == copied['output'] for item in inventory['cleanup_candidates'])
    planned = call('maintain', {'stage': 'plan', 'paths': [copied['output']]}, method='clean')
    cleaned = call('maintain', {'stage': 'apply', 'paths': [copied['output']],
        'plan_source': runtime.reference(planned['run_id'])}, method='clean')
    assert cleaned['outcome'] == 'review_cleanup_completed' and unknown.is_file()
    assert not (project / copied['output']).exists()
    assert all((project / name).read_bytes() == content for name, content in original.items())
    assert (project / '.next/BUILD_ID').is_file() and (project / 'tsconfig.tsbuildinfo').is_file()
    assert runtime.reference(fresh['run_id']) == source
    save(evidence / 'summary.json', {'passed': True, 'content_digest': manifest['content_digest'],
        'change_id': plan['change_id'], 'real_next_build': True, 'real_incremental_types': True,
        'original_inputs_preserved': True, 'preservation_pair_actual': True, 'explicit_reuse_observed': True,
        'fresh_checks_actual': True, 'archive': closed['outcome'], 'review_cleanup': cleaned['outcome'],
        'unknown_material_preserved': True, 'model_requests_sent': False,
        'semantic_review': 'controlled_fixture_self_review_only'})
    print(json.dumps({'passed': True, 'evidence': str(evidence)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
