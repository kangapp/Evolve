"""Index local review copies; remove only sealed, reproducible, unreferenced copies."""
import json
import os
from pathlib import Path
import posixpath

from .continuation import retained_source, sealed_result
from .errors import EvolveError
from .package import canonical, digest
from .requests import normalize, require_effect
from .store import Store
from .workspace import current_digest, durable_write, inside, writer_lock

INDEX = '.evolve-local/review/index.json'


def local_path(root, name):
    if not isinstance(name, str) or not name.startswith('.evolve-local/review/'):
        raise EvolveError('REVIEW_PATH', 'Review copies belong inside .evolve-local/review')
    path = inside(root, name)
    if path.resolve() != path:
        raise EvolveError('REVIEW_PATH', 'Review material paths must not use links')
    return path


def owners(connection, meta, active_run=None):
    result = {}
    for row in connection.execute("SELECT run_id,payload_json FROM events WHERE kind='review_copy_prepared' ORDER BY rowid"):
        run = connection.execute('SELECT * FROM phase_runs WHERE id=?', (row['run_id'],)).fetchone()
        if not run or (run['status'] != 'completed' and run['id'] != active_run):
            continue
        item = json.loads(row['payload_json'])
        if run['id'] == active_run and run['status'] == 'started':
            request = json.loads(run['input_json'])['request']
            saved = {'output': item['path'], 'content_digest': item['content_digest']}
        else:
            _, request, saved = sealed_result(connection, {'run_id': run['id'], 'result_digest': run['result_digest']})
        if (retained_source(connection, run, request) and item.get('project_id') == meta['project_id']
                and saved.get('output') == item['path'] and saved.get('content_digest') == item['content_digest']):
            result[item['path']] = {**item, 'owner_run_id': run['id']}
    return result


def references(connection, root, name, owner):
    refs = []
    for row in connection.execute('SELECT id,action,method,input_json,result_json FROM phase_runs'):
        data = json.loads(row['input_json'])['request']['input']
        bookkeeping = row['action'] == 'maintain' and (row['method'] == 'clean'
            or row['method'] == 'export' and data.get('kind') in ('review_copy', 'review_index'))
        if row['id'] == owner or bookkeeping:
            continue  # Material bookkeeping does not make its own copies permanent.
        if name in row['input_json'] or name in (row['result_json'] or ''):
            refs.append({'kind': 'run', 'id': row['id']})
    for row in connection.execute('SELECT id,definition_json FROM tasks'):
        if name in row['definition_json']:
            refs.append({'kind': 'task', 'id': row['id']})
    for row in connection.execute("SELECT path FROM artifacts WHERE kind='knowledge' AND path IS NOT NULL"):
        try:
            path = inside(root, row['path'])
            if name in path.read_text():
                refs.append({'kind': 'knowledge', 'path': row['path']})
        except (OSError, UnicodeError, EvolveError):
            refs.append({'kind': 'knowledge_reference_unknown', 'path': row['path']})
    return refs


def index_digests(connection):
    values = set()
    for row in connection.execute("SELECT r.*,e.payload_json FROM events e JOIN phase_runs r ON r.id=e.run_id "
                                  "WHERE e.kind='review_index_prepared' AND r.status='completed'"):
        prepared = json.loads(row['payload_json'])
        _, request, result = sealed_result(connection, {'run_id': row['id'], 'result_digest': row['result_digest']})
        if retained_source(connection, row, request) and result.get('index_digest') == prepared['content_digest']:
            values.add(prepared['content_digest'])
    return values


