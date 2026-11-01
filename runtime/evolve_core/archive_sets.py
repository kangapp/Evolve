"""Bounded, blob-backed archive sets; observed user bytes are never authority."""
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

from . import VERSION, PROTOCOL_VERSION, SCHEMA_VERSION
from .errors import EvolveError
from .package import canonical, digest
from .store import now, schema_compatible
from .workspace import current_digest, durable_write, inside

FORMAT = 'evolve-archive-v1'
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_SET_BYTES = 256 * 1024 * 1024
RESERVE_BYTES = 8 * 1024 * 1024


def managed_path(root, name, kind):
    if Path(root).is_symlink():
        raise EvolveError('ARCHIVE_PATH', 'Managed collection roots cannot be linked', exit_code=4)
    root = Path(root).resolve()
    path = inside(root, name)
    relative = path.relative_to(root)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise EvolveError('ARCHIVE_PATH', 'Managed archive paths cannot traverse links', exit_code=4)
    if kind == 'config':
        valid = name == 'evolve/config.toml'
    elif kind == 'database':
        valid = name == 'evolve/history.db'
    else:
        valid = (kind == 'knowledge' and path.suffix == '.md'
                 and relative.parts[0] not in {'.git', '.agents', '.codex', '.claude', '.evolve-local'})
    if not valid or path.is_symlink():
        raise EvolveError('ARCHIVE_PATH', 'Archive contains an unsupported managed target: ' + str(name), exit_code=4)
    return path


def database_copy(connection, target):
    destination = sqlite3.connect(target)
    try:
        connection.backup(destination)
    finally:
        destination.close()


def inspect_database(path):
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or connection.execute('PRAGMA foreign_key_check').fetchone():
            raise EvolveError('ARCHIVE_DATABASE', 'Archive database integrity or references are invalid', exit_code=4)
        if not schema_compatible(connection):
            raise EvolveError('ARCHIVE_DATABASE', 'Archive database schema is incomplete', exit_code=4)
        meta = dict(connection.execute('SELECT key,value FROM project_meta'))
        if int(meta['schema_version']) != SCHEMA_VERSION or int(meta['protocol_version']) not in {14, 15, 16, PROTOCOL_VERSION}:
            raise EvolveError('SCHEMA_VERSION', 'Archive requires an explicitly supported schema', exit_code=4)
        for row in connection.execute('SELECT digest,content FROM blobs'):
            if digest(row['content']) != row['digest']:
                raise EvolveError('ARCHIVE_DATABASE', 'Archive contains a damaged immutable blob', exit_code=4)
        if connection.execute('SELECT a.id FROM artifacts a LEFT JOIN artifact_versions v '
                'ON v.id=a.current_version AND v.artifact_id=a.id WHERE v.id IS NULL LIMIT 1').fetchone():
            raise EvolveError('ARCHIVE_DATABASE', 'An artifact current version is missing or belongs to another artifact', exit_code=4)
        registered = [dict(row) for row in connection.execute(
            "SELECT a.path,a.kind,v.blob_digest,b.content FROM artifacts a "
            "JOIN artifact_versions v ON v.id=a.current_version JOIN blobs b ON b.digest=v.blob_digest "
            "WHERE a.kind IN ('config','knowledge') AND a.path IS NOT NULL ORDER BY a.path")]
        if not any(r['path'] == 'evolve/config.toml' and r['kind'] == 'config' for r in registered):
            raise EvolveError('ARCHIVE_DATABASE', 'Registered configuration is missing from the archive collection', exit_code=4)
        pending = [dict(row) for row in connection.execute(
            "SELECT id,action,method,execution_instance FROM phase_runs WHERE status='started'")]
        return meta, registered, pending
    except (sqlite3.Error, KeyError, ValueError, TypeError) as error:
        raise EvolveError('ARCHIVE_DATABASE', 'Cannot validate the archive database: ' + str(error), exit_code=4)
    finally:
        connection.close()


