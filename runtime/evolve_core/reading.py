"""Read a consistent temporary history snapshot without touching live SQLite sidecars."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import tomllib

from . import PROTOCOL_VERSION, SCHEMA_VERSION
from .errors import EvolveError
from .checks import pending_checks
from .workspace import current_digest, inside, request_staging_only
from .store import schema_compatible, validate_lineage
from .analysis import analysis_views


@contextmanager
def history_snapshot(root):
    root = Path(root).resolve()
    database = inside(root, 'evolve/history.db')
    if not database.is_file():
        raise EvolveError('NOT_CONNECTED', 'Explicit project connection is required')
    paths = [database, database.with_name(database.name + '-wal')]
    before = {p: p.read_bytes() for p in paths if p.exists()}
    with tempfile.TemporaryDirectory(prefix='evolve-read-') as directory:
        for path, content in before.items():
            (Path(directory) / path.name).write_bytes(content)
        connection = sqlite3.connect(str(Path(directory) / database.name))
        connection.row_factory = sqlite3.Row
        try:
            meta = dict(connection.execute('SELECT key,value FROM project_meta'))
            if int(meta['schema_version']) != SCHEMA_VERSION or int(meta.get('protocol_version', PROTOCOL_VERSION)) != PROTOCOL_VERSION:
                raise EvolveError('SCHEMA_VERSION', 'History schema or protocol is unsupported; no migration attempted')
            config = tomllib.loads(inside(root, 'evolve/config.toml').read_text())
            if config.get('config_version') != 1:
                raise EvolveError('CONFIG_VERSION', 'Configuration version is unsupported')
            if config.get('history') != {'backend': 'sqlite', 'database': 'evolve/history.db'}:
                raise EvolveError('CONFIG_PATH', 'History path/backend changed')
            if config.get('project', {}).get('id') != meta['project_id']:
                raise EvolveError('PROJECT_IDENTITY', 'Project configuration and history identities differ')
            guard = inside(root, '.evolve-local/control/guard.json')
            if guard.exists():
                value = json.loads(guard.read_text())
                validate_lineage(connection, meta, value)
            if before != {p: p.read_bytes() for p in paths if p.exists()}:
                raise EvolveError('PROJECT_CHANGED', 'History changed while preparing the observation', exit_code=3)
            yield connection, meta
            if before != {p: p.read_bytes() for p in paths if p.exists()}:
                raise EvolveError('PROJECT_CHANGED', 'History changed while reading; prepare a fresh observation', exit_code=3)
        except EvolveError:
            raise
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
            raise EvolveError('PROJECT_INVALID', 'Cannot inspect current project history: ' + str(error))
        finally:
            connection.close()


def current_state(root, target=None):
    root = Path(root).resolve()
    for name in ('evolve/config.toml', 'evolve/history.db', '.evolve-local'):
        inside(root, name)
    if not root.is_dir():
        raise EvolveError('PROJECT_ROOT', 'Project root must be an existing directory')
    barrier = inside(root, '.evolve-local/control/maintenance.json')
    if barrier.is_file():
        value = json.loads(barrier.read_text())
        if value.get('state') != 'completed':
            return {'state': 'maintenance', 'root': str(root), 'maintenance': value,
                    'write_compatible': False, 'changes': [], 'next_step': 'Resume the exact original maintenance apply request'}
    config, database = root / 'evolve/config.toml', root / 'evolve/history.db'
    if not config.exists() and not database.exists():
        if (root / 'evolve').exists() or ((root / '.evolve-local').exists() and not request_staging_only(root)):
            raise EvolveError('PROJECT_COLLISION', 'Evolve-named files require inspection; no changes made')
        return {'state': 'not_connected', 'root': str(root), 'project_id': None, 'changes': []}
    if not config.is_file() or not database.is_file():
        raise EvolveError('PROJECT_INCOMPLETE', 'Configuration and history must both exist; no recreation attempted')
    with history_snapshot(root) as (connection, meta):
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        changes = []
        if 'changes' in tables:
            for row in connection.execute('SELECT * FROM changes ORDER BY code'):
                if target and target not in (row['id'], row['code'], row['title']):
                    continue
                tasks = [dict(t) for t in connection.execute('SELECT * FROM tasks '
                                                            'WHERE change_id=? AND revision_id=?',
                                                            (row['id'], row['current_revision']))]
                if row['complexity'] == 'complex':
                    from .structured import readiness
                    observations = {task['id']: readiness(connection, root, task, tasks) for task in tasks}
                for task in tasks:
                    definition = task.pop('definition_json')
                    task.pop('result_json')
                    if row['complexity'] == 'complex':
                        task['local_key'] = json.loads(definition)['local_key']
                        task['task_code'] = json.loads(definition).get('task_code')
                        task['readiness'] = observations[task['id']]
                    if target:
                        task['definition'] = json.loads(definition)
                revision = connection.execute('SELECT * FROM plan_revisions WHERE id=?', (row['current_revision'],)).fetchone()
                details = {}
                if target and revision:
                    text = connection.execute('SELECT content FROM blobs WHERE digest=?', (revision['plan_digest'],)).fetchone()
                    details['plan'] = {'revision_id': revision['id'], 'digest': revision['plan_digest'],
                                       'text': text['content'].decode('utf-8') if text else None,
                                       'ordinal': revision['ordinal'], 'presented_at': revision['presented_at'], 'accepted': revision['accepted_event_id'] is not None}
                    if row['complexity'] == 'complex' and text:
                        details['plan']['document'] = json.loads(text['content'])
                    from .revisions import eligible_verifications, presentation, revision_source
                    presented, value = presentation(connection, revision['id'])
                    if value:
                        from .package import canonical, digest
                        details['plan'].update({'candidate': value['candidate'], 'candidate_digest': digest(canonical(value['candidate'])),
                            'requires_acceptance': value['requires_acceptance'],
                            'source_pending': revision_source(connection, presented['run_id']) is None})
                    observed = eligible_verifications(connection, row['id'], revision['id'])
                    latest = observed[0] if observed else None
                    details['latest_verification'] = ({'id': latest['id'], 'revision_id': latest['revision_id'], 'recorded_status': latest['status'],
                                                       'observed_at': latest['observed_at'], 'source_run_id': latest['source_run_id'],
                                                       'applicability': 'unconfirmed'} if latest else None)
                from .knowledge_impact import declared_impacts
                changes.append({**dict(row), 'tasks': tasks, 'knowledge_impact': declared_impacts(connection, row['current_revision']),
                                'definition_digest': revision['definition_digest'] if revision else None,
                                'plan_digest': revision['plan_digest'] if revision else None,
                                'details_loaded': bool(target), **details})
        analyses = analysis_views(connection, target, root=root) if 'phase_runs' in tables else []
        from .knowledge_proposals import proposal_views
        proposals = proposal_views(connection, root, target) if 'knowledge_proposals' in tables else []
        if changes and 'knowledge_proposals' in tables:
            related = proposals if not target else proposal_views(connection, root)
            for change in changes:
                change['knowledge_proposal_refs'] = [{key: item[key] for key in ('proposal_id', 'code', 'path', 'state', 'superseded_by')}
                    for item in related if item['associated_change_id'] == change['id']]
        if target and len(changes) + len(analyses) + len(proposals) != 1:
            raise EvolveError('TARGET', 'Target is missing or ambiguous; choose a stable work, analysis or knowledge proposal identity')
        pending_runs = [dict(r) for r in connection.execute("SELECT id,action,method,started_at,input_digest,execution_instance FROM phase_runs WHERE status='started'")] if 'phase_runs' in tables else []
        for run in pending_runs:
            run['execution_instance'] = json.loads(run['execution_instance'])
            run['operations'] = [dict(r) for r in connection.execute(
                'SELECT id,state,effect_kind FROM operations WHERE run_id=?', (run['id'],))] if 'operations' in tables else []
            run['pending_checks'] = pending_checks(connection, run['id']) if 'events' in tables else []
        knowledge_refs = []
        if {'artifacts', 'artifact_versions'}.issubset(tables):
            for item in connection.execute("SELECT a.path,v.id,v.blob_digest,v.source_run_id,v.observed_at FROM artifacts a "
                                            "JOIN artifact_versions v ON v.id=a.current_version WHERE a.kind='knowledge' AND a.path IS NOT NULL ORDER BY a.path"):
                observed = current_digest(inside(root, item['path']))
                knowledge_refs.append({'path': item['path'], 'artifact_version_id': item['id'],
                                       'registered_digest': item['blob_digest'], 'source_run_id': item['source_run_id'],
                                       'registered_at': item['observed_at'], 'observed_digest': observed,
                                       'confirmation': 'approved_version' if observed == item['blob_digest'] else 'unconfirmed'})
                if 'rule_bindings' in tables:
                    from .rules import rule_views
                    knowledge_refs[-1]['rule_bindings'] = rule_views(connection, root, item['path'])
        pending_knowledge = [dict(r) for r in connection.execute("SELECT id,target_path,state,version,candidate_digest FROM knowledge_proposals "
                                                               "WHERE state IN ('proposed','approved','deferred') AND applied_operation_id IS NULL ORDER BY id")] if 'knowledge_proposals' in tables else []
        init_journal = inside(root, '.evolve-local/control/init.json')
        initialization = json.loads(init_journal.read_text()).get('state') if init_journal.is_file() else 'unregistered'
        from .project_knowledge import catalog_view
        return {'state': 'connected', 'root': str(root), 'knowledge': catalog_view(connection, root), 'project_id': meta['project_id'],
                'workspace_epoch': meta.get('workspace_epoch'), 'schema_version': int(meta['schema_version']),
                'checkpoint': meta.get('checkpoint'), 'changes': changes, 'analyses': analyses, 'pending_runs': pending_runs,
                'knowledge_refs': knowledge_refs, 'pending_knowledge': pending_knowledge, 'knowledge_proposals': proposals,
                'write_compatible': schema_compatible(connection), 'initialization': initialization}
