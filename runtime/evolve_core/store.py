"""SQLite facts for the small-change workflow; no model or business execution."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import sqlite3
import socket
import uuid

from . import VERSION, PROTOCOL_VERSION, SCHEMA_VERSION
from .errors import EvolveError
from .package import canonical, digest
from .privacy import ensure_recordable
from .workspace import durable_write, inside

DDL = '''
CREATE TABLE project_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE checkpoints (id TEXT PRIMARY KEY, parent_id TEXT REFERENCES checkpoints(id));
CREATE TABLE counters (prefix TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE blobs (digest TEXT PRIMARY KEY, content BLOB NOT NULL);
CREATE TABLE changes (
 id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, title TEXT NOT NULL, kind TEXT NOT NULL, complexity TEXT NOT NULL,
 state TEXT NOT NULL, current_revision TEXT, row_version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE plan_revisions (
 id TEXT PRIMARY KEY, change_id TEXT NOT NULL REFERENCES changes(id), ordinal INTEGER NOT NULL,
 plan_digest TEXT NOT NULL REFERENCES blobs(digest), definition_digest TEXT NOT NULL,
 scope_json TEXT NOT NULL, acceptance_json TEXT NOT NULL, checks_json TEXT NOT NULL,
 presented_at TEXT NOT NULL, accepted_event_id TEXT, UNIQUE(change_id, ordinal));
CREATE TABLE tasks (
 id TEXT PRIMARY KEY, change_id TEXT NOT NULL REFERENCES changes(id),
 revision_id TEXT NOT NULL REFERENCES plan_revisions(id), definition_json TEXT NOT NULL,
 definition_digest TEXT NOT NULL, state TEXT NOT NULL, row_version INTEGER NOT NULL DEFAULT 1,
 result_json TEXT);
CREATE TABLE phase_runs (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL, workspace_epoch TEXT NOT NULL,
 input_digest TEXT NOT NULL, input_json TEXT NOT NULL, action TEXT NOT NULL, method TEXT NOT NULL,
 owner_skill TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT, result_digest TEXT,
 started_at TEXT NOT NULL, ended_at TEXT, package_version TEXT NOT NULL, protocol_version INTEGER NOT NULL,
 package_digest TEXT NOT NULL, execution_instance TEXT NOT NULL,
 UNIQUE(workspace_epoch, request_id));
CREATE TABLE operations (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES phase_runs(id),
 effect_kind TEXT NOT NULL, state TEXT NOT NULL, input_digest TEXT NOT NULL,
 result_json TEXT, journal_path TEXT);
CREATE TABLE artifacts (id TEXT PRIMARY KEY, path TEXT UNIQUE, kind TEXT NOT NULL, current_version TEXT);
CREATE TABLE artifact_versions (
 id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(id),
 blob_digest TEXT NOT NULL REFERENCES blobs(digest), source_run_id TEXT NOT NULL REFERENCES phase_runs(id),
 source TEXT NOT NULL, observed_at TEXT NOT NULL);
CREATE TABLE verifications (
 id TEXT PRIMARY KEY, change_id TEXT REFERENCES changes(id),
 revision_id TEXT REFERENCES plan_revisions(id), source_run_id TEXT NOT NULL REFERENCES phase_runs(id),
 subject_kind TEXT NOT NULL, status TEXT NOT NULL, fingerprint_json TEXT NOT NULL, items_json TEXT NOT NULL,
 observed_at TEXT NOT NULL);
CREATE TABLE evidence (
 id TEXT PRIMARY KEY, source_run_id TEXT NOT NULL REFERENCES phase_runs(id),
 verification_id TEXT REFERENCES verifications(id), subject_kind TEXT NOT NULL,
 observer TEXT NOT NULL, method TEXT NOT NULL, content_digest TEXT NOT NULL REFERENCES blobs(digest),
 observed_at TEXT NOT NULL, limitations TEXT NOT NULL);
CREATE TABLE events (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES phase_runs(id),
 kind TEXT NOT NULL, payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE resource_claims (
 resource TEXT PRIMARY KEY, operation_id TEXT NOT NULL REFERENCES operations(id),
 state TEXT NOT NULL, generation TEXT NOT NULL, row_version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE source_runs (
 run_id TEXT NOT NULL REFERENCES phase_runs(id), source_run_id TEXT NOT NULL REFERENCES phase_runs(id),
 result_digest TEXT NOT NULL, purpose TEXT NOT NULL, PRIMARY KEY(run_id, source_run_id, purpose));
CREATE TABLE input_checks (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES phase_runs(id),
 target_type TEXT NOT NULL, target_id TEXT NOT NULL, expected_digest TEXT NOT NULL,
 purpose TEXT NOT NULL, result TEXT NOT NULL);
CREATE TABLE knowledge_proposals (
 id TEXT PRIMARY KEY, version INTEGER NOT NULL, owner_skill TEXT NOT NULL,
 target_kind TEXT NOT NULL, target_path TEXT NOT NULL, expected_digest TEXT,
 candidate_digest TEXT NOT NULL REFERENCES blobs(digest), source_json TEXT NOT NULL,
 state TEXT NOT NULL, created_run_id TEXT NOT NULL REFERENCES phase_runs(id),
 approved_event_id TEXT REFERENCES events(id), applied_operation_id TEXT REFERENCES operations(id));
CREATE TABLE delta_items (
 id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE REFERENCES knowledge_proposals(id),
 kind TEXT NOT NULL, target_path TEXT NOT NULL, expected_digest TEXT,
 candidate_digest TEXT NOT NULL REFERENCES blobs(digest), acceptance_json TEXT NOT NULL,
 predecessor_id TEXT REFERENCES delta_items(id));
CREATE TABLE spec_applications (
 id TEXT PRIMARY KEY, delta_id TEXT NOT NULL REFERENCES delta_items(id),
 proposal_id TEXT NOT NULL REFERENCES knowledge_proposals(id), proposal_version INTEGER NOT NULL,
 approved_event_id TEXT NOT NULL REFERENCES events(id), candidate_check_run_id TEXT NOT NULL REFERENCES phase_runs(id),
 baseline_digest TEXT, result_digest TEXT NOT NULL REFERENCES blobs(digest),
 artifact_version_id TEXT NOT NULL REFERENCES artifact_versions(id), operation_id TEXT NOT NULL UNIQUE REFERENCES operations(id),
 source_run_id TEXT NOT NULL REFERENCES phase_runs(id), verification_id TEXT REFERENCES verifications(id),
 UNIQUE(delta_id,result_digest));
CREATE TABLE rule_bindings (
 application_id TEXT PRIMARY KEY REFERENCES spec_applications(id),
 proposal_id TEXT NOT NULL REFERENCES knowledge_proposals(id),
 artifact_version_id TEXT NOT NULL REFERENCES artifact_versions(id),
 sources_json TEXT NOT NULL, scope_json TEXT NOT NULL);
'''


def identifier():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


def schema_compatible(connection):
    required_tables = set(re.findall(r'CREATE TABLE (\w+)', DDL))
    actual_tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required_tables.issubset(actual_tables):
        return False
    fields = {row[1] for row in connection.execute('PRAGMA table_info(phase_runs)')}
    return {'package_digest', 'execution_instance'}.issubset(fields)


def validate_lineage(connection, meta, guard):
    head, seen = meta.get('checkpoint'), set()
    while head and head != guard['checkpoint']:
        if head in seen:
            raise EvolveError('HISTORY_DIVERGED', 'Checkpoint lineage contains a cycle', exit_code=4)
        seen.add(head)
        row = connection.execute('SELECT parent_id FROM checkpoints WHERE id=?', (head,)).fetchone()
        head = row[0] if row else None
    if not head or guard['project_id'] != meta['project_id'] or guard['workspace_epoch'] != meta.get('workspace_epoch'):
        raise EvolveError('HISTORY_DIVERGED', 'History and local guard do not share the expected lineage', exit_code=4)


def create_database(path, project_id, epoch):
    """Build an init candidate. Caller installs it only through the init journal."""
    path = Path(path)
    if path.exists():
        raise EvolveError('PROJECT_COLLISION', 'Candidate database already exists')
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.executescript('BEGIN IMMEDIATE;\n' + DDL)
        checkpoint = identifier()
        connection.execute('INSERT INTO checkpoints VALUES (?, NULL)', (checkpoint,))
        meta = {'project_id': project_id, 'workspace_epoch': epoch,
                'schema_version': str(SCHEMA_VERSION), 'protocol_version': str(PROTOCOL_VERSION),
                'package_version': VERSION, 'checkpoint': checkpoint}
        connection.executemany('INSERT INTO project_meta VALUES (?, ?)', meta.items())
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


class Store:
    """Caller holds a short writer lock; no transaction spans file/command execution."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        from .protection import require_admission
        require_admission(self.root)
        path = inside(root, 'evolve/history.db')
        if not path.is_file():
            raise EvolveError('NOT_CONNECTED', 'No history database; explicit init is required')
        self.database_identity = (path.stat().st_dev, path.stat().st_ino)
        self.connection = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.execute('PRAGMA busy_timeout=3000')
        try:
            self.meta = dict(self.connection.execute('SELECT key,value FROM project_meta'))
            if (int(self.meta['schema_version']) != SCHEMA_VERSION or int(self.meta['protocol_version']) != PROTOCOL_VERSION
                    or not schema_compatible(self.connection)):
                raise EvolveError('SCHEMA_VERSION', 'Incomplete or unsupported schema/protocol; no migration performed')
            self.validate_guard(self.meta)
        except (KeyError, ValueError, TypeError, sqlite3.Error):
            self.connection.close()
            raise EvolveError('SCHEMA_VERSION', 'Cannot establish a supported history schema; data was preserved')
        except BaseException:
            self.connection.close()
            raise

    def validate_guard(self, meta):
        guard = inside(self.root, '.evolve-local/control/guard.json')
        if guard.exists():
            data = json.loads(guard.read_text())
            validate_lineage(self.connection, meta, data)

    def close(self):
        self.connection.close()

    def assert_current_database(self):
        from .protection import require_admission
        require_admission(self.root)
        path = inside(self.root, 'evolve/history.db')
        if not path.is_file() or (path.stat().st_dev, path.stat().st_ino) != self.database_identity:
            raise EvolveError('EXECUTION_CHANGED', 'The database file was replaced; old execution cannot write', exit_code=3)

    @contextmanager
    def transaction(self):
        self.assert_current_database()
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            current = dict(self.connection.execute('SELECT key,value FROM project_meta'))
            if current['project_id'] != self.meta['project_id'] or current['workspace_epoch'] != self.meta['workspace_epoch']:
                raise EvolveError('WORKSPACE_EPOCH', 'Project or epoch changed before committing facts', exit_code=3)
            self.validate_guard(current)
            yield self.connection
            checkpoint = identifier()
            self.connection.execute('INSERT INTO checkpoints VALUES (?, ?)', (checkpoint, current['checkpoint']))
            self.connection.execute("UPDATE project_meta SET value=? WHERE key='checkpoint'", (checkpoint,))
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise
        self.meta['checkpoint'] = checkpoint
        try:
            from .protection import save_guard
            save_guard(self.root, self.connection, self.meta)
        except OSError:
            raise EvolveError('NEEDS_RECOVERY', 'Database committed but local guard was not updated',
                              exit_code=4, committed=True,
                              next_steps=['Reconcile the committed checkpoint; do not rerun business effects'])

    def one(self, sql, values=()):
        return self.connection.execute(sql, values).fetchone()

    def run_started(self, run_id):
        row = self.one('SELECT status FROM phase_runs WHERE id=?', (run_id,))
        return row is not None and row['status'] == 'started'

    def blob(self, data):
        ensure_recordable(data)
        value = digest(data)
        self.connection.execute('INSERT OR IGNORE INTO blobs VALUES (?,?)', (value, data))
        return value

    def number(self, prefix):
        row = self.one('SELECT value FROM counters WHERE prefix=?', (prefix,))
        value = row[0] + 1 if row else 1
        self.connection.execute('INSERT INTO counters VALUES (?,?) ON CONFLICT(prefix) DO UPDATE SET value=?',
                                (prefix, value, value))
        return f'{prefix}-{value:03d}'

    def artifact(self, path, kind, content, run_id, source):
        previous = self.one('SELECT id FROM artifacts WHERE path=?', (path,)) if path is not None else None
        artifact_id = previous['id'] if previous else identifier()
        version_id = identifier()
        content_digest = self.blob(content)
        if previous:
            current_kind = self.one('SELECT kind FROM artifacts WHERE id=?', (artifact_id,))[0]
            if current_kind in ('knowledge', 'config') and current_kind != kind:
                raise EvolveError('ARTIFACT_AUTHORITY', 'Business observations cannot replace formal/configuration authority')
            self.connection.execute('UPDATE artifacts SET current_version=?,kind=? WHERE id=?', (version_id, kind, artifact_id))
        else:
            self.connection.execute('INSERT INTO artifacts VALUES (?,?,?,?)', (artifact_id, path, kind, version_id))
        self.connection.execute('INSERT INTO artifact_versions VALUES (?,?,?,?,?,?)',
                                (version_id, artifact_id, content_digest, run_id, source, now()))
        return {'entity_type': 'artifact_version', 'entity_id': version_id, 'digest': content_digest}

    def request_body(self, request, *, action, method, owner):
        if any(not isinstance(request.get(key), str) or not request[key] for key in
               ('project_id', 'expected_workspace_epoch', 'request_id')):
            raise EvolveError('INPUT', 'Prepared request must freeze its request, project and workspace identities')
        if request['project_id'] != self.meta['project_id']:
            raise EvolveError('PROJECT_IDENTITY', 'Request targets another project')
        if request['expected_workspace_epoch'] != self.meta['workspace_epoch']:
            raise EvolveError('WORKSPACE_EPOCH', 'Request belongs to an old workspace epoch', exit_code=3)
        body = {'action': action, 'method': method, 'owner_skill': owner,
                'request': {k: v for k, v in request.items() if k != 'request_id'}}
        return body, digest(canonical(body))

    def lookup(self, request, *, action, method, owner):
        body, input_digest = self.request_body(request, action=action, method=method, owner=owner)
        previous = self.one('SELECT * FROM phase_runs WHERE workspace_epoch=? AND request_id=?',
                            (self.meta['workspace_epoch'], request['request_id']))
        if previous:
            if previous['input_digest'] != input_digest:
                raise EvolveError('REQUEST_CONFLICT', 'Same request identity has different input', exit_code=3)
            if previous['status'] == 'started':
                raise EvolveError('NEEDS_RECOVERY', 'Existing run has not been safely finalized', exit_code=4)
            return previous['id'], json.loads(previous['result_json'])
        return None

    def start(self, request, *, action, method, owner, run_id=None):
        previous = self.lookup(request, action=action, method=method, owner=owner)
        if previous is not None:
            return previous
        body, input_digest = self.request_body(request, action=action, method=method, owner=owner)
        backup_ref = None
        first_connection = (action, method) == ('init', 'connect') and self.one('SELECT COUNT(*) FROM phase_runs')[0] == 0
        if first_connection:
            from .protection import initial_execution_indexes
            initial_execution_indexes(self.root, self.meta)
        if not first_connection and (action, method) not in {('maintain', 'recover'), ('maintain', 'backup')}:
            from .protection import require_action_protection
            require_action_protection(self.root, self.meta, action, method, request)
            from .backup import protect_before_write
            backup_ref = protect_before_write(self, request['request_id'])
        run_id = run_id or identifier()
        from .package import check_package
        package_digest = check_package()['content_digest']
        with self.transaction() as connection:
            connection.execute('INSERT INTO phase_runs (id,request_id,workspace_epoch,input_digest,input_json,'
                               'action,method,owner_skill,status,started_at,package_version,protocol_version,package_digest,execution_instance) '
                               'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                               (run_id, request['request_id'], self.meta['workspace_epoch'], input_digest,
                                canonical(body).decode(), action, method, owner, 'started', now(), VERSION, PROTOCOL_VERSION,
                                package_digest, canonical({'pid': os.getpid(), 'host': socket.gethostname(),
                                                           'generation': identifier()}).decode()))
            self.event(run_id, 'request_received', {'authorization': request['authorization']})
            if backup_ref:
                self.event(run_id, 'protection_backup', {'path': backup_ref})
        return run_id, None

    def input_check(self, run_id, target_type, target_id, expected_digest, purpose, *, status, code, reason):
        """Append an actual registered consumer's check; never copy source bodies."""
        if not self.run_started(run_id):
            raise EvolveError('RUN_FINALIZED', 'Input observations belong to an active consuming run', exit_code=3)
        check_id = identifier()
        self.connection.execute('INSERT INTO input_checks VALUES (?,?,?,?,?,?,?)',
            (check_id, run_id, target_type, target_id, expected_digest, purpose,
             canonical({'status': status, 'code': code, 'reason': reason, 'checked_at': now()}).decode()))
        return check_id

    def link_source(self, run_id, source_id, result_digest, purpose):
        """Owner has checked semantics; verify the exact sealed source and retain its use."""
        from .continuation import sealed_result
        sealed_result(self.connection, {'run_id': source_id, 'result_digest': result_digest})
        existing = self.one('SELECT result_digest FROM source_runs WHERE run_id=? AND source_run_id=? AND purpose=?',
                            (run_id, source_id, purpose))
        if existing:
            if existing[0] != result_digest:
                raise EvolveError('RUN_RESULT_INVALID', 'A recorded source use cannot change its expected result')
            return
        self.connection.execute('INSERT INTO source_runs VALUES (?,?,?,?)', (run_id, source_id, result_digest, purpose))
        self.input_check(run_id, 'phase_run', source_id, result_digest, purpose, status='passed',
            code='SOURCE_VALID', reason='Exact sealed input/result match; accepted for the stated owner purpose.')

    def rejected_source(self, run_id, reference, purpose, error):
        if (isinstance(reference, dict) and isinstance(reference.get('run_id'), str) and reference['run_id']
                and isinstance(reference.get('result_digest'), str) and reference['result_digest']):
            target_type, target_id, expected = 'phase_run', reference['run_id'], reference['result_digest']
        else:
            target_type, target_id = 'request', run_id
            expected = self.one('SELECT input_digest FROM phase_runs WHERE id=?', (run_id,))[0]
        self.input_check(run_id, target_type, target_id, expected, purpose, status='rejected',
                         code=error.code, reason=str(error))

    def event(self, run_id, kind, payload):
        event_id = identifier()
        self.connection.execute('INSERT INTO events VALUES (?,?,?,?,?)',
                                (event_id, run_id, kind, canonical(payload).decode(), now()))
        return event_id

    def finish(self, run_id, result, *, status='completed'):
        previous = self.one('SELECT status,result_json FROM phase_runs WHERE id=?', (run_id,))
        if previous is None or previous['status'] != 'started':
            raise EvolveError('RUN_FINALIZED', 'A terminal run cannot be rewritten', exit_code=3)
        result = {**result, 'run_id': run_id}
        from .change_views import prepare as prepare_view, install as install_view
        view = None
        with self.transaction() as connection:
            connection.execute('SAVEPOINT derived_view')
            try:
                view = prepare_view(self, run_id, result, status)
                connection.execute('RELEASE derived_view')
            except (EvolveError, OSError, ValueError, TypeError, KeyError) as error:
                connection.execute('ROLLBACK TO derived_view')
                connection.execute('RELEASE derived_view')
                from .privacy import redact
                self.event(run_id, 'change_view_unavailable', {'reason': redact(str(error))})
            connection.execute('UPDATE phase_runs SET status=?,result_json=?,result_digest=?,ended_at=? WHERE id=?',
                               (status, canonical(result).decode(), digest(canonical(result)), now(), run_id))
            self.event(run_id, 'run_finished', {'status': status, 'outcome': result.get('outcome')})
        install_view(self, view)
        return result