def validate_archive(bundle, expected_digest):
    bundle = Path(bundle).absolute()
    if bundle.is_symlink() or not bundle.is_dir():
        raise EvolveError('ARCHIVE_PATH', 'Select an existing regular archive directory', exit_code=4)
    try:
        manifest_path = inside(bundle, 'manifest.json')
        if manifest_path.is_symlink():
            raise EvolveError('ARCHIVE_PATH', 'Archive manifest cannot be linked', exit_code=4)
        encoded = manifest_path.read_bytes()
        manifest = json.loads(encoded)
        if digest(encoded) != expected_digest or manifest.get('format') != FORMAT or manifest.get('complete') is not True:
            raise EvolveError('ARCHIVE_INVALID', 'Archive manifest differs from the selected complete set', exit_code=4)
        if not isinstance(manifest.get('files'), list) or not manifest['files']:
            raise EvolveError('ARCHIVE_INVALID', 'Archive has no explicit authority collection', exit_code=4)
        seen, total = set(), len(encoded)
        for item in manifest['files']:
            managed_path(bundle / 'authority', item['path'], item['kind'])
            name = 'authority/' + item['path']
            if name in seen or item.get('payload') != name:
                raise EvolveError('ARCHIVE_PATH', 'Archive targets must be unique and exactly bound', exit_code=4)
            seen.add(name)
            path = inside(bundle, name)
            if path.is_symlink() or not path.is_file() or path.stat().st_size != item['bytes'] or current_digest(path) != item['digest']:
                raise EvolveError('ARCHIVE_INVALID', 'Archive authority bytes are missing or changed: ' + name, exit_code=4)
            if item['kind'] != 'database' and item['bytes'] > MAX_FILE_BYTES:
                raise EvolveError('ARCHIVE_CAPACITY', 'Authority file exceeds the archive budget', exit_code=4)
            total += item['bytes']
        for observation in manifest.get('observations', []):
            managed_path(bundle / 'authority', observation['path'], observation['kind'])
            if observation.get('protected_copy'):
                name = observation['protected_copy']
                if name != 'observed/' + observation['actual_digest']:
                    raise EvolveError('ARCHIVE_PATH', 'Observed copies must remain separate from authority', exit_code=4)
                shared = name in seen
                seen.add(name)
                path = inside(bundle, name)
                if (bundle / 'observed').is_symlink() or path.is_symlink():
                    raise EvolveError('ARCHIVE_PATH', 'Observed protection copies cannot be linked', exit_code=4)
                if current_digest(path) != observation['actual_digest']:
                    raise EvolveError('ARCHIVE_INVALID', 'Observed protection copy changed', exit_code=4)
                if path.stat().st_size > MAX_FILE_BYTES:
                    raise EvolveError('ARCHIVE_CAPACITY', 'Observed file exceeds the archive budget', exit_code=4)
                if not shared:
                    total += path.stat().st_size
        if total > MAX_SET_BYTES:
            raise EvolveError('ARCHIVE_CAPACITY', 'Archive exceeds the supported collection budget', exit_code=4)
        database = inside(bundle, 'authority/evolve/history.db')
        meta, registered, pending = inspect_database(database)
        for key in ('project_id', 'workspace_epoch', 'checkpoint', 'schema_version', 'protocol_version'):
            if str(manifest.get(key)) != meta[key]:
                raise EvolveError('ARCHIVE_INVALID', 'Manifest and database identity or cutoff differ', exit_code=4)
        authority = {r['path']: r for r in manifest['files']}
        if set(authority) != {'evolve/history.db'} | {r['path'] for r in registered}:
            raise EvolveError('ARCHIVE_INVALID', 'Manifest is not the exact registered snapshot collection', exit_code=4)
        for row in registered:
            if authority[row['path']]['kind'] != row['kind'] or authority[row['path']]['digest'] != row['blob_digest']:
                raise EvolveError('ARCHIVE_INVALID', 'Authority file is not its recorded immutable version', exit_code=4)
        if manifest.get('pending_runs') != pending:
            raise EvolveError('ARCHIVE_INVALID', 'Pending execution list differs from the saved cutoff', exit_code=4)
        return manifest
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        raise EvolveError('ARCHIVE_INVALID', 'Cannot validate the exact selected archive: ' + str(error), exit_code=4)


def require_archive_quiet(store):
    root = store.root
    if store.one("SELECT id FROM operations WHERE state IN ('prepared','needs_recovery') AND effect_kind!='external_write' LIMIT 1"):
        raise EvolveError('NEEDS_RECOVERY', 'Unresolved file effects prevent a complete archive', exit_code=4)
    operations = inside(root, '.evolve-local/control/operations')
    if operations.exists() and any(json.loads(p.read_text()).get('state') != 'committed' for p in operations.glob('*.json')):
        raise EvolveError('NEEDS_RECOVERY', 'Unresolved file journals prevent a complete archive', exit_code=4)


