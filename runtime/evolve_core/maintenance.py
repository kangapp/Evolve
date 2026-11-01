"""Explicit complete backup and resumable offline archive restore/14/15/16→17 upgrade."""
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

from . import VERSION, PROTOCOL_VERSION
from .archive_sets import (MAX_SET_BYTES, RESERVE_BYTES, collect_archive, inspect_database,
                           managed_path, validate_archive)
from .errors import EvolveError
from .package import canonical, check_package, digest, UPGRADE_PROTOCOLS
from .protection import (managed_index, protected_identity,
                         require_drained)
from .requests import normalize, require_effect
from .store import Store, identifier, now, validate_lineage
from .workspace import current_digest, durable_write, inside, writer_lock


def backup(root, payload):
    request = normalize(payload)
    require_effect(request, 'project_records')
    root = Path(root).resolve()
    with writer_lock(root, recover_dead=True):
        store = Store(root)
        try:
            body, input_digest = store.request_body(request, action='maintain', method='backup', owner='evolve-maintain')
            previous = store.one('SELECT * FROM phase_runs WHERE workspace_epoch=? AND request_id=?',
                                 (store.meta['workspace_epoch'], request['request_id']))
            if previous and previous['input_digest'] != input_digest:
                raise EvolveError('REQUEST_CONFLICT', 'Backup retry changed its original request', exit_code=3)
            if previous and previous['status'] != 'started':
                return json.loads(previous['result_json'])
            run_id = previous['id'] if previous else store.start(request, action='maintain', method='backup', owner='evolve-maintain')[0]
            folder = inside(root, '.evolve-local/backups/manual/' + request['request_id'])
            if folder.exists():
                path = folder / 'manifest.json'
                manifest = validate_archive(folder, digest(path.read_bytes()))
                if manifest['requested_by'] != request['request_id'] or any(manifest[k] != store.meta[k] for k in ('project_id', 'workspace_epoch')):
                    raise EvolveError('BACKUP_CONFLICT', 'Existing backup is not this request and epoch', exit_code=4)
                result = {'path': str(folder), 'manifest_digest': digest(path.read_bytes()), 'checkpoint': manifest['checkpoint']}
            else:
                result = collect_archive(store, folder, request['request_id'])
            return store.finish(run_id, {**result, 'committed': True, 'outcome': 'backed_up',
                'project_id': store.meta['project_id'], 'workspace_epoch': store.meta['workspace_epoch'],
                'business_data_included': False})
        finally:
            store.close()


@contextmanager
def history_copy(root):
    """Copy bounded raw DB/sidecars without connecting to the live archive."""
    database = managed_path(root, 'evolve/history.db', 'database')
    paths = [database.with_name(database.name + s) for s in ('', '-wal', '-shm', '-journal')]
    if sum(p.stat().st_size for p in paths if p.is_file()) > MAX_SET_BYTES:
        raise EvolveError('ARCHIVE_CAPACITY', 'History exceeds the supported maintenance inspection budget', exit_code=4)
    before = {p: current_digest(p) for p in paths}
    with tempfile.TemporaryDirectory(prefix='evolve-maintenance-inspect-') as folder:
        for path, value in before.items():
            if value is not None:
                shutil.copyfile(path, Path(folder) / path.name)
        if before != {p: current_digest(p) for p in paths}:
            raise EvolveError('RESTORE_CHANGED', 'History changed during maintenance inspection', exit_code=4)
        yield Path(folder) / 'history.db'


def raw_history(root):
    """Inspect a copy, including WAL, without opening the live database."""
    with history_copy(root) as path:
        return inspect_database(path)


