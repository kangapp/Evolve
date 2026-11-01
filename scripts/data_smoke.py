#!/usr/bin/env python3
"""Replay the controlled SQL fixture through an independent package's public CLI.

The test fixture supplies literal assertions and controlled review observations;
this controller sends no model requests and is not part of the distributed plugin.
"""
import argparse
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'tests'))
import test_sql_workflow as fixture
from evolve_core.package import canonical, digest
from evolve_core.store import now


def run(package, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    package = Path(package).resolve()
    runtime = package / 'runtime/evolve.py'
    commands, analyses = [], []

    def call(root, action, payload=None, *, method=None, target=None, expected=0):
        owner = {'init': 'init', 'analyze': 'propose', 'propose': 'propose', 'apply': 'apply',
                 'verify': 'verify', 'archive': 'archive', 'maintain': 'maintain',
                 'status': 'workflow', 'resume': 'workflow'}[action]
        argv = [sys.executable, '-B', str(runtime), '--project', str(root), action]
        if target:
            argv.append(target)
        argv += ['--owner', 'evolve-' + owner]
        if method:
            argv += ['--method', method]
        if payload is not None:
            argv += ['--request', '-']
        result = subprocess.run(argv, input=json.dumps(payload) if payload is not None else None,
                                cwd=output, capture_output=True, text=True, timeout=60)
        response = json.loads(result.stdout)
        commands.append({'argv': argv, 'request': payload, 'exit_code': result.returncode,
                         'response': response, 'stderr': result.stderr})
        (output / 'commands.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2))
        if result.returncode != expected:
            raise AssertionError('Unexpected CLI result; inspect ' + str(output / 'commands.json'))
        saved = ({key: value for key, value in response['data'].items()
                  if key not in ('request_context', 'input_bindings', 'result_digest')}
                 if response['ok'] else None)
        if action == 'analyze' and response['ok']:
            assert response['data']['result_digest'] == digest(canonical(saved))
            analyses.append((copy.deepcopy(payload), saved))
        return saved if response['ok'] else response

    f = fixture.SQLWorkflowTests()
    try:
        with ExitStack() as stack:
            for name, action in (('connect', 'init'), ('investigate', 'analyze'), ('propose', 'propose'),
                                 ('implement', 'apply'), ('verify', 'verify'), ('archive', 'archive')):
                stack.enter_context(patch.object(fixture, name,
                    lambda root, payload, action=action: call(root, action, payload)))
            f.setUp()
            original_inputs = {name: (f.root / name).read_bytes() for name in ('orders.json', 'test_reconciliation.py')}
            before = f.literal_check()
            (output / 'original-red.txt').write_text(before.stdout + before.stderr)
            verified = f.finish()
            after = f.literal_check()
            (output / 'original-green.txt').write_text(after.stdout + after.stderr)
        request, original = analyses[0]
        reference = {'run_id': original['run_id'], 'result_digest': digest(canonical(original))}
        readonly = {'source': 'controlled-data-public-CLI-fixture', 'text': 'Save bounded investigation and disposable report only.',
                    'effect_kinds': ['project_records']}
        request = copy.deepcopy(request)
        request['authorization'] = readonly
        data = request['input']
        data['question'] = 'What finite relationship is visible in the repaired SQL?'
        for source in data['sources']:
            if source['kind'] == 'file':
                source['expected_digest'] = digest((f.root / source['path']).read_bytes())
                source['observed_at'] = now()
        data['sources'] = [s for s in data['sources'] if s['kind'] == 'file']
        data['analysis'].pop('symptom')
        data['analysis'].update(answer_status='partial', conclusion='Saved SQL derives daily totals from the local orders fixture.',
            remaining_questions=['Production coverage and upstream origin were not observed.'])
        data['analysis']['observations'] = [{'local_key': 'F1', 'statement': 'SQL selects one date and the latest order revision before null filtering.', 'sources': ['S2']}]
        data['analysis']['relationships'][0]['transformation'] = 'Filter date; latest order revision; exclude null; aggregate amount and count.'
        relation = call(f.root, 'analyze', request)
        relation_ref = {'run_id': relation['run_id'], 'result_digest': digest(canonical(relation))}
        state = call(f.root, 'status')['project']
        assert len(state['analyses']) == 2 and len(state['changes']) == 1
        resumed = call(f.root, 'resume', target=relation['run_id'])
        assert resumed['context']['authorization_granted'] is False
        denied = copy.deepcopy(request)
        denied['input']['analysis']['data_context']['business_dates'].append('2026-11-02')
        rejected = call(f.root, 'analyze', denied, expected=2)
        assert rejected['error']['code'] == 'DATA_SOURCE_SCOPE'
        source_bytes = (f.root / 'model.sql').read_bytes()
        (f.root / 'model.sql').unlink()
        (f.root / 'orders.json').unlink()
        exported = []
        for form, suffix in (('markdown', 'md'), ('json', 'json')):
            payload = {'authorization': readonly, 'input': {'source': relation_ref,
                       'output': '.evolve-local/exports/lineage.' + suffix, 'format': form}}
            result = call(f.root, 'maintain', payload, method='export')
            assert result['outcome'] == 'exported' and result['business_sources_reobserved'] is False
            exported.append(result)
        report = (f.root / '.evolve-local/exports/lineage.md').read_text()
        assert '```mermaid' in report and 'partial' in report and 'not reobserved' in report
        saved_json = json.loads((f.root / '.evolve-local/exports/lineage.json').read_text())
        assert saved_json['analysis'] == relation['analysis']
        assert saved_json['source'] == relation_ref
        conflict = call(f.root, 'maintain', {'authorization': readonly,
            'input': {'source': reference, 'output': '.evolve-local/exports/lineage.md'}}, method='export')
        assert conflict['outcome'] == 'view_stale'
        assert (f.root / '.evolve-local/exports/lineage.md').read_text() == report
        state = call(f.root, 'status')['project']
        assert len(state['analyses']) == 2 and len(state['changes']) == 1
        assert not state['pending_runs']
        assert (f.root / 'test_reconciliation.py').read_bytes() == original_inputs['test_reconciliation.py']
        # Restore only controller-removed inputs, then record a genuine later failure.
        (f.root / 'orders.json').write_bytes(original_inputs['orders.json'])
        (f.root / 'model.sql').write_bytes(source_bytes)
        changed = json.loads(original_inputs['orders.json'])
        changed[1][3] = changed[2][3] = 99
        (f.root / 'orders.json').write_text(json.dumps(changed))
        failed = f.literal_check()
        (output / 'later-red.txt').write_text(failed.stdout + failed.stderr)
        assert failed.returncode == 1
        result = call(f.root, 'verify', f.verify_request('failed', failed.stdout + failed.stderr))
        assert result['status'] in ('failed', 'blocked')
        assert f.rows('SELECT state FROM changes')[0]['state'] == 'archived'
        assert f.rows('SELECT status FROM verifications WHERE id=?', (verified['verification_id'],))[0]['status'] == 'passed'
        shutil.copytree(f.root, output / 'project')
        summary = {'passed': True, 'model_requests_sent': False, 'review_inputs': 'Controlled actual observations, not independent model review',
            'commands': len(commands), 'package': str(package), 'original_criterion_before': before.returncode,
            'original_criterion_after': after.returncode, 'sql_change': 'archived',
            'bounded_relationship_analysis': relation_ref, 'separate_topics': 2,
            'source_removed_export_formats': [r['format'] for r in exported],
            'conflict': conflict['outcome'], 'later_verification': result['status'],
            'historical_pass_preserved': True, 'formal_data_executed': False}
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    finally:
        f.doCleanups()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.package, args.out), ensure_ascii=False, indent=2))