def file_references(connection, root, owned):
    """Find literal project/relative links without retaining local file contents."""
    refs = {name: [] for name in owned}
    if not refs:
        return refs
    generated_indices = index_digests(connection)
    excluded = {'.git', '.agents', '.codex', '.claude', 'node_modules', '.next', '.venv', 'venv',
                '__pycache__', '.pytest_cache', 'dist', 'build'}
    def unreadable(error):
        name = Path(error.filename).relative_to(root).as_posix()
        for target in refs:
            refs[target].append({'kind': 'file_reference_unknown', 'path': name})
    for directory, subdirs, files in os.walk(root, followlinks=False, onerror=unreadable):
        subdirs[:] = [name for name in subdirs if name not in excluded
                      and (Path(directory) / name).resolve() == Path(directory) / name]
        relative = Path(directory).relative_to(root).as_posix()
        if relative == '.evolve-local':
            subdirs[:] = [name for name in subdirs if name in ('review', 'exports')]
            files = []
        for filename in files:
            path = Path(directory) / filename
            if not path.is_file() or path.is_symlink() or filename.endswith(('.pyc', '.pyo', '.tsbuildinfo')):
                continue
            name = path.relative_to(root).as_posix()
            remaining = {target: (target.encode(), posixpath.relpath(target, posixpath.dirname(name) or '.').encode())
                         for target in owned if target != name}
            if not remaining:
                continue
            try:
                automatic = owned.get(name)
                if automatic and current_digest(path) == automatic['content_digest']:
                    continue  # An unchanged runtime copy is immutable bookkeeping, not a new consumer.
                if name == INDEX and current_digest(path) in generated_indices:
                    continue
                overlap = max(len(value) for values in remaining.values() for value in values) - 1
                tail = b''
                with path.open('rb') as stream:
                    block = stream.read(65536)
                    if b'\x00' in block:
                        continue  # Database/binary contents are not local text references.
                    while block and remaining:
                        content = tail + block
                        for target, variants in list(remaining.items()):
                            if any(value in content for value in variants):
                                refs[target].append({'kind': 'project_text', 'path': name})
                                del remaining[target]
                        tail = content[-overlap:]
                        block = stream.read(65536)
            except OSError:
                for target in remaining:
                    refs[target].append({'kind': 'file_reference_unknown', 'path': name})
    return refs


def observe(connection, root, meta, *, active_run=None):
    owned = owners(connection, meta, active_run)
    file_refs = file_references(connection, root, owned)
    found = set(owned)
    folder = inside(root, '.evolve-local/review')
    if folder.is_symlink() or folder.resolve() != folder:
        return {'status': 'conflict', 'reason': 'review_directory_uses_link', 'copies': [], 'cleanup_candidates': []}
    for directory, subdirs, files in os.walk(folder, followlinks=False):
        for name in list(subdirs):
            path = Path(directory) / name
            if path.is_symlink() or path.resolve() != path:
                found.add(path.relative_to(root).as_posix())
                subdirs.remove(name)
        found.update((Path(directory) / name).relative_to(root).as_posix() for name in files)
    busy = bool(connection.execute("SELECT 1 FROM phase_runs WHERE status='started' AND id!=?", (active_run or '',)).fetchone()
                or connection.execute('SELECT 1 FROM resource_claims').fetchone())
    copies = []
    for name in sorted(found - {INDEX}):
        item = owned.get(name)
        reasons, refs = [], []
        try:
            actual = current_digest(local_path(root, name))
        except (EvolveError, OSError):
            actual = 'unreadable_or_linked'
        if item is None:
            reasons.append('unknown_ownership')
        else:
            if actual != item['content_digest']:
                reasons.append('missing' if actual is None else 'manual_change_or_link')
            if item['purpose'] != 'auxiliary_copy':
                reasons.append(item['purpose'])
            change = connection.execute('SELECT state FROM changes WHERE id=?', (item['change_id'],)).fetchone()
            if not change or change['state'] not in ('archived', 'cancelled'):
                reasons.append('work_not_closed')
            blob = connection.execute('SELECT content FROM blobs WHERE digest=?', (item['content_digest'],)).fetchone()
            if blob is None or digest(blob['content']) != item['content_digest']:
                reasons.append('source_not_reproducible')
            source, request, saved = sealed_result(connection, item['source'])
            if digest(canonical(saved) + b'\n') != item['content_digest']:
                reasons.append('source_not_reproducible')
            if source['status'] != 'completed' or not retained_source(connection, source, request):
                reasons.append('source_unavailable')
            refs = references(connection, root, name, item['owner_run_id']) + file_refs[name]
            if refs:
                reasons.append('referenced')
            if busy:
                reasons.append('unfinished_execution')
        copies.append({'path': name, 'classification': item['purpose'] if item else 'unknown',
                       'content_digest': actual, 'source': item['source'] if item else None,
                       'change_id': item['change_id'] if item else None,
                       'references': refs, 'retain_reasons': reasons, 'cleanup_eligible': not reasons})
    return {'status': 'observed', 'reference_coverage': 'saved_runs_tasks_registered_knowledge_and_project_text',
            'formal_receipts': {'location': 'evolve/history.db', 'cleanup_allowed': False,
                'verifications': [dict(row) for row in connection.execute('SELECT id,status,source_run_id FROM verifications')]},
            'candidates': [dict(row) for row in connection.execute('SELECT id,state,target_path FROM knowledge_proposals')],
            'copies': copies, 'cleanup_candidates': [item for item in copies if item['cleanup_eligible']]}