def external_protection(root, project_id, *, protocol_version=None):
    path = inside(root, '.evolve-local/control/external.json')
    if not path.is_file():
        if str(protocol_version) in ('16', '17'):
            raise EvolveError('EXTERNAL_PROTECTION_UNKNOWN', 'Actual sender protection is missing; absence cannot establish drainage', exit_code=4)
        return {'project_id': project_id, 'coverage': 'unverified', 'pending': []}
    value = json.loads(path.read_text())
    if value.get('project_id') != project_id or not isinstance(value.get('pending'), list):
        raise EvolveError('EXTERNAL_UNKNOWN', 'External protection identity or collection is inconsistent', exit_code=4)
    seen = set()
    for item in value['pending']:
        if (not isinstance(item, dict) or not isinstance(item.get('operation_id'), str)
                or item['operation_id'] in seen or item.get('state') not in ('running', 'unknown')
                or not isinstance(item.get('resources'), list) or not item['resources']
                or any(not isinstance(r, str) or not r for r in item['resources'])):
            raise EvolveError('EXTERNAL_UNKNOWN', 'External pending references require exact identities and resources', exit_code=4)
        seen.add(item['operation_id'])
    return value


def observed_collection(root, index, external=None):
    """Known managed files and control journals only; never glob business sources."""
    paths = {r['path']: r['kind'] for r in index['files']}
    paths['evolve/history.db'] = 'database'
    for suffix in ('-wal', '-shm', '-journal'):
        name = 'evolve/history.db' + suffix
        if inside(root, name).exists():
            paths[name] = 'sidecar'
    control = inside(root, '.evolve-local/control')
    for name in ('guard.json', 'managed.json', 'checks.json', 'external.json', 'init.json'):
        if (control / name).exists():
            paths['.evolve-local/control/' + name] = 'control'
    if (control / 'operations').exists():
        for path in sorted((control / 'operations').glob('*.json')):
            paths[path.relative_to(root).as_posix()] = 'old_journal'
    for item in (external or {}).get('pending', []):
        if item.get('capsule_path'):
            paths[item['capsule_path']] = 'external_capsule'
    result = []
    total = 0
    for name, kind in sorted(paths.items()):
        path = inside(root, name)
        if kind in ('knowledge', 'config', 'database'):
            managed_path(root, name, kind)
        size = path.stat().st_size if path.is_file() else 0
        total += size
        if total > MAX_SET_BYTES:
            raise EvolveError('ARCHIVE_CAPACITY', 'Current protection exceeds its budget; nothing read or truncated', exit_code=4)
        value = current_digest(path)
        result.append({'path': name, 'kind': kind, 'digest': value, 'bytes': size})
    if total > MAX_SET_BYTES:
        raise EvolveError('ARCHIVE_CAPACITY', 'Current archive protection exceeds the supported budget', exit_code=4)
    return result


