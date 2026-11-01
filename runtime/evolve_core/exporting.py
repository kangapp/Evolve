"""Regenerate disposable reports from sealed analysis, never business sources."""
import html
import json
from pathlib import Path

from .analysis import analysis_reference, analysis_views
from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store, now
from .workspace import current_digest, durable_write, inside, writer_lock


def output_path(root, data):
    name, form = data.get('output'), data.get('format', 'markdown')
    if (form not in ('markdown', 'json') or not isinstance(name, str)
            or not name.startswith('.evolve-local/exports/')
            or not name.endswith('.md' if form == 'markdown' else '.json')):
        raise EvolveError('EXPORT_PATH', 'Choose a new .md or .json file inside .evolve-local/exports')
    path = inside(root, name)
    if path.resolve() != path:
        raise EvolveError('EXPORT_PATH', 'Export paths must not use linked files or directories')
    return path, form


def markdown(report):
    analysis = report['analysis']
    lines = ['# Evolve analysis report', '', 'Source: ' + report['source']['run_id'],
             'Result digest: ' + report['source']['result_digest'], 'Generated: ' + report['generated_at'],
             'Business sources were not reobserved during export.', '',
             'Answer status: ' + analysis['answer_status'], '', analysis['conclusion'], '']
    if analysis.get('data_context') is not None:
        lines += ['## Data context', '', '```json', json.dumps(analysis['data_context'], ensure_ascii=False, indent=2), '```', '']
    for title, key in (('Coverage', 'coverage'), ('Limitations', 'limitations'), ('Remaining questions', 'remaining_questions'), ('Next steps', 'next_steps')):
        lines += ['## ' + title, ''] + ['- ' + item for item in analysis[key]] + ['']
    for title, key in (('Observations', 'observations'), ('Hypotheses', 'hypotheses')):
        lines += ['## ' + title, '']
        for item in analysis[key]:
            refs = item.get('sources', item.get('observations', []))
            lines += ['- ' + item['local_key'] + ': ' + item['statement'] + ' [' + ', '.join(refs) + ']'
                      + (' (' + item['status'] + ')' if 'status' in item else '')]
        lines.append('')
    relations = analysis.get('relationships', [])
    if relations:
        nodes = list(dict.fromkeys(value for item in relations for value in (item['source'], item['target'])))
        lines += ['## Observed relationship scope', '', '```mermaid', 'flowchart LR']
        for index, label in enumerate(nodes):
            label = html.escape(label, quote=True).replace('\n', ' ').replace('\r', ' ')
            lines.append('  N' + str(index) + '["' + label + '"]')
        for item in relations:
            arrow = ' --> ' if item['certainty'] == 'observed' else ' -.-> '
            lines.append('  N' + str(nodes.index(item['source'])) + arrow + 'N' + str(nodes.index(item['target'])))
        lines += ['```', '']
        for item in relations:
            lines += ['- ' + item['local_key'] + ' (' + item['certainty'] + '): ' + item['source'] + ' -> ' + item['target']
                      + '; ' + item['transformation'] + '; sources: ' + ', '.join(item['sources'])]
            lines += ['  - ' + limit for limit in item['limitations']]
        lines.append('')
    lines += ['## Source observations', '']
    for item in report['sources']:
        lines += ['- ' + item['id'] + ': ' + item.get('path', item.get('object', 'unknown'))
                  + '; observer: ' + item['observer'] + '; observed: ' + str(item.get('observed_at') or 'unknown')
                  + '; version: ' + str(item.get('version', item.get('expected_digest', 'unknown')))]
        lines += ['  - ' + limit for limit in item['limitations']]
    lines += ['', '## Recorded successor and corrections', '',
              'Current recorded head: ' + report['recorded_head'],
              json.dumps(report['recorded_corrections'], ensure_ascii=False, indent=2), '']
    return '\n'.join(lines).encode('utf-8')


def export_analysis(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    require_effect(request, 'project_records')
    with writer_lock(root):
        store = Store(root)
        try:
            previous = store.lookup(request, action='maintain', method='export', owner='evolve-maintain')
            if previous is not None:
                return previous[1]
            path, form = output_path(root, request['input'])
            source = request['input'].get('source')
            original, result = analysis_reference(store.connection, source)
            view = analysis_views(store.connection, original['id'])[0]
            report = {'source': {'run_id': original['id'], 'result_digest': original['result_digest']},
                      'generated_at': now(), 'business_sources_reobserved': False,
                      'analysis': result['analysis'], 'sources': result['sources'], 'evidence': result['evidence'],
                      'recorded_head': view['current_head'], 'recorded_corrections': view['current_corrections']}
            content = markdown(report) if form == 'markdown' else canonical(report) + b'\n'
            run_id, _ = store.start(request, action='maintain', method='export', owner='evolve-maintain')
            with store.transaction() as connection:
                blob = store.blob(content)
                store.link_source(run_id, original['id'], original['result_digest'], 'analysis_export')
                store.event(run_id, 'analysis_export_prepared', {'output': request['input']['output'],
                    'format': form, 'content_digest': blob, 'source': report['source']})
            error = None
            try:
                durable_write(path, content, new=True)
                status = 'written' if current_digest(path) == blob else 'stale'
            except (OSError, EvolveError) as failure:
                status, error = 'stale', str(failure)
            return store.finish(run_id, {'committed': True, 'outcome': 'exported' if status == 'written' else 'view_stale',
                'source': report['source'], 'output': request['input']['output'], 'format': form,
                'content_digest': blob, 'view_status': status, 'view_error': error,
                'view_observed_at': now(), 'view_applicability': 'recorded_observation_not_live_guarantee',
                'business_commands_run': False, 'business_sources_reobserved': False})
        finally:
            store.close()


def interrupted_export(store, original_id):
    rows = store.connection.execute("SELECT payload_json FROM events WHERE run_id=? AND kind='analysis_export_prepared'", (original_id,)).fetchall()
    if len(rows) != 1:
        return {'outcome': 'export_interrupted', 'view_status': 'not_prepared', 'business_sources_reobserved': False}
    prepared = json.loads(rows[0]['payload_json'])
    path, _ = output_path(store.root, prepared)
    blob = store.one('SELECT content FROM blobs WHERE digest=?', (prepared['content_digest'],))
    if blob is None or digest(blob['content']) != prepared['content_digest']:
        raise EvolveError('EXPORT_RECORD_INVALID', 'Saved report differs from its prepared digest')
    try:
        status = 'written' if current_digest(path) == prepared['content_digest'] else 'stale'
    except (OSError, EvolveError):
        status = 'stale'
    return {**prepared, 'outcome': 'export_interrupted', 'view_status': status,
            'business_sources_reobserved': False, 'view_rewritten': False}
