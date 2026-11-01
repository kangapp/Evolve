"""Minimal pending protection and immutable capsules, independent of restored history."""
import json
from pathlib import Path
import re
import socket

from .checks import group_alive, validate_stop_observations
from .errors import EvolveError
from .external_material import regular_path
from .package import canonical, digest
from .workspace import current_digest, durable_write, inside

INDEX = '.evolve-local/control/external.json'
RECORDS = '.evolve-local/control/external-records/'


def record_path(root, operation_id):
    if not isinstance(operation_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', operation_id):
        raise EvolveError('EXTERNAL_OPERATION', 'Use an exact recorded operation identity')
    return inside(Path(root).resolve(), RECORDS + operation_id + '.json')


def load_index(root, meta):
    path = regular_path(root, INDEX)
    encoded = path.read_bytes()
    value = json.loads(encoded)
    if (not isinstance(value, dict) or any(value.get(k) != meta[k] for k in ('project_id', 'workspace_epoch'))
            or not isinstance(value.get('pending'), list)):
        raise EvolveError('EXTERNAL_PROTECTION_UNKNOWN', 'Pending protection differs from the current project/epoch', exit_code=4)
    seen = set()
    for row in value['pending']:
        if not isinstance(row, dict):
            raise EvolveError('EXTERNAL_PROTECTION_UNKNOWN', 'Pending references must be explicit operation objects', exit_code=4)
        record_path(root, row.get('operation_id'))
        if (row['operation_id'] in seen or row.get('state') not in ('running', 'unknown')
                or not isinstance(row.get('resources'), list) or not row['resources']
                or any(not isinstance(r, str) or not r for r in row['resources'])):
            raise EvolveError('EXTERNAL_PROTECTION_UNKNOWN', 'Pending protection has duplicate or incomplete operation references', exit_code=4)
        seen.add(row['operation_id'])
        if 'capsule_path' in row:
            capsule = read_capsule(root, row, meta['project_id'])
            if capsule.get('format') == 'evolve-external-capsule-v1' and (
                    row['resources'] != capsule.get('resources') or row.get('original_epoch') != capsule.get('original_epoch')):
                raise EvolveError('EXTERNAL_SOURCE_CONFLICT', 'Pending protection cannot change the immutable operation resources or source epoch', exit_code=4)
    return value, digest(encoded)



def require_recorded_reference(pending, value):
    """Protection does not replace an available operation's recorded source."""
    if pending is not None and value is not None:
        reference = value.get('capsule', {})
        if (any(pending.get(k) != reference.get(k) for k in ('capsule_path', 'capsule_digest'))
                or pending.get('resources') != value.get('resources')):
            raise EvolveError('EXTERNAL_SOURCE_CONFLICT', 'Pending protection disagrees with the recorded operation source; preserve both and investigate', exit_code=4)

def save_index(root, value, expected_digest):
    """Caller holds the shared writer lock. Preserve an unexpected external value."""
    path = inside(root, INDEX)
    if current_digest(path) != expected_digest:
        raise EvolveError('EXTERNAL_PROTECTION_CHANGED', 'Pending protection changed before its controlled update', exit_code=4)
    durable_write(path, canonical(value))
    return current_digest(path)


def save_capsule(root, value):
    """Only immutable non-secret source/authority facts; no mutable observation history."""
    path = record_path(root, value.get('operation_id'))
    if not isinstance(value.get('project_id'), str) or not value['project_id']:
        raise EvolveError('EXTERNAL_OPERATION', 'A protection capsule needs its actual project identity')
    encoded = canonical(value)
    expected = digest(encoded)
    if path.exists():
        regular_path(root, path.relative_to(Path(root).resolve()).as_posix())
        if current_digest(path) != expected:
            raise EvolveError('EXTERNAL_PROTECTION_CHANGED', 'An immutable operation capsule cannot be rewritten', exit_code=4)
    else:
        durable_write(path, encoded, new=True)
    return {'capsule_path': path.relative_to(Path(root).resolve()).as_posix(), 'capsule_digest': expected}


def read_capsule(root, reference, project_id):
    path = record_path(root, reference.get('operation_id'))
    if reference.get('capsule_path') != path.relative_to(Path(root).resolve()).as_posix():
        raise EvolveError('EXTERNAL_PROTECTION_UNKNOWN', 'Capsule reference does not identify its own controlled operation', exit_code=4)
    regular_path(root, reference['capsule_path'])
    if current_digest(path) != reference.get('capsule_digest'):
        raise EvolveError('EXTERNAL_PROTECTION_UNKNOWN', 'Immutable external source capsule is missing or changed', exit_code=4)
    value = json.loads(path.read_text())
    if value.get('operation_id') != reference['operation_id'] or value.get('project_id') != project_id:
        raise EvolveError('EXTERNAL_PROTECTION_UNKNOWN', 'External capsule belongs to another operation or project', exit_code=4)
    return value


def require_senders_stopped(index, observations=()):
    """Observe actual local process groups; an unknown launch needs specific evidence."""
    pending = []
    for row in index['pending']:
        sender = row.get('sender')
        if sender is None:
            # Protocol-15 controlled references had no actual dispatch mechanism.
            if 'capsule_path' in row:
                raise EvolveError('EXTERNAL_SENDER_UNKNOWN', 'A real operation capsule lacks its sender protection', exit_code=4)
            continue
        if (not isinstance(sender, dict) or any(not isinstance(sender.get(k), str) or not sender[k]
                for k in ('execution_id', 'command_digest', 'host', 'prepared_at'))):
            raise EvolveError('EXTERNAL_SENDER_UNKNOWN', 'Cannot interpret the protected dispatch sender', exit_code=4)
        if 'pid' in sender:
            if type(sender['pid']) is not int or sender['pid'] <= 0:
                raise EvolveError('EXTERNAL_SENDER_UNKNOWN', 'Dispatch sender PID is not an actual process identity', exit_code=4)
            if sender['host'] != socket.gethostname():
                pending.append({**sender, 'state': 'foreign_host'})
            elif group_alive(sender['pid']):
                pending.append({**sender, 'state': 'process_group_present'})
        elif sender.get('state') not in ('not_started', 'stopped'):
            pending.append({**sender, 'state': 'launch_unknown'})
    return validate_stop_observations(pending, list(observations))