def prepare(root, request, method):
    data = request['input']
    current = None
    try:
        current = raw_history(root)
    except EvolveError:
        if method in ('upgrade', 'repair'):
            raise
    if method == 'upgrade':
        meta, registered, pending = current
        if meta['protocol_version'] not in UPGRADE_PROTOCOLS:
            raise EvolveError('UPGRADE_UNSUPPORTED', 'Only explicit protocol 14/15/16→17 upgrade is supported', exit_code=4)
        index = {'protocol_version': int(meta['protocol_version']),
                 'files': [{'path': r['path'], 'kind': r['kind'], 'digest': r['blob_digest']} for r in registered],
                 'executions': pending}
        guard_path = inside(root, '.evolve-local/control/guard.json')
        if not guard_path.is_file():
            raise EvolveError('PROTECTION_UNKNOWN', 'Upgrade requires the actual old local lineage guard', exit_code=4)
        guard = json.loads(guard_path.read_text())
        with history_copy(root) as path:
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            try:
                validate_lineage(connection, meta, guard)
                from .checks import pending_checks
                if (any(pending_checks(connection, r[0]) for r in connection.execute('SELECT id FROM phase_runs'))
                        or connection.execute("SELECT id FROM operations WHERE state IN ('prepared','needs_recovery') LIMIT 1").fetchone()):
                    raise EvolveError('NEEDS_RECOVERY', 'Reconcile old-protocol checks and file effects with their original package before upgrade', exit_code=4)
            finally:
                connection.close()
        operations = inside(root, '.evolve-local/control/operations')
        if operations.exists() and any(json.loads(p.read_text()).get('state') != 'committed' for p in operations.glob('*.json')):
            raise EvolveError('NEEDS_RECOVERY', 'Complete old file journals before explicit protocol upgrade', exit_code=4)
        if pending:
            raise EvolveError('NEEDS_RECOVERY', 'Close interrupted old-protocol runs before upgrading', exit_code=4)
        bundle, manifest_digest = None, None
    elif method == 'repair':
        meta, registered, pending = current
        guard, index = protected_identity(root)
        if (meta['protocol_version'] != str(PROTOCOL_VERSION)
                or any(meta[k] != guard[k] for k in ('project_id', 'workspace_epoch', 'checkpoint'))):
            raise EvolveError('REPAIR_UNSAFE', 'Repair requires a supported intact archive and matching current protection checkpoint', exit_code=4)
        with history_copy(root) as path:
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            try:
                evidence = repair_evidence(connection, root, meta, pending)
            finally:
                connection.close()
        bundle, manifest_digest = None, None
    else:
        guard, index = protected_identity(root)
        if current:
            meta = current[0]
            if any(meta[k] != guard[k] for k in ('project_id', 'workspace_epoch', 'checkpoint')):
                raise EvolveError('PROTECTION_UNKNOWN', 'Healthy database differs from its protective checkpoint; reconcile before restore', exit_code=4)
        bundle = Path(data.get('bundle', '')).absolute()
        manifest_digest = data.get('manifest_digest')
        manifest = validate_archive(bundle, manifest_digest)
        if manifest['project_id'] != guard['project_id']:
            raise EvolveError('PROJECT_IDENTITY', 'Restore cannot import another project archive', exit_code=4)
        if manifest['protocol_version'] != PROTOCOL_VERSION:
            raise EvolveError('UPGRADE_REQUIRED', 'Use a current-protocol archive; protocol 14 requires its separate upgrade first', exit_code=4)
        known = {r['path'] for r in index['files']}
        for item in manifest['files']:
            path = managed_path(root, item['path'], item['kind'])
            if item['kind'] != 'database' and item['path'] not in known and path.exists():
                raise EvolveError('RESTORE_COLLISION', 'Unregistered user file occupies a restore target: ' + item['path'], exit_code=4)
    if (request.get('project_id') != guard['project_id']
            or request.get('expected_workspace_epoch') != guard['workspace_epoch']):
        raise EvolveError('WORKSPACE_EPOCH', 'Maintenance plan must bind the current local identity and epoch', exit_code=3)
    from .external_recovery import merge
    if method == 'repair' and 'external.json' in evidence['missing']:
        external = {'project_id': meta['project_id'], 'workspace_epoch': meta['workspace_epoch'],
                    'pending': [], 'coverage': 'local-protocol-' + meta['protocol_version']}
    else:
        external = external_protection(root, guard['project_id'], protocol_version=index.get('protocol_version'))
    capsules = {}
    if current and current[0]['protocol_version'] in ('16', '17'):
        with history_copy(root) as current_database:
            external, capsules = merge(root, external, current_database, current_snapshot=True)
    external, capsules = merge(root, external, bundle / 'authority/evolve/history.db' if bundle else None, capsules=capsules)
    require_drained(root, index.get('executions', []), data.get('check_observations', []), legacy=method in ('upgrade', 'repair'),
                    external_index=external, sender_observations=data.get('sender_observations', []))
    observed = observed_collection(root, index, external)
    if method == 'repair':
        observed.extend({'path': '.evolve-local/control/' + name, 'kind': 'control', 'digest': None, 'bytes': 0}
                        for name in evidence['missing'])
    plan = {'format': 'evolve-maintenance-plan-v1', 'method': method, 'plan_id': request['request_id'],
        'project_id': guard['project_id'], 'old_epoch': guard['workspace_epoch'], 'new_epoch': identifier(),
        'checkpoint': guard['checkpoint'], 'package_digest': check_package()['content_digest'],
        'bundle': str(bundle) if bundle else None, 'manifest_digest': manifest_digest,
        'observed': observed, 'managed': index['files'], 'executions': index.get('executions', []),
        'external': external, 'external_capsules': capsules, 'sender_observations': data.get('sender_observations', []),
        'check_observations': data.get('check_observations', []),
        'authorization': request['authorization'], 'observed_at': now(),
        'business_data_restored': False, 'commands_replayed': False}
    if method == 'restore':
        restored = {r['path'] for r in manifest['files']}
        plan['quarantined_managed'] = [r['path'] for r in index['files'] if r['path'] not in restored]
        plan['targets'] = manifest['files']
    else:
        plan['quarantined_managed'], plan['targets'] = [], []
    if method == 'repair':
        plan['repair_evidence'] = evidence
    return plan


