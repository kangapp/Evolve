"""Incremental records-only connection, journaled before the project database exists."""
import base64
import json
from pathlib import Path, PureWindowsPath
import tempfile

from .errors import EvolveError
from .package import ROOT, canonical, digest
from .requests import normalize, require_effect
from .store import Store, create_database, identifier, now
from .privacy import ensure_recordable
from .workspace import current_digest, durable_write, inside, request_staging_only, writer_lock


def validate_checks(checks):
    if not isinstance(checks, list):
        raise EvolveError('INPUT', 'checks must be a list')
    seen = set()
    for check in checks:
        if not isinstance(check, dict):
            raise EvolveError('INPUT', 'Each check must be an object')
        if set(check) - {'id', 'argv', 'cwd', 'timeout'}:
            raise EvolveError('CONFIG_UNSUPPORTED', 'Check fields are limited to id, argv, cwd and timeout')
        if not isinstance(check.get('id'), str) or not check['id'] or check['id'] in seen:
            raise EvolveError('INPUT', 'Check identities must be distinct nonempty strings')
        seen.add(check['id'])
        if not isinstance(check.get('argv'), list) or not check['argv'] or any(
                not isinstance(item, str) or '\x00' in item for item in check['argv']):
            raise EvolveError('INPUT', 'Checks use nonempty argv arrays, never shell strings')
        if type(check.get('timeout', 60)) is not int or not 1 <= check.get('timeout', 60) <= 3600:
            raise EvolveError('INPUT', 'Check timeout must be between 1 and 3600 seconds')
        cwd = check.get('cwd', '.')
        if not isinstance(cwd, str) or Path(cwd).is_absolute() or PureWindowsPath(cwd).drive or '..' in Path(cwd).parts or '\\' in cwd:
            raise EvolveError('INPUT', 'Check cwd must be project-relative')
    return checks


def configuration(project_id, name, checks):
    if not isinstance(name, str) or not name.strip():
        raise EvolveError('INPUT', 'Project name must be a nonempty string')
    content = (ROOT / 'assets/templates/config.toml').read_text()
    content = content.replace('"{{project_id}}"', json.dumps(project_id, ensure_ascii=False))
    content = content.replace('"{{project_name}}"', json.dumps(name, ensure_ascii=False))
    for check in checks:
        content += ('\n[[verification.checks]]\n' +
                    'id = ' + json.dumps(check['id'], ensure_ascii=False) + '\n' +
                    'argv = ' + json.dumps(check['argv'], ensure_ascii=False) + '\n' +
                    'cwd = ' + json.dumps(check.get('cwd', '.'), ensure_ascii=False) + '\n' +
                    'timeout = ' + str(check.get('timeout', 60)) + '\n')
    encoded = content.encode('utf-8')
    ensure_recordable(encoded)
    return encoded


