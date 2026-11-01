"""Finite Python project material and read-only identity probes for SQLite targets."""
import json
from pathlib import Path
import sqlite3
import sys
import time

from .errors import EvolveError
from .package import canonical, digest
from .privacy import ensure_recordable
from .workspace import current_digest, durable_write, inside

MAX_MATERIAL_BYTES = 8 * 1024 * 1024
MAX_OBSERVATION_BYTES = 65536


def regular_path(root, name):
    root = Path(root).resolve()
    path = inside(root, name)
    cursor = root
    for part in path.relative_to(root).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise EvolveError('EXTERNAL_PATH', 'External material and target paths cannot traverse links', exit_code=3)
    if not path.is_file():
        raise EvolveError('EXTERNAL_PATH', 'Expected an existing regular project file: ' + name, exit_code=3)
    return path


def read_query(path, query, parameters=()):
    """The real target observer opens SQLite read-only and has a bounded deadline."""
    if not isinstance(query, str) or not query.strip() or not isinstance(parameters, (list, tuple)):
        raise EvolveError('EXTERNAL_QUERY', 'Read-only observation needs exact SQL and parameter values')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=3)
    deadline = time.monotonic() + 3
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_OBSERVATION_BYTES)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, MAX_OBSERVATION_BYTES)
        connection.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        connection.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        cursor = connection.execute(query, parameters)
        if cursor.description is None:
            raise EvolveError('EXTERNAL_QUERY', 'Observation must return rows, never mutate the target')
        rows = cursor.fetchmany(1001)
        result = {'columns': [c[0] for c in cursor.description], 'rows': [list(r) for r in rows]}
        encoded = canonical(result)
        if len(rows) > 1000 or len(encoded) > MAX_OBSERVATION_BYTES:
            raise EvolveError('EXTERNAL_QUERY_LIMIT', 'Target observation exceeds its bounded rows/bytes; nothing truncated')
        ensure_recordable(encoded)
        return result
    except sqlite3.Error as error:
        raise EvolveError('EXTERNAL_OBSERVATION', 'Read-only target observation failed: ' + str(error), exit_code=3)
    finally:
        connection.close()


def target_snapshot(root, target):
    if not isinstance(target, dict) or target.get('kind') != 'sqlite':
        raise EvolveError('EXTERNAL_UNSUPPORTED', 'Only an explicitly identified local SQLite project mechanism is supported')
    if (target.get('environment') not in ('isolated', 'test', 'production')
            or not isinstance(target.get('scope'), str) or not target['scope'].strip()
            or not isinstance(target.get('objects'), list) or not target['objects']
            or any(not isinstance(x, str) or not x for x in target['objects'])
            or len(set(target['objects'])) != len(target['objects'])):
        raise EvolveError('EXTERNAL_TARGET', 'Specify the actual environment, unique objects and precise data scope')
    path = regular_path(root, target.get('path'))
    if path.relative_to(Path(root).resolve()).parts[0] in {'evolve', '.evolve-local', '.git', '.agents', '.codex', '.claude'}:
        raise EvolveError('EXTERNAL_TARGET', 'Archive, installation and host control files cannot be business targets')
    identity = target.get('identity')
    if not isinstance(identity, dict) or not isinstance(identity.get('expected'), str) or not identity['expected']:
        raise EvolveError('EXTERNAL_TARGET', 'A stable non-secret provider identity and read-only identity query are required')
    provider = read_query(path, identity.get('sql'), identity.get('parameters', []))
    if provider['rows'] != [[identity['expected']]]:
        raise EvolveError('EXTERNAL_TARGET_CHANGED', 'Resolved provider identity differs from the selected target', exit_code=3)
    schema = read_query(path, "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")
    available = {r[1] for r in schema['rows'] if r[0] in ('table', 'view')}
    if not set(target['objects']).issubset(available):
        raise EvolveError('EXTERNAL_TARGET', 'An approved data object is absent from the actual target')
    stat = path.stat()
    value = {'kind': 'sqlite', 'path': target['path'], 'resolved_path': str(path),
             'environment': target['environment'], 'objects': sorted(target['objects']), 'scope': target['scope'],
             'provider_identity': identity['expected'], 'device': stat.st_dev, 'inode': stat.st_ino,
             'schema_digest': digest(canonical(schema))}
    return {**value, 'digest': digest(canonical(value))}


def interpreter_identity():
    path = Path(sys.executable).resolve()
    value = {'path': str(path), 'version': sys.version, 'digest': current_digest(path)}
    return value