def repair_evidence(connection, root, meta, pending):
    """Rebuild only missing ledgers supported by complete retained execution facts."""
    from .checks import pending_checks
    from .continuation import retained_source, sealed_result
    missing = [name for name in ('checks.json', 'external.json', 'init.json')
               if not inside(root, '.evolve-local/control/' + name).exists()]
    if not missing:
        raise EvolveError('REPAIR_UNSAFE', 'No supported missing ledger; inspect existing bytes rather than replacing them')
    for name in ('checks.json', 'external.json'):
        if name not in missing:
            value = json.loads(inside(root, '.evolve-local/control/' + name).read_text())
            if not isinstance(value, dict) or any(value.get(k) != meta[k] for k in ('project_id', 'workspace_epoch')):
                raise EvolveError('REPAIR_UNSAFE', 'Existing execution protection has another identity: ' + name, exit_code=4)
    if pending or any(pending_checks(connection, r[0]) for r in connection.execute('SELECT id FROM phase_runs')):
        raise EvolveError('REPAIR_UNSAFE', 'Unfinished runs or check dispatches prevent reconstruction; recover original executions first', exit_code=4)
    if connection.execute("SELECT id FROM operations WHERE state IN ('prepared','needs_recovery') LIMIT 1").fetchone():
        raise EvolveError('REPAIR_UNSAFE', 'Unfinished file effects require their original recovery', exit_code=4)
    if 'external.json' in missing and connection.execute("SELECT id FROM events WHERE kind LIKE 'external_%' LIMIT 1").fetchone():
        raise EvolveError('REPAIR_UNSAFE', 'Missing sender protection with external execution history requires original retained protection', exit_code=4)
    original = connection.execute("SELECT * FROM phase_runs WHERE action='init' AND method='connect' AND status='completed' ORDER BY rowid LIMIT 1").fetchone()
    if original is None:
        raise EvolveError('REPAIR_UNSAFE', 'No safely completed retained project connection supports reconstruction', exit_code=4)
    _, request, result = sealed_result(connection, {'run_id': original['id'], 'result_digest': original['result_digest']})
    if not retained_source(connection, original, request) or result.get('outcome') != 'connected':
        raise EvolveError('REPAIR_UNSAFE', 'Retained connection does not establish this project identity', exit_code=4)
    return {'missing': missing, 'connection_run_id': original['id'], 'connection_result_digest': original['result_digest'],
            'connection_request': request, 'unfinished_runs': 0, 'unfinished_checks': 0,
            'basis': 'Matching protected checkpoint and sealed connection; all retained check dispatches terminal. Missing sender ledger allowed only without external execution history.'}


def stage_path(root, plan_id):
    # normalize validates the same identifier grammar without accepting path segments.
    normalize({'request_id': plan_id, 'authorization': {'source': 'internal', 'text': 'validate identifier',
               'effect_kinds': ['project_records']}, 'input': {}})
    return inside(root, '.evolve-local/control/restores/' + plan_id)


def recheck(root, observed):
    for item in observed:
        if current_digest(inside(root, item['path'])) != item['digest']:
            raise EvolveError('RESTORE_CHANGED', 'Current bytes differ from the presented maintenance plan: ' + item['path'], exit_code=4)


def fault_point(name):
    """Tests replace this function in their own subprocess; no user fault switch."""