def _finish_connection(root, journal):
    request = journal['request']
    config = inside(root, 'evolve/config.toml')
    database = inside(root, 'evolve/history.db')
    if database.exists():
        existing_store = Store(root)
        try:
            if existing_store.meta['project_id'] != journal['project_id'] or existing_store.meta['workspace_epoch'] != journal['workspace_epoch']:
                raise EvolveError('PROJECT_IDENTITY', 'Init journal belongs to another project or epoch')
            previous = existing_store.one('SELECT status,result_json FROM phase_runs WHERE id=?', (journal['run_id'],))
            if previous and previous['status'] != 'started':
                if journal['state'] != 'committed':
                    durable_write(inside(root, '.evolve-local/control/init.json'), canonical({**journal, 'state': 'committed'}))
                return json.loads(previous['result_json'])
        finally:
            existing_store.close()
    config_bytes = base64.b64decode(journal['config_b64'], validate=True)
    if digest(config_bytes) != journal['config_digest']:
        raise EvolveError('JOURNAL_INVALID', 'Init candidate does not match its digest', exit_code=4)
    if current_digest(config) not in (None, journal['config_digest']):
        raise EvolveError('NEEDS_RECOVERY', 'Existing configuration differs from init candidate', exit_code=4)
    if not config.exists():
        durable_write(config, config_bytes, new=True)
    if not database.exists():
        content = base64.b64decode(journal['database_b64'], validate=True)
        if digest(content) != journal['database_digest']:
            raise EvolveError('JOURNAL_INVALID', 'Init database candidate changed', exit_code=4)
        durable_write(database, content, new=True)
    # Once installed, the database can contain the init run. Its bytes no longer
    # match the initial candidate; verify identity and the original run instead.
    store = Store(root)
    try:
        if store.meta['project_id'] != journal['project_id'] or store.meta['workspace_epoch'] != journal['workspace_epoch']:
            raise EvolveError('PROJECT_IDENTITY', 'Existing database does not match init identity')
        request = {**request, 'project_id': journal['project_id'],
                   'expected_workspace_epoch': journal['workspace_epoch']}
        previous = store.one('SELECT * FROM phase_runs WHERE id=?', (journal['run_id'],))
        if previous and previous['status'] != 'started':
            result = json.loads(previous['result_json'])
        else:
            if previous is None:
                store.start(request, action='init', method='connect', owner='evolve-init', run_id=journal['run_id'])
            with store.transaction() as connection:
                existing = store.one('SELECT id FROM operations WHERE id=?', (journal['operation_id'],))
                if existing is None:
                    connection.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?)',
                                       (journal['operation_id'], journal['run_id'], 'project_records', 'committed',
                                        journal['request_digest'], '{}', '.evolve-local/control/init.json'))
                    blob = store.blob(config_bytes)
                    artifact, version = identifier(), identifier()
                    connection.execute('INSERT INTO artifacts VALUES (?,?,?,?)',
                                       (artifact, 'evolve/config.toml', 'config', version))
                    connection.execute('INSERT INTO artifact_versions VALUES (?,?,?,?,?,?)',
                                       (version, artifact, blob, journal['run_id'], 'evolve-init', now()))
                    store.event(journal['run_id'], 'project_connected', {'project_id': journal['project_id']})
            result = store.finish(journal['run_id'], {'committed': True, 'outcome': 'connected',
                                  'project_id': journal['project_id'], 'workspace_epoch': journal['workspace_epoch'],
                                  'operation_id': journal['operation_id'], 'formal_baseline': 'not_proposed'})
        durable_write(inside(root, '.evolve-local/control/init.json'), canonical({**journal, 'state': 'committed'}))
        return result
    finally:
        store.close()


def connect(root, payload, *, recover=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise EvolveError('PROJECT_ROOT', 'Project root must exist')
    request = normalize(payload)
    require_effect(request, 'project_records')
    checks = validate_checks(request['input'].get('checks', []))
    name = request['input'].get('name', root.name)
    # Validate all candidate content before creating any record facilities.
    configuration('preflight-only', name, checks)
    journal_path = inside(root, '.evolve-local/control/init.json')
    if journal_path.exists():
        journal = json.loads(journal_path.read_text())
        if journal['request']['request_id'] == request['request_id']:
            request.setdefault('project_id', journal['project_id'])
            request.setdefault('expected_workspace_epoch', journal['workspace_epoch'])
            request_digest = digest(canonical(request))
            if journal['request_digest'] != request_digest:
                raise EvolveError('REQUEST_CONFLICT', 'Init retry changed the original input', exit_code=3)
            with writer_lock(root, recover_dead=recover):
                return _finish_connection(root, journal)
        if journal['state'] != 'committed':
            raise EvolveError('NEEDS_RECOVERY', 'Existing initialization must be reconciled before new work', exit_code=4)
    if inside(root, 'evolve/history.db').is_file() and inside(root, 'evolve/config.toml').is_file():
        from .configure import reconnect
        return reconnect(root, request)
    if (root / 'evolve').exists() or ((root / '.evolve-local').exists() and not request_staging_only(root)):
        raise EvolveError('PROJECT_COLLISION', 'Existing records need incremental inspection; no replacement performed')
    if request.get('project_id') or request.get('expected_workspace_epoch'):
        raise EvolveError('PROJECT_IDENTITY', 'A new project identity must be generated by initialization')
    with writer_lock(root):
        project_id, epoch = identifier(), identifier()
        request['project_id'] = project_id
        request['expected_workspace_epoch'] = epoch
        request_digest = digest(canonical(request))
        with tempfile.TemporaryDirectory(prefix='evolve-init-candidate-') as directory:
            candidate = Path(directory) / 'history.db'
            create_database(candidate, project_id, epoch)
            database_bytes = candidate.read_bytes()
        content = configuration(project_id, name, checks)
        journal = {'state': 'prepared', 'project_id': project_id, 'workspace_epoch': epoch,
                   'run_id': identifier(), 'operation_id': identifier(), 'request': request,
                   'request_digest': request_digest, 'config_b64': base64.b64encode(content).decode(),
                   'config_digest': digest(content), 'database_b64': base64.b64encode(database_bytes).decode(),
                   'database_digest': digest(database_bytes)}
        durable_write(journal_path, canonical(journal), new=True)
        return _finish_connection(root, journal)