def collect_archive(store, destination, request_id):
    """Caller holds the local writer lock, with no SQLite transaction open."""
    root, destination = store.root, Path(destination)
    require_archive_quiet(store)
    if destination.exists() or destination.is_symlink():
        raise EvolveError('ARCHIVE_EXISTS', 'A completed or incomplete archive is never overwritten', exit_code=3)
    if store.connection.in_transaction:
        raise EvolveError('ARCHIVE_BUSY', 'Finish the current SQLite transaction before collecting a snapshot', exit_code=3)
    rows = store.connection.execute(
        "SELECT a.path,a.kind,b.content,b.digest FROM artifacts a "
        "JOIN artifact_versions v ON v.id=a.current_version JOIN blobs b ON b.digest=v.blob_digest "
        "WHERE a.kind IN ('config','knowledge') AND a.path IS NOT NULL ORDER BY a.path").fetchall()
    physical = {}
    for row in rows:
        path = managed_path(root, row['path'], row['kind'])
        if len(row['content']) > MAX_FILE_BYTES or (path.is_file() and path.stat().st_size > MAX_FILE_BYTES):
            raise EvolveError('ARCHIVE_CAPACITY', 'Managed file exceeds the archive budget; nothing truncated', exit_code=4)
        physical[row['path']] = path.read_bytes() if path.is_file() else None
    database = inside(root, 'evolve/history.db')
    database_files = [database, database.with_name(database.name + '-wal')]
    if sum(p.stat().st_size for p in database_files if p.is_file()) > MAX_SET_BYTES:
        raise EvolveError('ARCHIVE_CAPACITY', 'History exceeds the archive collection budget', exit_code=4)
    original_database = {p: current_digest(p) for p in database_files}
    estimate = sum(p.stat().st_size for p in database_files if p.is_file()) + sum(len(r['content']) for r in rows) + sum(len(v) for v in physical.values() if v is not None)
    if (any(len(r['content']) > MAX_FILE_BYTES for r in rows)
            or any(len(v) > MAX_FILE_BYTES for v in physical.values() if v is not None) or estimate > MAX_SET_BYTES):
        raise EvolveError('ARCHIVE_CAPACITY', 'Collection exceeds the supported archive/file budget; nothing truncated', exit_code=4)
    existing_parent = destination.parent
    while not existing_parent.exists():
        existing_parent = existing_parent.parent
    if shutil.disk_usage(existing_parent).free < estimate + RESERVE_BYTES:
        raise EvolveError('ARCHIVE_SPACE', 'Insufficient space for a complete archive and reserve', exit_code=4)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.incomplete-', dir=destination.parent))
    try:
        target = staging / 'authority/evolve/history.db'
        target.parent.mkdir(parents=True)
        database_copy(store.connection, target)
        meta, registered, pending = inspect_database(target)
        if any(meta[k] != store.meta[k] for k in ('project_id', 'workspace_epoch', 'checkpoint')):
            raise EvolveError('ARCHIVE_CHANGED', 'Archive checkpoint changed during SQLite collection', exit_code=3)
        files = [{'path': 'evolve/history.db', 'payload': 'authority/evolve/history.db', 'kind': 'database',
                  'bytes': target.stat().st_size, 'digest': digest(target.read_bytes())}]
        observations = []
        for row in registered:
            path = managed_path(root, row['path'], row['kind'])
            if row['path'] not in physical:
                raise EvolveError('ARCHIVE_CHANGED', 'Managed collection changed during snapshot', exit_code=3)
            actual = physical[row['path']]
            if (path.read_bytes() if path.is_file() else None) != actual:
                raise EvolveError('ARCHIVE_CHANGED', 'Managed bytes changed after the archive cutoff', exit_code=3)
            payload = 'authority/' + row['path']
            durable_write(inside(staging, payload), row['content'], new=True)
            files.append({'path': row['path'], 'payload': payload, 'kind': row['kind'],
                          'bytes': len(row['content']), 'digest': row['blob_digest']})
            actual_digest = digest(actual) if actual is not None else None
            if actual_digest != row['blob_digest']:
                protected = 'observed/' + actual_digest if actual is not None else None
                if protected and not (staging / protected).exists():
                    durable_write(staging / protected, actual, new=True)
                observations.append({'path': row['path'], 'kind': row['kind'], 'registered_digest': row['blob_digest'],
                                     'actual_digest': actual_digest, 'protected_copy': protected, 'source': 'external_or_unknown'})
        if {p: current_digest(p) for p in database_files} != original_database:
            raise EvolveError('ARCHIVE_CHANGED', 'Source history changed while collecting the archive', exit_code=3)
        for name, actual in physical.items():
            path = inside(root, name)
            if (path.read_bytes() if path.is_file() else None) != actual:
                raise EvolveError('ARCHIVE_CHANGED', 'Managed bytes changed before archive finalization', exit_code=3)
        manifest = {'format': FORMAT, 'complete': True, 'package_version': VERSION,
            'schema_version': int(meta['schema_version']), 'protocol_version': int(meta['protocol_version']),
            'project_id': meta['project_id'], 'workspace_epoch': meta['workspace_epoch'], 'checkpoint': meta['checkpoint'],
            'requested_by': request_id, 'observed_at': now(), 'files': files, 'observations': observations,
            'pending_runs': pending, 'business_data_included': False, 'attachments': 'All actual immutable blobs are included in the SQLite snapshot; unstored external sources remain references only.',
            'capacity': {'estimated_bytes': estimate, 'max_file_bytes': MAX_FILE_BYTES, 'max_set_bytes': MAX_SET_BYTES}}
        encoded = canonical(manifest)
        durable_write(staging / 'manifest.json', encoded, new=True)
        validate_archive(staging, digest(encoded))
        staging.rename(destination)
        return {'path': str(destination), 'manifest_digest': digest(encoded), 'project_id': meta['project_id'],
                'workspace_epoch': meta['workspace_epoch'], 'checkpoint': meta['checkpoint'], 'files': len(files),
                'observations': len(observations), 'business_data_included': False}
    except BaseException:
        # Partial copies are retained for inspection; they are never labelled complete.
        manifest = staging / 'manifest.json'
        if manifest.exists():
            manifest.rename(staging / 'incomplete-manifest.json')
        raise