def candidate_database(source, target, plan, *, source_digest):
    shutil.copyfile(source, target)
    if current_digest(target) != source_digest:
        raise EvolveError('ARCHIVE_CHANGED', 'Copied database differs from the exact approved/protected source bytes', exit_code=4)
    connection = sqlite3.connect(target, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('BEGIN IMMEDIATE')
        checkpoint = identifier()
        connection.execute('INSERT INTO checkpoints VALUES (?,?)', (checkpoint, plan['checkpoint'] if plan['method'] == 'upgrade' else
            connection.execute("SELECT value FROM project_meta WHERE key='checkpoint'").fetchone()[0]))
        for key, value in (('workspace_epoch', plan['new_epoch']), ('checkpoint', checkpoint),
                           ('protocol_version', str(PROTOCOL_VERSION)), ('package_version', VERSION)):
            connection.execute('UPDATE project_meta SET value=? WHERE key=?', (value, key))
        # Restored started registrations are history, never dispatch instructions.
        for row in connection.execute("SELECT id FROM phase_runs WHERE status='started'").fetchall():
            result = {'run_id': row['id'], 'committed': None, 'outcome': 'interrupted_by_archive_restore',
                      'maintenance_plan': plan['plan_id'], 'commands_replayed': False}
            connection.execute("UPDATE phase_runs SET status='interrupted',result_json=?,result_digest=?,ended_at=? WHERE id=?",
                (canonical(result).decode(), digest(canonical(result)), now(), row['id']))
        connection.execute("UPDATE operations SET state='failed',result_json=? WHERE state!='committed'",
                           (canonical({'maintenance_plan': plan['plan_id'], 'commands_replayed': False}).decode(),))
        connection.execute('DELETE FROM resource_claims')
        connection.commit()
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or connection.execute('PRAGMA foreign_key_check').fetchone():
            raise EvolveError('ARCHIVE_DATABASE', 'Prepared replacement database failed integrity validation', exit_code=4)
        return dict(connection.execute('SELECT key,value FROM project_meta'))
    finally:
        connection.close()


def protect_and_stage(root, folder, plan):
    observed = plan['observed']
    recheck(root, observed)
    required = (sum(r['bytes'] for r in observed) * 2
                + sum(r['bytes'] for r in plan['targets']) * 2 + RESERVE_BYTES)
    if shutil.disk_usage(folder).free < required:
        raise EvolveError('ARCHIVE_SPACE', 'Insufficient space to protect current archive before maintenance', exit_code=4)
    protection = folder / 'protection'
    protection.mkdir(exist_ok=True)
    for row in observed:
        if row['digest'] is not None:
            original = inside(root, row['path']).read_bytes()
            if digest(original) != row['digest']:
                raise EvolveError('RESTORE_CHANGED', 'Current bytes changed during protection', exit_code=4)
            target = inside(protection, row['path'])
            if target.exists() and current_digest(target) != row['digest']:
                raise EvolveError('PROTECTION_UNKNOWN', 'Previously protected bytes changed', exit_code=4)
            if not target.exists():
                durable_write(target, original, new=True)
    recheck(root, observed)
    durable_write(protection / 'manifest.json', canonical({'complete': True, 'files': observed}), new=True)
    source = (Path(plan['bundle']) / 'authority/evolve/history.db' if plan['method'] == 'restore'
              else protection / 'evolve/history.db')
    candidate = folder / 'candidate.db'
    # Candidate uses fixed protected bytes. Include WAL for an old-protocol upgrade.
    if plan['method'] in ('upgrade', 'repair'):
        with tempfile.TemporaryDirectory(prefix='evolve-upgrade-snapshot-') as temporary:
            for suffix in ('', '-wal', '-shm', '-journal'):
                path = protection / ('evolve/history.db' + suffix)
                if path.is_file():
                    shutil.copyfile(path, Path(temporary) / ('history.db' + suffix))
            old = sqlite3.connect(Path(temporary) / 'history.db')
            new = sqlite3.connect(folder / 'upgrade-source.db')
            try:
                old.backup(new)
            finally:
                new.close(); old.close()
        source = folder / 'upgrade-source.db'
    source_digest = (next(r['digest'] for r in plan['targets'] if r['kind'] == 'database')
                     if plan['method'] == 'restore' else current_digest(source))
    meta = candidate_database(source, candidate, plan, source_digest=source_digest)
    steps = []
    before = {r['path']: r['digest'] for r in observed}
    if plan['method'] == 'restore':
        for row in plan['targets']:
            if row['kind'] != 'database':
                content = (Path(plan['bundle']) / row['payload']).read_bytes()
                if digest(content) != row['digest']:
                    raise EvolveError('ARCHIVE_INVALID', 'Selected archive changed before staging', exit_code=4)
                target = folder / 'candidates' / row['path']
                durable_write(target, content, new=True)
                steps.append({'path': row['path'], 'before': before.get(row['path']),
                              'after': row['digest'], 'candidate': str(target.relative_to(folder))})
    for row in observed:
        if (row['path'] in plan['quarantined_managed'] or row['kind'] in ('sidecar', 'old_journal')):
            steps.append({'path': row['path'], 'before': row['digest'], 'after': None, 'candidate': None})
    for operation_id, capsule in plan.get('external_capsules', {}).items():
        from .external_registry import record_path
        name = record_path(root, operation_id).relative_to(Path(root).resolve()).as_posix()
        content = canonical(capsule)
        if before.get(name) is None:
            target = folder / 'candidates' / name
            durable_write(target, content, new=True)
            steps.append({'path': name, 'before': None, 'after': digest(content),
                          'candidate': str(target.relative_to(folder))})
    steps.append({'path': 'evolve/history.db', 'before': before['evolve/history.db'],
                  'after': current_digest(candidate), 'candidate': 'candidate.db'})
    connection = sqlite3.connect(candidate)
    connection.row_factory = sqlite3.Row
    try:
        index = canonical(managed_index(connection, meta))
    finally:
        connection.close()
    control_values = {
        'managed.json': json.loads(index),
        'guard.json': {**{k: meta[k] for k in ('project_id', 'workspace_epoch', 'checkpoint')}, 'managed_index_digest': digest(index)},
        'checks.json': {'project_id': meta['project_id'], 'workspace_epoch': meta['workspace_epoch'], 'attempts': {}},
        'external.json': {**plan['external'], 'workspace_epoch': meta['workspace_epoch'],
                         'pending': [{**r, 'state': 'unknown', 'requires_reconciliation': True} for r in plan['external']['pending']]}}
    if plan['method'] == 'repair' and 'init.json' in plan['repair_evidence']['missing']:
        evidence = plan['repair_evidence']
        control_values['init.json'] = {'state': 'committed', 'project_id': meta['project_id'],
            'workspace_epoch': meta['workspace_epoch'], 'run_id': evidence['connection_run_id'],
            'request': evidence['connection_request'], 'repaired_by_plan': plan['plan_id'],
            'connection_result_digest': evidence['connection_result_digest']}
    for name, value in control_values.items():
        target = folder / 'candidates' / name
        content = canonical(value)
        durable_write(target, content, new=True)
        path = '.evolve-local/control/' + name
        steps.append({'path': path, 'before': before.get(path), 'after': digest(content),
                      'candidate': str(target.relative_to(folder))})
    return {'state': 'prepared', 'steps': steps, 'completed_steps': 0, 'new_meta': meta}


def validate_protection(folder, plan):
    protection = folder / 'protection'
    manifest = json.loads((protection / 'manifest.json').read_text())
    if manifest != {'complete': True, 'files': plan['observed']}:
        raise EvolveError('PROTECTION_UNKNOWN', 'Maintenance protection manifest changed', exit_code=4)
    for row in plan['observed']:
        if current_digest(inside(protection, row['path'])) != row['digest']:
            raise EvolveError('PROTECTION_UNKNOWN', 'Protected original bytes changed: ' + row['path'], exit_code=4)
    return protection


def journal_payload_digest(journal):
    return digest(canonical({k: journal[k] for k in
        ('steps', 'new_meta', 'request_digest', 'request_id', 'authorization', 'request')}))


def apply_plan(root, request, plan, folder):
    body_digest = digest(canonical(request))
    journal_path = folder / 'journal.json'
    if journal_path.is_file():
        journal = json.loads(journal_path.read_text())
        if journal['request_digest'] != body_digest:
            raise EvolveError('REQUEST_CONFLICT', 'Maintenance retry must preserve the exact apply request', exit_code=3)
    else:
        journal = None
    if (request['project_id'] != plan['project_id'] or request['expected_workspace_epoch'] != plan['old_epoch']
            or plan['package_digest'] != check_package()['content_digest']):
        raise EvolveError('WORKSPACE_EPOCH', 'Maintenance request or executing package changed', exit_code=4)
    if plan['method'] == 'restore':
        validate_archive(Path(plan['bundle']), plan['manifest_digest'])
    token = request['request_id']
    with writer_lock(root, recover_dead=True, maintenance_token=token):
        barrier_path = inside(root, '.evolve-local/control/maintenance.json')
        if journal is not None:
            barrier = json.loads(barrier_path.read_text()) if barrier_path.is_file() else {}
            if (barrier.get('plan_id') != plan['plan_id'] or barrier.get('request_id') != token
                    or barrier.get('journal_payload_digest') != journal_payload_digest(journal)
                    or journal.get('state') not in ('prepared', 'completed')
                    or type(journal.get('completed_steps')) is not int
                    or not 0 <= journal['completed_steps'] <= len(journal['steps'])):
                raise EvolveError('JOURNAL_INVALID', 'Swap journal differs from its immutable maintenance admission', exit_code=4)
            if journal['state'] == 'completed':
                if barrier.get('result_digest') != digest(canonical(journal['result'])):
                    raise EvolveError('JOURNAL_INVALID', 'Completed maintenance receipt differs from its durable result', exit_code=4)
                if barrier.get('state') != 'completed':
                    durable_write(barrier_path, canonical({**barrier, 'state': 'completed',
                        'new_epoch': journal['new_meta']['workspace_epoch']}))
                return journal['result']
        if journal is None:
            recheck(root, plan['observed'])
            require_drained(root, plan['executions'], plan['check_observations'], legacy=plan['method'] in ('upgrade', 'repair'),
                            external_index=plan['external'], sender_observations=plan.get('sender_observations', []))
            barrier = {'request_id': token, 'plan_id': plan['plan_id'], 'state': 'active', 'old_epoch': plan['old_epoch']}
            durable_write(inside(root, '.evolve-local/control/maintenance.json'), canonical(barrier))
            fault_point('barrier')
            # Safe retries before journal creation can reconstruct staging from unchanged protected originals.
            for name in ('candidate.db', 'upgrade-source.db'):
                (folder / name).unlink(missing_ok=True)
            staging = folder / 'candidates'
            if staging.exists():
                shutil.rmtree(staging)
            manifest = folder / 'protection/manifest.json'
            manifest.unlink(missing_ok=True)
            journal = {**protect_and_stage(root, folder, plan), 'request_digest': body_digest,
                       'request_id': token, 'authorization': request['authorization'], 'request': request}
            barrier['journal_payload_digest'] = journal_payload_digest(journal)
            durable_write(barrier_path, canonical(barrier))
            fault_point('staged')
            durable_write(journal_path, canonical(journal), new=True)
            fault_point('prepared')
        # The current check index may already be the new epoch's empty one.
        # Resume stopping evidence against the exact protected old execution set.
        protection = validate_protection(folder, plan)
        require_drained(root, plan['executions'], plan['check_observations'], legacy=plan['method'] in ('upgrade', 'repair'),
                        check_index=protection / '.evolve-local/control/checks.json',
                        external_index=plan['external'], sender_observations=plan.get('sender_observations', []))
        for i, step in enumerate(journal['steps']):
            path = inside(root, step['path'])
            expected = step['after'] if i < journal['completed_steps'] else step['before']
            observed = current_digest(path)
            if observed != expected and not (i == journal['completed_steps'] and observed == step['after']):
                raise EvolveError('RESTORE_CHANGED', 'Third-party value preserved during maintenance: ' + step['path'], exit_code=4)
            if i < journal['completed_steps']:
                continue
            fault_point('before:' + step['path'])
            if current_digest(path) != observed:
                raise EvolveError('RESTORE_CHANGED', 'Target changed immediately before maintenance replacement', exit_code=4)
            if observed != step['after']:
                if step['candidate'] is None:
                    path.unlink(missing_ok=True)
                else:
                    content = inside(folder, step['candidate']).read_bytes()
                    if digest(content) != step['after']:
                        raise EvolveError('JOURNAL_INVALID', 'Maintenance candidate bytes changed', exit_code=4)
                    durable_write(path, content, new=observed is None)
            fault_point('after:' + step['path'])
            journal['completed_steps'] = i + 1
            durable_write(journal_path, canonical(journal))
        meta, registered, pending = raw_history(root)
        if meta != journal['new_meta'] or pending:
            raise EvolveError('RESTORE_INVALID', 'Installed history differs from the prepared new epoch', exit_code=4)
        protected_identity(root)
        for step in journal['steps']:
            if current_digest(inside(root, step['path'])) != step['after']:
                raise EvolveError('RESTORE_CHANGED', 'A target changed before maintenance finalization: ' + step['path'], exit_code=4)
        result = {'committed': True, 'outcome': {'restore': 'restored', 'upgrade': 'upgraded', 'repair': 'repaired'}[plan['method']],
            'project_id': meta['project_id'], 'workspace_epoch': meta['workspace_epoch'],
            'old_epoch': plan['old_epoch'], 'plan_id': plan['plan_id'], 'protection': str(folder / 'protection'),
            'quarantined_managed': plan['quarantined_managed'], 'external_pending': len(plan['external']['pending']),
            'external_coverage': plan['external'].get('coverage', 'unverified'),
            'business_data_restored': False, 'commands_replayed': False, 'checks_run': False}
        barrier = json.loads(barrier_path.read_text())
        barrier['result_digest'] = digest(canonical(result))
        durable_write(barrier_path, canonical(barrier))
        journal.update(state='completed', result=result)
        durable_write(journal_path, canonical(journal))
        fault_point('completed')
        durable_write(inside(root, '.evolve-local/control/maintenance.json'), canonical({
            **barrier, 'state': 'completed', 'new_epoch': meta['workspace_epoch']}))
        return result


def maintenance(root, payload, *, method):
    root, request = Path(root).resolve(), normalize(payload)
    require_effect(request, 'project_records')
    stage = request['input'].get('stage', 'plan')
    if stage == 'plan':
        folder = stage_path(root, request['request_id'])
        with writer_lock(root, recover_dead=True):
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'plan.json'
            request_path = folder / 'plan-request.json'
            if path.is_file():
                if json.loads(request_path.read_text()) != request:
                    raise EvolveError('REQUEST_CONFLICT', 'Maintenance plan retry changed its original request', exit_code=3)
                plan = json.loads(path.read_text())
            else:
                plan = prepare(root, request, method)
                if request_path.exists() and json.loads(request_path.read_text()) != request:
                    raise EvolveError('REQUEST_CONFLICT', 'Incomplete plan belongs to another request', exit_code=3)
                if not request_path.exists():
                    durable_write(request_path, canonical(request), new=True)
                durable_write(path, canonical(plan), new=True)
        return {'committed': True, 'outcome': 'maintenance_plan', 'plan': plan,
                'plan_digest': digest(canonical(plan)), 'business_data_restored': False}
    if stage != 'apply':
        raise EvolveError('INPUT', 'Maintenance stage must be plan or apply')
    folder = stage_path(root, request['input'].get('plan_id'))
    plan = json.loads((folder / 'plan.json').read_text())
    if request['input'].get('plan_digest') != digest(canonical(plan)) or plan['method'] != method:
        raise EvolveError('MAINTENANCE_APPROVAL', 'Apply must select the exact presented plan and method', exit_code=3)
    return apply_plan(root, request, plan, folder)


def restore(root, payload):
    return maintenance(root, payload, method='restore')


def upgrade(root, payload):
    return maintenance(root, payload, method='upgrade')


def repair(root, payload):
    return maintenance(root, payload, method='repair')
