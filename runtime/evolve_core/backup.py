"""One complete daily protection set before managed writes; epochs never overwrite."""
import json

from .archive_sets import collect_archive, require_archive_quiet, validate_archive
from .errors import EvolveError
from .package import digest
from .store import now
from .workspace import inside


def protect_before_write(store, request_id):
    require_archive_quiet(store)
    root = store.root
    initial = inside(root, '.evolve-local/control/init.json')
    if initial.exists() and json.loads(initial.read_text()).get('state') != 'committed':
        raise EvolveError('NEEDS_RECOVERY', 'Project initialization has not been finalized', exit_code=4)
    folder = inside(root, '.evolve-local/backups/' + now()[:10])
    manifest_path = folder / 'manifest.json'
    if manifest_path.is_file():
        manifest = validate_archive(folder, digest(manifest_path.read_bytes()))
        if manifest['project_id'] != store.meta['project_id']:
            raise EvolveError('BACKUP_CONFLICT', 'Existing daily protection belongs to another project', exit_code=4)
        if manifest['workspace_epoch'] != store.meta['workspace_epoch']:
            folder = folder.with_name(folder.name + '-' + store.meta['workspace_epoch'])
            manifest_path = folder / 'manifest.json'
        else:
            return manifest_path.relative_to(root).as_posix()
    if manifest_path.is_file():
        manifest = validate_archive(folder, digest(manifest_path.read_bytes()))
        if any(manifest[k] != store.meta[k] for k in ('project_id', 'workspace_epoch')):
            raise EvolveError('BACKUP_CONFLICT', 'Daily protection identity differs from current epoch', exit_code=4)
    else:
        collect_archive(store, folder, request_id)
    return manifest_path.relative_to(root).as_posix()
