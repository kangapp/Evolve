"""Observe declared check inputs without launching tools or retaining environment values."""
import os
from pathlib import Path
import re
import shutil
import sys

from .errors import EvolveError
from .package import canonical, digest
from .privacy import redact
from .workspace import current_digest, inside


FIELDS = ('environment_tools', 'environment_files', 'environment_variables')


def validate(check):
    if any(type(check.get(field, False)) is not bool for field in ('preflight', 'reuse')):
        raise EvolveError('INPUT', 'Check preflight and reuse must be boolean')
    for field in FIELDS:
        names = check.get(field, [])
        if (not isinstance(names, list) or any(not isinstance(name, str) or not name or '\x00' in name for name in names)
                or len(names) != len(set(names))):
            raise EvolveError('INPUT', field + ' must list distinct nonempty names')
    for name in check.get('environment_variables', []):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name) or re.search(r'TOKEN|PASSWORD|SECRET|API_KEY', name, re.I):
            raise EvolveError('INPUT', 'Environment observations accept explicit non-credential variable names')
    for name in check.get('environment_files', []):
        if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name:
            raise EvolveError('INPUT', 'Environment files must be project-relative')


def tool(cwd, name):
    selected = str(cwd / name) if '/' in name and not Path(name).is_absolute() else name
    search = os.pathsep.join(str(cwd / part) if not Path(part).is_absolute() else part
                            for part in os.environ.get('PATH', os.defpath).split(os.pathsep))
    found = shutil.which(selected, path=search)
    if not found:
        return {'requested': redact(name), 'status': 'missing'}
    path = Path(found).absolute()
    resolved = path.resolve()
    try:
        content_digest = current_digest(resolved)
    except OSError:
        return {'requested': redact(name), 'status': 'unreadable'}
    result = {'requested': redact(name), 'status': 'ready', 'selected_path': redact(str(path)),
              'resolved_path': redact(str(resolved)), 'digest': content_digest,
              'version': sys.version.split()[0] if resolved == Path(sys.executable).resolve() else 'not_observed'}
    # Virtual environments can share the same binary while using different packages.
    config = path.parent.parent / 'pyvenv.cfg'
    if config.is_file():
        result['virtual_environment_digest'] = current_digest(config)
    return result


def observe(root, check):
    validate(check)
    cwd = inside(root, check.get('cwd', '.'))
    tools = [tool(cwd, name) for name in dict.fromkeys([check['argv'][0], *check.get('environment_tools', [])])]
    files = {name: current_digest(inside(root, name)) for name in check.get('environment_files', [])}
    variables = {name: {'present': bool(os.environ.get(name)),
        'digest': digest(os.environ[name].encode()) if os.environ.get(name) else None}
        for name in check.get('environment_variables', [])}
    missing = ([{'kind': 'working_directory', 'name': check.get('cwd', '.')}] if not cwd.is_dir() else [])
    missing += [{'kind': 'executable', 'name': item['requested']} for item in tools if item['status'] != 'ready']
    missing += [{'kind': 'file', 'name': name} for name, value in files.items() if value is None]
    missing += [{'kind': 'variable', 'name': name} for name, value in variables.items() if not value['present']]
    basis = {'tools': tools, 'files': files, 'variables': variables, 'cwd': check.get('cwd', '.'),
             'python_bytecode': 'disabled', 'version_probes': 'not_executed'}
    return {**basis, 'check_id': check['id'], 'status': 'blocked' if missing else 'ready',
            'missing': missing, 'digest': digest(canonical(basis))}


def require(root, checks):
    observations = [observe(root, check) for check in checks]
    if any(item['status'] != 'ready' for item in observations):
        raise EvolveError('CHECK_ENVIRONMENT', 'Required check environment is unavailable; inspect the actual executable and declared prerequisites before writing files',
                         exit_code=3, details={'environments': observations})
    return observations
