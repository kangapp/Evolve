"""Read-only business investigations; immutable records reuse runs and evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import socket
import sqlite3

from .errors import EvolveError
from .package import canonical, digest
from .privacy import ensure_recordable
from .requests import normalize, require_effect
from .store import Store, identifier, now
from .workspace import current_digest, inside, process_alive, writer_lock


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return isinstance(value, list) and all(text(item) for item in value)


def source_material(root, data):
    sources, content = {}, {}
    if not isinstance(data.get('sources'), list) or not data['sources']:
        raise EvolveError('ANALYSIS_SOURCE', 'Investigation requires explicit actual sources')
    for item in data['sources']:
        if not isinstance(item, dict) or not text(item.get('id')) or item['id'] in sources:
            raise EvolveError('ANALYSIS_SOURCE', 'Source identities must be distinct')
        if not text(item.get('observer')) or not strings(item.get('limitations')):
            raise EvolveError('ANALYSIS_SOURCE', 'Sources identify the actual observer and limitations')
        observed = item.get('observed_at')
        if observed is None:
            if not item['limitations']:
                raise EvolveError('ANALYSIS_SOURCE', 'Unknown observation time requires an explicit limitation')
        else:
            try:
                time = datetime.fromisoformat(observed)
                if time.tzinfo is None or time > datetime.now(timezone.utc):
                    raise ValueError('Unbound or future observation time')
            except (TypeError, ValueError):
                raise EvolveError('ANALYSIS_SOURCE', 'Observation time must include a timezone; do not invent a missing date')
        kind = item.get('kind')
        if kind == 'file':
            path = inside(root, item.get('path'))
            if not any(path == inside(root, scope) or inside(root, scope) in path.parents for scope in data['scope']):
                raise EvolveError('ANALYSIS_SCOPE', 'File source is outside the declared investigation scope')
            actual = current_digest(path)
            if actual is None or actual != item.get('expected_digest'):
                raise EvolveError('ANALYSIS_SOURCE_CHANGED', 'File source differs from the supplied observation: ' + item['path'], exit_code=3)
            content[item['id']] = path.read_bytes()
            if digest(content[item['id']]) != actual:
                raise EvolveError('ANALYSIS_SOURCE_CHANGED', 'File source changed while reading', exit_code=3)
        elif kind in ('observation', 'reference'):
            if any(not text(item.get(k)) for k in ('object', 'method')) or 'version' not in item:
                raise EvolveError('ANALYSIS_SOURCE', 'External evidence needs its object, method and known or explicitly unknown version')
            if item['version'] is None and not item['limitations']:
                raise EvolveError('ANALYSIS_SOURCE', 'Unknown evidence version requires an explicit limitation')
            if kind == 'observation':
                if not text(item.get('content')):
                    raise EvolveError('ANALYSIS_SOURCE', 'Save the actual observation, not just its claimed outcome')
                content[item['id']] = item['content'].encode('utf-8')
            elif not text(item.get('location')) or not item['limitations'] or item.get('content') is not None:
                raise EvolveError('ANALYSIS_SOURCE', 'Unsaved external references require their location and retrieval limitations')
        else:
            raise EvolveError('ANALYSIS_SOURCE', 'Source kind must be file, observation or reference')
        sources[item['id']] = item
    return sources, content


def validate_analysis(data, sources):
    analysis = data.get('analysis')
    if not isinstance(analysis, dict) or analysis.get('answer_status') not in ('answered', 'partial', 'inconclusive'):
        raise EvolveError('ANALYSIS', 'Use answered, partial or inconclusive independently of run completion')
    if not text(analysis.get('conclusion')) or any(not strings(analysis.get(k)) for k in ('coverage', 'limitations', 'remaining_questions', 'next_steps')):
        raise EvolveError('ANALYSIS', 'Analysis requires conclusion, coverage, limitations, remaining questions and next steps')
    if analysis['answer_status'] != 'answered' and (not analysis['limitations'] or not analysis['remaining_questions']):
        raise EvolveError('ANALYSIS', 'Partial or inconclusive answers retain their limits and unanswered questions')
    facts = analysis.get('observations')
    hypotheses = analysis.get('hypotheses')
    if not isinstance(facts, list) or not isinstance(hypotheses, list):
        raise EvolveError('ANALYSIS', 'Observations and hypotheses are separate explicit arrays')
    known = set()
    for group, prefix in ((facts, 'F'), (hypotheses, 'H')):
        for item in group:
            if (not isinstance(item, dict) or not re.fullmatch(prefix + r'[1-9][0-9]*', str(item.get('local_key')))
                    or item['local_key'] in known or not text(item.get('statement'))):
                raise EvolveError('ANALYSIS', 'Facts and hypotheses require distinct run-local F1/H1 identities and statements')
            refs = item.get('sources') if prefix == 'F' else item.get('observations')
            available = set(sources) if prefix == 'F' else {f['local_key'] for f in facts}
            if not strings(refs) or not refs or not set(refs).issubset(available):
                raise EvolveError('ANALYSIS', 'Each claim must refer to actual sources or observations in this run')
            if prefix == 'H' and (item.get('status') not in ('unconfirmed', 'supported', 'refuted')
                                   or not text(item.get('basis'))):
                raise EvolveError('ANALYSIS', 'Hypotheses retain their strength and supporting or exclusion basis')
            known.add(item['local_key'])
    symptom = analysis.get('symptom')
    if symptom is not None:
        if not isinstance(symptom, dict) or not isinstance(symptom.get('criterion'), dict):
            raise EvolveError('SYMPTOM', 'A diagnostic symptom requires its repeatable criterion')
        criterion = symptom['criterion']
        if (any(not text(criterion.get(k)) for k in ('method', 'environment', 'side_effects'))
                or 'input' not in criterion or 'expected' not in criterion
                or not isinstance(criterion.get('expected_source'), str) or criterion['expected_source'] not in sources):
            raise EvolveError('SYMPTOM', 'Criterion binds actual method, environment, input, independent expected source and side effects')
        if symptom.get('status') not in ('reproduced', 'not_reproduced', 'blocked', 'historical'):
            raise EvolveError('SYMPTOM', 'Save actual reproduction status; missing red is not a failure observation')
        counts = (symptom.get('attempts'), symptom.get('failures'))
        if any(value is not None and (type(value) is not int or value < 0) for value in counts):
            raise EvolveError('SYMPTOM', 'Save actual nonnegative attempt and failure counts, or explicit unknowns')
        if None not in counts and symptom['failures'] > symptom['attempts']:
            raise EvolveError('SYMPTOM', 'Failure count cannot exceed actual attempts')
        if (not strings(symptom.get('sources')) or not symptom['sources']
                or not set(symptom['sources']).issubset(sources) or not strings(symptom.get('limitations'))):
            raise EvolveError('SYMPTOM', 'Reproduction requires actual source references and explicit limits')
        if symptom['status'] in ('reproduced', 'not_reproduced'):
            observed = [sources[key] for key in symptom['sources'] if sources[key]['kind'] == 'observation']
            if None in counts or symptom['attempts'] < 1 or not any(item.get('observed_at') is not None for item in observed):
                raise EvolveError('SYMPTOM', 'Reproduction status requires a retained, dated actual observation and real attempt counts')
            if (symptom['status'] == 'reproduced' and symptom['failures'] < 1) or (symptom['status'] == 'not_reproduced' and symptom['failures'] != 0):
                raise EvolveError('SYMPTOM', 'Reproduction status differs from the supplied failure count')
        if symptom['status'] != 'reproduced' and not symptom['limitations']:
            raise EvolveError('SYMPTOM', 'Historical, missing reproduction or access keeps its explicit limitation')
        if symptom.get('intermittent') is True and (not text(symptom.get('trigger')) or not text(symptom.get('window')) or not symptom['limitations']):
            raise EvolveError('SYMPTOM', 'Intermittent observations retain trigger, time window and sampling limitations')
    from .data_material import validate_material
    validate_material(analysis, sources)
    return analysis


def analysis_runs(connection):
    runs = []
    for row in connection.execute("SELECT * FROM phase_runs WHERE action='analyze'"):
        body = json.loads(row['input_json'])
        if (digest(canonical(body)) != row['input_digest']
                or (row['result_json'] is not None and digest(row['result_json'].encode()) != row['result_digest'])):
            raise EvolveError('ANALYSIS_RECORD_INVALID', 'Analysis input or result differs from its recorded digest; inspect history without rewriting it')
        runs.append({**dict(row), 'request': body['request']})
    return runs


def analysis_reference(connection, reference):
    if not isinstance(reference, dict) or not text(reference.get('run_id')) or not text(reference.get('result_digest')):
        raise EvolveError('ANALYSIS_REFERENCE', 'Analysis references bind a saved run and its immutable result digest')
    row = connection.execute("SELECT * FROM phase_runs WHERE id=? AND action='analyze'", (reference['run_id'],)).fetchone()
    if (not row or row['status'] != 'completed' or row['result_digest'] != reference['result_digest']
            or digest(row['result_json'].encode()) != row['result_digest']):
        raise EvolveError('ANALYSIS_REFERENCE', 'Referenced investigation is missing, incomplete or changed', exit_code=3)
    result = json.loads(row['result_json'])
    if not isinstance(result.get('analysis'), dict):
        raise EvolveError('ANALYSIS_REFERENCE', 'Referenced run does not contain a completed analysis record')
    return row, result


def repair_basis(connection, reference, checks, *, root=None):
    row, result = analysis_reference(connection, reference)
    if not text(reference.get('adoption_basis')):
        raise EvolveError('ANALYSIS_REFERENCE', 'Explain why the observed investigation is applicable to this repair')
    context = result['analysis'].get('data_context')
    if context and root is not None:
        from .data_material import source_applicability
        selected = [source for source in result['sources'] if source['id'] in context['source_ids']]
        if any(item['status'] in ('local_bytes_changed', 'unavailable') for item in source_applicability(root, selected)):
            raise EvolveError('DATA_EVIDENCE_CHANGED', 'Observed data inputs changed; obtain a new scoped observation before using this basis', exit_code=3)
    symptom = result['analysis'].get('symptom')
    if symptom:
        if reference.get('criterion_digest') != result['criterion_digest']:
            raise EvolveError('SYMPTOM_CHANGED', 'Repair must retain the observed criterion, not silently change its meaning', exit_code=3)
        check = symptom['criterion'].get('check')
        if check is not None and check not in checks:
            raise EvolveError('SYMPTOM_CHANGED', 'The original symptom check must remain in the repair check definition', exit_code=3)
    return row, result


def repair_task_verified(connection, root, task, definition):
    from .revisions import eligible_verifications
    from .work import fingerprint, verification_source
    verification = next(iter(eligible_verifications(connection, task['change_id'], task['revision_id'], task)), None)
    if verification is None or verification['status'] != 'passed' or verification_source(connection, verification) is None:
        return False
    items = json.loads(verification['items_json'])
    symptom = items.get('symptom_result', {})
    inspected = json.loads(verification['fingerprint_json'])
    current = fingerprint(root, definition)
    return (symptom.get('status') == 'passed'
        and symptom.get('criterion_digest') == definition['analysis_basis']['criterion_digest']
        and inspected.get('task_basis_digest') == current['task_basis_digest'])


def symptom_reverification(store, task, definition, snapshot, item):
    before = definition.get('symptom_before')
    if before is None:
        return None
    if not isinstance(item, dict):
        raise EvolveError('SYMPTOM_REVERIFY_REQUIRED', 'Record the actual post-repair observation using the original symptom criterion')
    if item.get('criterion_digest') != definition['analysis_basis']['criterion_digest']:
        raise EvolveError('SYMPTOM_CHANGED', 'Reverification cannot substitute a different symptom or lower its expectation', exit_code=3)
    if item.get('fingerprint_digest') != snapshot['digest']:
        raise EvolveError('STALE_REVIEW', 'Symptom observation does not describe the current workspace', exit_code=3)
    if (item.get('status') not in ('passed', 'failed', 'blocked')
            or any(not text(item.get(k)) for k in ('observer', 'basis', 'evidence'))
            or not strings(item.get('limitations'))):
        raise EvolveError('SYMPTOM', 'Reverification retains actual observer, evidence, assessment and limitations')
    try:
        observed = datetime.fromisoformat(item['observed_at'])
        if observed.tzinfo is None or observed > datetime.now(timezone.utc):
            raise ValueError('Unknown or future observation')
        for row in store.connection.execute("SELECT payload_json,recorded_at FROM events WHERE kind='task_result'"):
            if json.loads(row['payload_json'])['task_id'] == task['id'] and observed < datetime.fromisoformat(row['recorded_at']):
                raise ValueError('Observation predates the current task result')
    except (KeyError, TypeError, ValueError):
        raise EvolveError('SYMPTOM', 'Post-repair observation time must follow the current task result and be explicit')
    counts = (item.get('attempts'), item.get('failures'))
    if any(type(value) is not int or value < 0 for value in counts) or counts[1] > counts[0]:
        raise EvolveError('SYMPTOM', 'Reverification states its actual attempt and failure counts')
    if item['status'] == 'passed' and (counts[0] < 1 or counts[1] != 0):
        raise EvolveError('SYMPTOM', 'Passing observation requires actual attempts without an observed symptom failure')
    if item['status'] == 'failed' and counts[1] < 1:
        raise EvolveError('SYMPTOM', 'Failing observation requires an actual observed failure')
    bounded = before['status'] not in ('reproduced', 'historical') or (before.get('intermittent') is True and counts[0] <= 1)
    if bounded and not item['limitations']:
        raise EvolveError('SYMPTOM_LIMITATIONS', 'Missing red or one intermittent absence cannot prove elimination; retain the limitation')
    return {**item, 'before_status': before['status'], 'bounded_observation_only': bounded,
            'causal_resolution': 'not_inferred'}


def correction_sources(connection, analysis):
    references = []
    for item in analysis['observations'] + analysis['hypotheses']:
        if not isinstance(item.get('corrects', []), list):
            raise EvolveError('ANALYSIS_REFERENCE', 'Corrections are explicit run/digest/local-key references')
        for ref in item.get('corrects', []):
            row, result = analysis_reference(connection, ref)
            claims = result['analysis']['observations'] + result['analysis']['hypotheses']
            if ref.get('local_key') not in {claim['local_key'] for claim in claims}:
                raise EvolveError('ANALYSIS_REFERENCE', 'Correction refers to a nonexistent prior finding')
            references.append((row['id'], row['result_digest']))
    return sorted(set(references))


def analysis_views(connection, target=None, *, root=None):
    runs = {r['id']: r for r in analysis_runs(connection)}
    children = {}
    for row in runs.values():
        previous = row['request']['input'].get('previous')
        if previous:
            if previous['run_id'] not in runs or previous['run_id'] in children:
                raise EvolveError('ANALYSIS_CHAIN', 'Analysis history is missing a parent or contains multiple successors')
            children[previous['run_id']] = row['id']
    def head(run_id):
        seen = set()
        while run_id in children:
            if run_id in seen:
                raise EvolveError('ANALYSIS_CHAIN', 'Analysis history contains a cycle')
            seen.add(run_id)
            run_id = children[run_id]
        return run_id
    if target in runs:
        selected = [target]
    elif target:
        selected = sorted({head(r['id']) for r in runs.values() if r['request']['input']['question'] == target})
    else:
        selected = sorted({head(run_id) for run_id in runs})
    views = []
    for run_id in selected:
        row = runs[run_id]
        latest = runs[head(run_id)]
        result = json.loads(row['result_json']) if row['result_json'] else {}
        current = json.loads(latest['result_json']) if latest['result_json'] else {}
        topic = {key for key in runs if head(key) == latest['id']}
        corrections = []
        for source in runs.values():
            saved = json.loads(source['result_json']) if source['result_json'] else {}
            for item in saved.get('analysis', {}).get('observations', []) + saved.get('analysis', {}).get('hypotheses', []):
                if any(ref['run_id'] in topic for ref in item.get('corrects', [])):
                    corrections.append({**item, 'source_run_id': source['id'], 'result_digest': source['result_digest']})
        from .data_material import source_applicability
        view = {'run_id': row['id'], 'question': row['request']['input']['question'],
                'run_status': row['status'], 'answer_status': result.get('analysis', {}).get('answer_status'),
                'result_digest': row['result_digest'], 'recorded_at': row['ended_at'],
                'criterion_digest': result.get('criterion_digest'),
                'current_head': latest['id'], 'current_head_status': latest['status'],
                'details_loaded': bool(target), 'business_effect': 'read_only', 'correction_count': len(corrections),
                'limitations': current.get('analysis', {}).get('limitations'),
                'source_applicability': source_applicability(root, result.get('sources', []))}
        if target:
            view.update(analysis=result.get('analysis'), sources=result.get('sources'), evidence=result.get('evidence'),
                        previous=row['request']['input'].get('previous'), parent=row['request']['input'].get('parent'),
                        current_conclusion=current.get('analysis', {}).get('conclusion'),
                        current_limitations=current.get('analysis', {}).get('limitations'),
                        current_corrections=corrections)
            if result.get('analysis') is None:
                view['unfinished_input'] = row['request']['input']
                view['retained_evidence'] = [dict(item) for item in connection.execute(
                    'SELECT id,observer,method,content_digest,observed_at,limitations FROM evidence WHERE source_run_id=?', (run_id,))]
                view['draft_is_completed_answer'] = False
        views.append(view)
    return views


def check_previous(store, previous):
    if previous is None:
        return None
    if not isinstance(previous, dict) or not text(previous.get('run_id')):
        raise EvolveError('ANALYSIS_PREVIOUS', 'Continuation names its observed head and result digest')
    runs = {r['id']: r for r in analysis_runs(store.connection)}
    target = runs.get(previous['run_id'])
    if not target or target['result_digest'] != previous.get('result_digest'):
        raise EvolveError('ANALYSIS_PREVIOUS', 'Previous must identify an actual same-project analysis result', exit_code=3)
    if target['status'] == 'started':
        raise EvolveError('ANALYSIS_RUNNING', 'Previous analysis has not safely ended', exit_code=3)
    if any((r['request']['input'].get('previous') or {}).get('run_id') == target['id'] for r in runs.values()):
        raise EvolveError('ANALYSIS_HEAD', 'This analysis already has a successor; read the current head', exit_code=3)
    seen, cursor = set(), target
    while cursor:
        if cursor['id'] in seen:
            raise EvolveError('ANALYSIS_CHAIN', 'Analysis ancestry contains a cycle')
        seen.add(cursor['id'])
        pointer = cursor['request']['input'].get('previous')
        cursor = runs.get(pointer['run_id']) if pointer else None
        if pointer and cursor is None:
            raise EvolveError('ANALYSIS_CHAIN', 'Analysis ancestry is incomplete')
    return target


def check_parent(store, parent, scope):
    if parent is None:
        return
    if not isinstance(parent, dict):
        raise EvolveError('ANALYSIS_PARENT', 'Parent requires its active execution binding')
    row = store.one('SELECT * FROM phase_runs WHERE id=?', (parent.get('run_id'),))
    if (not row or row['status'] != 'started' or row['action'] not in ('apply', 'verify', 'analyze')
            or row['input_digest'] != parent.get('input_digest')
            or json.loads(row['execution_instance']) != parent.get('execution_instance')):
        raise EvolveError('ANALYSIS_PARENT', 'Parent is no longer the observed active phase; use a standalone investigation', exit_code=3)
    try:
        body = json.loads(row['input_json'])
        if digest(canonical(body)) != row['input_digest']:
            raise EvolveError('ANALYSIS_PARENT', 'Active parent input no longer matches the observed digest', exit_code=3)
        request = body['request']
    except (ValueError, TypeError, KeyError):
        raise EvolveError('ANALYSIS_PARENT', 'Active parent input is not a valid frozen request', exit_code=3)
    execution = json.loads(row['execution_instance'])
    if execution['host'] != socket.gethostname() or not process_alive(execution['pid']):
        raise EvolveError('ANALYSIS_PARENT', 'Parent execution is not locally confirmed active; inspect or recover it first', exit_code=3)
    from .work import gate_identity
    gate_identity(store, {**request, 'request_id': row['request_id']}, row['id'])
    data = request['input']
    if data.get('change_id'):
        task = store.one('SELECT definition_json FROM tasks WHERE change_id=? AND revision_id=?',
                         (data['change_id'], data['revision_id']))
        allowed = json.loads(task[0])['scope'] if task else []
    else:
        allowed = data.get('scope', [])
    if not all(any(inside(store.root, name) == inside(store.root, base) or inside(store.root, base) in inside(store.root, name).parents for base in allowed) for name in scope):
        raise EvolveError('ANALYSIS_PARENT', 'Investigation extends beyond the current parent phase scope')


def prepared_analysis(root, data):
    if not text(data.get('question')) or not strings(data.get('scope')) or not data['scope']:
        raise EvolveError('ANALYSIS_SCOPE', 'Question and actual investigation scope are required')
    for name in data['scope']:
        inside(root, name)
    sources, content = source_material(root, data)
    analysis = validate_analysis(data, sources)
    return sources, content, analysis


def investigate(root, payload):
    root = Path(root).resolve()
    request = normalize(payload)
    data = request['input']
    if data.get('business_effect') != 'read_only' or data.get('record_intent') not in ('record', 'answer_only'):
        raise EvolveError('ANALYSIS_INTENT', 'Investigation explicitly separates read-only business intent from record intent')
    if data['record_intent'] == 'answer_only':
        require_effect(request, 'read_only')
        sources, content, analysis = prepared_analysis(root, data)
        if (data.get('previous') is not None or data.get('parent') is not None
                or any(item.get('corrects') for item in analysis['observations'] + analysis['hypotheses'])):
            raise EvolveError('ANALYSIS_INTENT', 'Answer-only queries do not create or continue recorded chains')
        return {'committed': False, 'outcome': 'answered_without_record', 'run_id': None, 'analysis': analysis,
                'sources': data['sources'], 'business_commands_run': False}
    require_effect(request, 'project_records')
    run_id = None
    with writer_lock(root):
        store = Store(root)
        try:
            repeated = store.lookup(request, action='analyze', method='investigate', owner='evolve-propose')
            if repeated is not None:
                return repeated[1]
            sources, content, analysis = prepared_analysis(root, data)
            for material in content.values():
                ensure_recordable(material)
            previous = check_previous(store, data.get('previous'))
            check_parent(store, data.get('parent'), data['scope'])
            corrections = correction_sources(store.connection, analysis)
            run_id, _ = store.start(request, action='analyze', method='investigate', owner='evolve-propose')
            for item in sources.values():
                if item['kind'] == 'file' and current_digest(inside(root, item['path'])) != item['expected_digest']:
                    raise EvolveError('ANALYSIS_SOURCE_CHANGED', 'Source changed before saving the investigation', exit_code=3)
            with store.transaction() as connection:
                if data.get('parent'):
                    store.input_check(run_id, 'phase_input', data['parent']['run_id'], data['parent']['input_digest'],
                        'analysis_parent', status='passed', code='PARENT_VALID',
                        reason='Actual active local parent input, execution, grant and investigation scope matched.')
                evidence = []
                for key, item in sources.items():
                    evidence_id = identifier()
                    body = content.get(key)
                    blob = store.blob(body if body is not None else canonical(item))
                    connection.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)',
                        (evidence_id, run_id, None, 'analysis', item['observer'], 'analysis:' + item['kind'], blob,
                         item.get('observed_at') or 'unknown', canonical({'limitations': item['limitations'],
                            'observation_time_unknown': item.get('observed_at') is None}).decode()))
                    evidence.append({'source_id': key, 'evidence_id': evidence_id, 'digest': blob,
                                     'retained_content': body is not None})
                if previous:
                    store.link_source(run_id, previous['id'], previous['result_digest'], 'analysis_previous')
                for source_id, source_digest in corrections:
                    store.link_source(run_id, source_id, source_digest, 'analysis_correction')
                store.event(run_id, 'analysis_sources_saved', {'evidence': evidence, 'business_effect': 'read_only'})
            result = {'committed': True, 'outcome': 'analyzed', 'targets': {'project_id': store.meta['project_id']},
                      'analysis': analysis, 'sources': data['sources'], 'evidence': evidence,
                      'previous': data.get('previous'), 'parent': data.get('parent'), 'business_commands_run': False}
            if analysis.get('symptom'):
                result['criterion_digest'] = digest(canonical(analysis['symptom']['criterion']))
            return store.finish(run_id, result)
        except EvolveError as error:
            if run_id is not None:
                if store.run_started(run_id):
                    store.finish(run_id, {'committed': True, 'outcome': 'analysis_incomplete',
                                         'analysis_saved': False, 'message': str(error)}, status='blocked')
                error.committed = True
            raise
        except (OSError, sqlite3.Error) as error:
            raise EvolveError('ANALYSIS_INCOMPLETE', 'Observations were supplied but complete analysis was not saved; inspect pending run ' + str(run_id),
                              exit_code=4, committed=run_id is not None,
                              next_steps=['Inspect saved input and evidence; do not invent a completed answer or rerun business commands']) from error
        finally:
            store.close()
