"""Local recovery fences and protective indexes; none is knowledge authority."""
import json
from pathlib import Path
import shutil
import socket
import subprocess

from .errors import EvolveError
from .package import canonical, digest
from .workspace import current_digest, durable_write, inside, process_alive


def require_admission(root, token=None):
    path = inside(root, '.evolve-local/control/maintenance.json')
    if path.exists():
        value = json.loads(path.read_text())
        if value.get('state') != 'completed' and value.get('request_id') != token:
            raise EvolveError('MAINTENANCE_ACTIVE', 'A persistent maintenance barrier requires its original request to resume', exit_code=4)


def managed_index(connection, meta):
    return {**{k: meta[k] for k in ('project_id', 'workspace_epoch', 'checkpoint')},
            'purpose': 'protection-only-not-content-authority', 'protocol_version': meta['protocol_version'],
            'executions': [dict(r) for r in connection.execute(
                "SELECT id,execution_instance FROM phase_runs WHERE status='started'")],
            'files': [dict(r) for r in connection.execute(
                "SELECT a.path,a.kind,v.blob_digest AS digest FROM artifacts a "
                "JOIN artifact_versions v ON v.id=a.current_version "
                "WHERE a.kind IN ('config','knowledge') AND a.path IS NOT NULL ORDER BY a.path")]}


def save_guard(root, connection, meta):
    index = canonical(managed_index(connection, meta))
    durable_write(inside(root, '.evolve-local/control/managed.json'), index)
    durable_write(inside(root, '.evolve-local/control/guard.json'), canonical({
        **{k: meta[k] for k in ('project_id', 'workspace_epoch', 'checkpoint')},
        'managed_index_digest': digest(index)}))


def protected_identity(root):
    """Corrupt history needs matching last-committed guard and protective collection."""
    guard_path = inside(root, '.evolve-local/control/guard.json')
    index_path = inside(root, '.evolve-local/control/managed.json')
    if not guard_path.is_file() or not index_path.is_file():
        raise EvolveError('PROTECTION_UNKNOWN', 'A matching local guard and managed-file index are required', exit_code=4)
    guard, index = json.loads(guard_path.read_text()), json.loads(index_path.read_text())
    if (guard.get('managed_index_digest') != current_digest(index_path)
            or any(guard.get(k) != index.get(k) for k in ('project_id', 'workspace_epoch', 'checkpoint'))):
        raise EvolveError('PROTECTION_UNKNOWN', 'Guard and managed-file protection index disagree; inspect healthy history before restore', exit_code=4)
    from .archive_sets import managed_path
    paths = set()
    for item in index['files']:
        managed_path(root, item['path'], item['kind'])
        if item['path'] in paths:
            raise EvolveError('PROTECTION_UNKNOWN', 'Duplicate managed-file protection target', exit_code=4)
        paths.add(item['path'])
    return guard, index


def record_check(root, meta, kind, details, recorded_at):
    """Intent is durable before launch, independent of a subsequently damaged DB."""
    path = inside(root, '.evolve-local/control/checks.json')
    value = json.loads(path.read_text())
    if any(value.get(k) != meta[k] for k in ('project_id', 'workspace_epoch')):
        raise EvolveError('PROTECTION_UNKNOWN', 'Check protection belongs to another epoch', exit_code=4)
    attempts = value['attempts']
    key = details['execution_id']
    if kind == 'check_dispatch_prepared':
        attempts[key] = {**details, 'prepared_at': recorded_at}
    elif kind == 'check_process_started':
        if key not in attempts:
            raise EvolveError('PROTECTION_UNKNOWN', 'Check launch has no durable intent', exit_code=4)
        attempts[key].update(details)
    elif kind in ('check_process_finished', 'check_dispatch_aborted'):
        attempts.pop(key, None)
    durable_write(path, canonical(value))


def require_drained(root, pending_runs=(), observations=(), *, legacy=False, check_index=None, external_index=None, sender_observations=()):
    """No epoch switch while an old local sender, check, or SQLite handle remains."""
    for run in pending_runs:
        owner = json.loads(run['execution_instance'])
        if owner['host'] != socket.gethostname() or process_alive(owner['pid']):
            raise EvolveError('WRITER_ACTIVE', 'An old execution has not been observed to stop: ' + run['id'], exit_code=4)
    from .checks import group_alive, validate_stop_observations
    path = Path(check_index) if check_index is not None else inside(root, '.evolve-local/control/checks.json')
    if not path.is_file() and not legacy:
        raise EvolveError('PROTECTION_UNKNOWN', 'Check protection is missing; do not infer that old checks stopped', exit_code=4)
    unresolved = []
    if path.is_file():
        for attempt in json.loads(path.read_text())['attempts'].values():
            if 'pid' not in attempt:
                unresolved.append({**attempt, 'state': 'launch_unknown'})
            elif attempt['host'] != socket.gethostname():
                unresolved.append({**attempt, 'state': 'foreign_host'})
            elif group_alive(attempt['pid']):
                unresolved.append({**attempt, 'state': 'process_group_present'})
    validate_stop_observations(unresolved, list(observations))
    if external_index is not None:
        from .external_registry import require_senders_stopped
        require_senders_stopped(external_index, sender_observations)
    observer = shutil.which('lsof')
    if observer is None:
        raise EvolveError('DRAIN_UNSUPPORTED', 'This environment cannot inspect open SQLite handles for offline maintenance', exit_code=4)
    database = inside(root, 'evolve/history.db')
    names = [str(p) for p in (database, *(database.with_name(database.name + s) for s in ('-wal', '-shm', '-journal'))) if p.exists()]
    if names:
        result = subprocess.run([observer, '-t', '--', *names], capture_output=True, text=True, timeout=15)
        if result.stdout.strip():
            raise EvolveError('DATABASE_OPEN', 'Close all old SQLite handles before maintenance; observed PIDs: ' + result.stdout.strip().replace('\n', ','), exit_code=4)
        if result.returncode not in (0, 1) or result.stderr.strip():
            raise EvolveError('DRAIN_UNKNOWN', 'Could not establish that old SQLite handles are closed', exit_code=4)


def initial_execution_indexes(root, meta):
    for name, fields in (('checks', {'attempts': {}}), ('external', {'pending': [], 'coverage': 'local-protocol-' + meta['protocol_version']})):
        path = inside(root, '.evolve-local/control/' + name + '.json')
        if not path.exists():
            durable_write(path, canonical({**{k: meta[k] for k in ('project_id', 'workspace_epoch')}, **fields}), new=True)