def collect_material(root, execution, target_path):
    if not isinstance(execution, dict):
        raise EvolveError('EXTERNAL_MATERIAL', 'Provide the complete finite project execution material')
    if set(execution) - {'files', 'argv', 'cwd', 'closure', 'timeout'}:
        raise EvolveError('EXTERNAL_MATERIAL', 'This finite mechanism accepts files/argv/cwd/closure/timeout only')
    if type(execution.get('timeout', 60)) is not int or not 1 <= execution.get('timeout', 60) <= 3600:
        raise EvolveError('EXTERNAL_MATERIAL', 'Bind an integer sender timeout between 1 and 3600 seconds')
    closure = execution.get('closure')
    if (not isinstance(closure, dict) or closure.get('complete') is not True
            or closure.get('no_detached_or_delayed_work') is not True
            or any(not isinstance(closure.get(k), str) or not closure[k].strip() for k in ('observer', 'basis'))
            or not isinstance(closure.get('limitations'), list) or not closure['limitations']
            or any(not isinstance(x, str) or not x.strip() for x in closure['limitations'])):
        raise EvolveError('EXTERNAL_CLOSURE', 'Actually review all indirect inputs and target resolution; incomplete/dynamic or detached work cannot be dispatched')
    names, argv = execution.get('files'), execution.get('argv')
    if (not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names)
            or len(set(names)) != len(names) or not isinstance(argv, list) or not argv
            or any(not isinstance(a, str) or '\x00' in a for a in argv)
            or argv[0] not in names or Path(argv[0]).suffix != '.py'
            or argv.count('{target}') != 1 or argv.count('{operation_id}') != 1):
        raise EvolveError('EXTERNAL_MATERIAL', 'Use a declared Python entry and exact target/operation-id argv placeholders; no shell command')
    root = Path(root).resolve()
    cwd = execution.get('cwd', '.')
    cwd_path = inside(root, cwd)
    if not cwd_path.is_dir() or cwd_path.is_symlink():
        raise EvolveError('EXTERNAL_MATERIAL', 'Execution cwd must be an existing nonlinked project directory')
    files, total = [], 0
    for name in sorted(names):
        path = regular_path(root, name)
        if (path.relative_to(root).parts[0] in {'evolve', '.evolve-local', '.git', '.agents', '.codex', '.claude'}
                or path == target_path):
            raise EvolveError('EXTERNAL_MATERIAL', 'Business target data and tool/host records cannot be frozen as execution material')
        total += path.stat().st_size
        if total > MAX_MATERIAL_BYTES:
            raise EvolveError('EXTERNAL_MATERIAL_LIMIT', 'Finite execution material exceeds 8 MiB; nothing truncated')
        before = current_digest(path)
        content = path.read_bytes().decode('utf-8')
        ensure_recordable(content)
        if digest(content.encode()) != before or current_digest(path) != before:
            raise EvolveError('EXTERNAL_MATERIAL_CHANGED', 'Execution material changed during collection', exit_code=3)
        files.append({'path': name, 'content': content, 'digest': before})
    for row in files:
        if current_digest(regular_path(root, row['path'])) != row['digest']:
            raise EvolveError('EXTERNAL_MATERIAL_CHANGED', 'Execution material changed before collection completed', exit_code=3)
    return {'files': files, 'argv': argv, 'cwd': cwd, 'closure': closure, 'interpreter': interpreter_identity(),
            'timeout': execution.get('timeout', 60), 'python_flags': ['-S', '-B'],
            'environment_policy': 'Only PATH/locale/TMPDIR plus no site-packages, PYTHONPATH or implicit credential inheritance; this SQLite mechanism needs no credential references.'}


def freeze_material(folder, candidate):
    """Only exact approved text is installed; actual dispatch never rereads live SQL/helpers."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    for row in candidate['execution']['files']:
        content = row['content'].encode()
        if digest(content) != row['digest']:
            raise EvolveError('EXTERNAL_MATERIAL', 'Saved immutable candidate text and digest disagree')
        durable_write(inside(folder, row['path']), content, new=True)
    inside(folder, candidate['execution']['cwd']).mkdir(parents=True, exist_ok=True)
    validate_frozen(folder, candidate)


def validate_frozen(folder, candidate):
    folder = Path(folder)
    names = {row['path'] for row in candidate['execution']['files']}
    observed = set()
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise EvolveError('EXTERNAL_MATERIAL_CHANGED', 'Frozen execution material cannot contain links', exit_code=3)
        if path.is_file():
            observed.add(path.relative_to(folder).as_posix())
    if observed != names:
        raise EvolveError('EXTERNAL_MATERIAL_CHANGED', 'Frozen execution collection gained or lost a file', exit_code=3)
    for row in candidate['execution']['files']:
        if current_digest(regular_path(folder, row['path'])) != row['digest']:
            raise EvolveError('EXTERNAL_MATERIAL_CHANGED', 'Frozen entry/indirect material changed', exit_code=3)


def require_current(root, candidate):
    actual = target_snapshot(root, candidate['target'])
    if actual != candidate['target_snapshot']:
        raise EvolveError('EXTERNAL_TARGET_CHANGED', 'Resolved target identity/schema/environment differs from the approved candidate', exit_code=3)
    for row in candidate['execution']['files']:
        path = regular_path(root, row['path'])
        if current_digest(path) != row['digest']:
            raise EvolveError('EXTERNAL_MATERIAL_CHANGED', 'Entry/indirect SQL/helper/config differs from the approved candidate: ' + row['path'], exit_code=3)
    if interpreter_identity() != candidate['execution']['interpreter']:
        raise EvolveError('EXTERNAL_MATERIAL_CHANGED', 'Approved execution interpreter changed', exit_code=3)
    return actual
