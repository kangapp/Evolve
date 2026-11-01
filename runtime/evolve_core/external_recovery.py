"""Merge real pending capsules from a selected archive with current protection."""
import json
from pathlib import Path
import sqlite3

from .errors import EvolveError
from . import external_registry as registry
from .package import canonical, digest
from .workspace import current_digest


def snapshot_pending(database, project_id, *, current_snapshot=False):
    connection = sqlite3.connect(Path(database).as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        result, capsules = [], {}
        for operation in connection.execute("SELECT * FROM operations WHERE effect_kind='external_write'"):
            value = json.loads(operation['result_json']) if operation['result_json'] else {}
            if value.get('terminal_confirmed'):
                continue
            reference = value.get('capsule')
            if not isinstance(reference, dict):
                raise EvolveError('EXTERNAL_SOURCE_UNKNOWN', 'Selected snapshot has an unknown effect without its exact source', exit_code=4)
            blob = connection.execute('SELECT content FROM blobs WHERE digest=?', (reference.get('capsule_digest'),)).fetchone()
            if not blob or digest(blob[0]) != reference['capsule_digest']:
                raise EvolveError('EXTERNAL_SOURCE_UNKNOWN', 'Selected snapshot lacks the immutable external capsule attachment', exit_code=4)
            capsule = json.loads(blob[0])
            if (canonical(capsule) != blob[0] or capsule.get('operation_id') != operation['id']
                    or capsule.get('project_id') != project_id or capsule.get('resources') != value.get('resources')):
                raise EvolveError('EXTERNAL_SOURCE_UNKNOWN', 'Snapshot operation and exact capsule disagree', exit_code=4)
            events = [json.loads(r[0]) for r in connection.execute(
                "SELECT payload_json FROM events WHERE run_id=? AND kind='external_sender_started'", (capsule['run_id'],))]
            admitted = [json.loads(r[0]) for r in connection.execute(
                "SELECT payload_json FROM events WHERE run_id=? AND kind='external_dispatch_admitted'", (capsule['run_id'],))]
            sender = (events[-1]['sender'] if events else admitted[-1]['sender'] if admitted else capsule.get('sender_identity'))
            if current_snapshot and not admitted and operation['state'] == 'prepared' and sender:
                sender = {**sender, 'state': 'not_started'}
            if not sender:
                raise EvolveError('EXTERNAL_SENDER_UNKNOWN', 'Selected pending source has no exact sender identity', exit_code=4)
            # A snapshot before admission is not proof that its actor never launched later.
            row = {**reference, 'operation_id': operation['id'], 'resources': capsule['resources'],
                   'state': 'unknown', 'sender': sender, 'original_epoch': capsule['original_epoch'],
                   'target': capsule['candidate']['target_snapshot']}
            result.append(row)
            capsules[operation['id']] = capsule
        return result, capsules
    finally:
        connection.close()


def merge(root, current, database=None, *, capsules=None, current_snapshot=False):
    selected, attachments = snapshot_pending(database, current['project_id'], current_snapshot=current_snapshot) if database else ([], {})
    capsules = dict(capsules or {})
    for operation_id, capsule in attachments.items():
        if operation_id in capsules and capsules[operation_id] != capsule:
            raise EvolveError('EXTERNAL_PROTECTION_CHANGED', 'Snapshot sources disagree about the same immutable operation', exit_code=4)
        capsules[operation_id] = capsule
    pending = {r['operation_id']: r for r in current['pending']}
    for row in selected:
        old = pending.get(row['operation_id'])
        if old:
            if any(old.get(k) != row[k] for k in ('capsule_path', 'capsule_digest', 'resources')):
                raise EvolveError('EXTERNAL_PROTECTION_CHANGED', 'Current and selected pending operation sources conflict', exit_code=4)
            # Current sender protection is later than this selected cutoff; preserve it.
        else:
            pending[row['operation_id']] = row
    for row in pending.values():
        if not row.get('capsule_path'):
            continue  # Explicit legacy protocol-15 controlled reference; no actual sender.
        path = registry.record_path(root, row['operation_id'])
        if row['capsule_path'] != path.relative_to(Path(root).resolve()).as_posix():
            raise EvolveError('EXTERNAL_SOURCE_UNKNOWN', 'Pending capsule path is not its own controlled identity', exit_code=4)
        if path.exists():
            if current_digest(path) != row['capsule_digest']:
                raise EvolveError('EXTERNAL_PROTECTION_CHANGED', 'Preserve conflicting existing external capsule bytes', exit_code=4)
            registry.read_capsule(root, row, current['project_id'])
        elif row['operation_id'] not in capsules:
            raise EvolveError('EXTERNAL_SOURCE_UNKNOWN', 'Current pending source is absent from both actual protection and selected immutable snapshot', exit_code=4)
    return {**current, 'pending': list(pending.values())}, capsules