def query(root):
    from .reading import history_snapshot
    root = Path(root).resolve()
    with history_snapshot(root) as (connection, meta):
        return {'committed': False, 'outcome': 'observed', 'materials': observe(connection, root, meta)}


def index_prepare(store, run_id):
    report = observe(store.connection, store.root, store.meta, active_run=run_id)
    content = canonical(report) + b'\n'
    blob = store.blob(content)
    prior = index_digests(store.connection)
    try:
        actual = current_digest(local_path(store.root, INDEX))
    except (OSError, EvolveError):
        actual = 'unreadable_or_linked'
    prepared = {'path': INDEX, 'content_digest': blob, 'expected_digest': actual,
                'write_allowed': actual is None or actual in prior}
    store.event(run_id, 'review_index_prepared', prepared)
    return prepared, content


def index_install(root, prepared, content):
    if not prepared['write_allowed']:
        return 'manual_conflict'
    try:
        path = local_path(root, INDEX)
        if current_digest(path) != prepared['expected_digest']:
            return 'changed_since_prepared'
        durable_write(path, content)
        return 'written'
    except (OSError, EvolveError):
        return 'pending'


def export(store, request):
    data = request['input']
    kind = data['kind']
    ref = data.get('source')
    source, source_request, saved = sealed_result(store.connection, ref) if kind == 'review_copy' else (None, None, None)
    if source is not None and not retained_source(store.connection, source, source_request):
        raise EvolveError('REVIEW_SOURCE', 'Review source belongs to another project')
    change_id = (saved.get('change_id') or source_request['input'].get('change_id')) if source is not None else None
    if source is not None and not store.one('SELECT 1 FROM changes WHERE id=?', (change_id,)):
        raise EvolveError('REVIEW_SOURCE', 'A review copy must identify its actual work item')
    run_id, _ = store.start(request, action='maintain', method='export', owner='evolve-maintain')
    result = {'committed': True, 'outcome': 'review_index_recorded', 'business_commands_run': False}
    if source is not None:
        content = canonical(saved) + b'\n'
        name = '.evolve-local/review/' + change_id + '/results/' + run_id + '.json'
        purpose = ('failure_or_recovery_copy' if source['status'] != 'completed' or source['method'] == 'recover'
                   or saved.get('status') in ('failed', 'blocked') or saved.get('outcome') in ('blocked', 'checks_not_passed', 'partial')
                   else 'candidate_copy' if saved.get('proposal_id') or source['action'] in ('propose', 'update') else 'auxiliary_copy')
        with store.transaction():
            blob = store.blob(content)
            item = {'project_id': store.meta['project_id'], 'change_id': change_id, 'source': ref,
                    'path': name, 'content_digest': blob, 'purpose': purpose}
            store.link_source(run_id, source['id'], source['result_digest'], 'review_copy')
            store.event(run_id, 'review_copy_prepared', item)
        durable_write(local_path(store.root, name), content, new=True)
        result.update(outcome='review_copy_exported', change_id=change_id, output=name, content_digest=blob, source=ref, purpose=purpose)
    with store.transaction():
        prepared, content = index_prepare(store, run_id)
    status = index_install(store.root, prepared, content)
    return store.finish(run_id, {**result, 'index_status': status, 'index_digest': prepared['content_digest']})


def clean(root, payload):
    request = normalize(payload)
    require_effect(request, 'project_records')
    root = Path(root).resolve()
    with writer_lock(root):
        store = Store(root)
        try:
            previous = store.lookup(request, action='maintain', method='clean', owner='evolve-maintain')
            if previous is not None:
                return previous[1]
            data = request['input']
            stage = data.get('stage', 'plan')
            if stage not in ('plan', 'apply'):
                raise EvolveError('INPUT', 'Review cleanup stage must be plan or apply')
            selected = data.get('paths')
            if (not isinstance(selected, list) or not selected or any(not isinstance(name, str) for name in selected)
                    or len(selected) != len(set(selected))):
                raise EvolveError('INPUT', 'Cleanup requires exact distinct copy paths from maintain.materials')
            report = observe(store.connection, root, store.meta)
            eligible = {item['path']: item for item in report['cleanup_candidates']}
            if not set(selected).issubset(eligible):
                raise EvolveError('REVIEW_RETAIN', 'A selected copy is modified, referenced, unknown, unfinished or not reproducible')
            entries = [eligible[name] for name in sorted(selected)]
            if stage == 'apply':
                source, original, plan = sealed_result(store.connection, data.get('plan_source'))
                if (source['action'] != 'maintain' or source['method'] != 'clean' or source['status'] != 'completed'
                        or original['input'].get('stage', 'plan') != 'plan' or not retained_source(store.connection, source, original)
                        or source['workspace_epoch'] != store.meta['workspace_epoch'] or plan.get('entries') != entries):
                    raise EvolveError('REVIEW_PLAN_CHANGED', 'Cleanup must match its exact current, sealed plan and epoch')
            run_id, _ = store.start(request, action='maintain', method='clean', owner='evolve-maintain')
            if stage == 'plan':
                return store.finish(run_id, {'committed': True, 'outcome': 'review_cleanup_planned', 'entries': entries,
                    'business_commands_run': False, 'business_files_changed': False})
            with store.transaction():
                store.link_source(run_id, source['id'], source['result_digest'], 'review_cleanup_plan')
                store.event(run_id, 'review_cleanup_prepared', {'entries': entries})
            removed, failure = [], None
            for item in entries:
                try:
                    path = local_path(root, item['path'])
                    if current_digest(path) != item['content_digest']:
                        raise EvolveError('REVIEW_CHANGED', 'Copy changed after cleanup preparation')
                    path.unlink()
                    removed.append(item['path'])
                    with store.transaction():
                        store.event(run_id, 'review_copy_removed', {'path': item['path'], 'content_digest': item['content_digest']})
                except (OSError, EvolveError) as error:
                    failure = str(error)
                    break
            with store.transaction():
                prepared, content = index_prepare(store, run_id)
            status = index_install(root, prepared, content)
            return store.finish(run_id, {'committed': True, 'outcome': 'review_cleanup_partial' if failure else 'review_cleanup_completed',
                'removed': removed, 'remaining': [item['path'] for item in entries if item['path'] not in removed],
                'error': failure, 'index_status': status, 'index_digest': prepared['content_digest'], 'business_commands_run': False, 'business_files_changed': False})
        finally:
            store.close()


def interrupted(store, run_id):
    result = {'outcome': 'review_materials_interrupted', 'business_commands_run': False, 'cleanup_replayed': False}
    rows = store.connection.execute("SELECT kind,payload_json FROM events WHERE run_id=? AND kind IN "
        "('review_copy_prepared','review_cleanup_prepared')", (run_id,)).fetchall()
    observations = []
    for row in rows:
        value = json.loads(row['payload_json'])
        for item in value.get('entries', [value]):
            try:
                actual = current_digest(local_path(store.root, item['path']))
            except (OSError, EvolveError):
                actual = 'unknown'
            observations.append({'path': item['path'], 'expected_digest': item['content_digest'], 'actual_digest': actual,
                                 'status': 'absent' if actual is None else 'present' if actual == item['content_digest'] else 'changed_or_unknown'})
    return {**result, 'observations': observations, 'remaining': ['Inspect actual copies; prepare a new exact cleanup plan for remaining eligible copies.']}
