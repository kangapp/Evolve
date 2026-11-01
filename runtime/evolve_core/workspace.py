"""Local file commit primitives: journals preserve candidates and third-party edits."""
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import socket
import tempfile
import uuid

from .errors import EvolveError
from .package import canonical, digest
from .privacy import ensure_recordable


def inside(root, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise EvolveError('PATH', 'Use a nonempty project-relative POSIX path')
    relative = PurePosixPath(name)
    if relative.is_absolute() or PureWindowsPath(name).drive or '..' in relative.parts:
        raise EvolveError('PATH', 'Path must remain within the selected project: ' + name)
    path = Path(root) / name
    try:
        path.resolve().relative_to(Path(root).resolve())
    except ValueError:
        raise EvolveError('PATH', 'Path escapes the selected project: ' + name)
    return path


def current_digest(path):
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise EvolveError('FILE_TYPE', 'Expected a regular file: ' + str(path))
    return digest(path.read_bytes())


def read_control(path):
    try:
        value = json.loads(Path(path).read_text())
        if not isinstance(value, dict):
            raise ValueError('Expected a control object')
        return value
    except (OSError, ValueError, TypeError) as error:
        raise EvolveError('PROTECTION_UNKNOWN', 'Cannot read control object: ' + str(path) + ': ' + str(error), exit_code=4) from error


def durable_write(path, content, *, new=False):
    """Atomic single-file installation; new=True never replaces an existing path."""
    ensure_recordable(content)
    path = Path(path)
    if path.is_symlink():
        raise EvolveError('FILE_TYPE', 'Refusing to replace a symbolic link: ' + str(path))
    mode = path.stat().st_mode & 0o777 if path.is_file() else 0o600
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.evolve-write-', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            if hasattr(os, 'fchmod'):
                os.fchmod(stream.fileno(), mode)
            else:
                os.chmod(temporary, mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if new:
            try:
                os.link(temporary, path)
            except FileExistsError:
                raise EvolveError('FILE_CONFLICT', 'File appeared while installing: ' + str(path), exit_code=3)
        else:
            os.replace(temporary, path)
        if os.name != 'nt':
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def process_alive(pid):
    if type(pid) is not int or pid <= 0:
        raise EvolveError('WRITER_UNKNOWN', 'Writer process identity is invalid', exit_code=3)
    if os.name == 'nt':
        # os.kill(pid, 0) is not a safe liveness probe on Windows.
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return False
            raise EvolveError('WRITER_UNKNOWN', 'Cannot inspect the existing Windows writer', exit_code=3)
        try:
            state = kernel.WaitForSingleObject(handle, 0)
            if state in (0, 258):
                return state == 258
            raise EvolveError('WRITER_UNKNOWN', 'Cannot determine writer process state', exit_code=3)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        raise EvolveError('WRITER_UNKNOWN', 'Cannot inspect existing writer process', exit_code=3)


@contextmanager
def writer_lock(root, *, recover_dead=False, maintenance_token=None):
    """Short local writer lock. Age is never proof that a writer is dead."""
    control = inside(root, '.evolve-local/control')
    control.mkdir(parents=True, exist_ok=True)
    path = control / 'writer.lock'
    identity = {'pid': os.getpid(), 'host': socket.gethostname(), 'generation': str(uuid.uuid4())}
    if recover_dead and path.exists():
        try:
            previous = json.loads(path.read_text())
            if previous['host'] != identity['host']:
                raise EvolveError('WRITER_UNKNOWN', 'Cannot verify a writer on another host', exit_code=3)
            if not process_alive(previous['pid']):
                path.unlink()
            else:
                raise EvolveError('WRITER_ACTIVE', 'Existing writer is still alive; recovery refused', exit_code=3)
        except (ValueError, KeyError, TypeError):
            raise EvolveError('WRITER_UNKNOWN', 'Cannot interpret existing writer lock', exit_code=3)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise EvolveError('WRITER_ACTIVE', 'Another local write needs completion or recovery', exit_code=3)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(identity))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        from .protection import require_admission
        require_admission(root, maintenance_token)
        yield identity
    finally:
        if path.exists() and json.loads(path.read_text()) == identity:
            path.unlink()


def prepare_files(root, operation_id, candidates):
    """Persist old bytes, candidate bytes, and their exact preconditions."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', operation_id):
        raise EvolveError('OPERATION_ID', 'Invalid internal operation identity')
    entries = []
    seen = set()
    for item in candidates:
        path = inside(root, item['path'])
        if str(path.resolve()) in seen:
            raise EvolveError('FILE_CONFLICT', 'Duplicate file target: ' + item['path'], exit_code=3)
        seen.add(str(path.resolve()))
        before = path.read_bytes() if path.exists() else None
        ensure_recordable(before)
        expected = item['expected_digest']
        if (digest(before) if before is not None else None) != expected or current_digest(path) != expected:
            raise EvolveError('FILE_CONFLICT', 'File differs from the accepted baseline: ' + item['path'], exit_code=3)
        content = item['content'].encode('utf-8')
        ensure_recordable(content)
        entries.append({'path': item['path'], 'expected_digest': expected,
                        'original_b64': base64.b64encode(before).decode() if before is not None else None,
                        'candidate_b64': base64.b64encode(content).decode(), 'candidate_digest': digest(content)})
    journal = {'operation_id': operation_id, 'state': 'prepared', 'files': entries}
    path = inside(root, '.evolve-local/control/operations/' + operation_id + '.json')
    durable_write(path, canonical(journal), new=True)
    return journal


def install_files(root, journal, *, before_write=None):
    """Resume only old/candidate states. A third value is preserved as a conflict."""
    for item in journal['files']:
        path = inside(root, item['path'])
        observed = current_digest(path)
        if observed == item['candidate_digest']:
            continue
        if observed != item['expected_digest']:
            raise EvolveError('NEEDS_RECOVERY', 'Third-party file value preserved: ' + item['path'],
                              exit_code=4, next_steps=['Inspect the journal and current file before recovery'])
        content = base64.b64decode(item['candidate_b64'], validate=True)
        if digest(content) != item['candidate_digest']:
            raise EvolveError('JOURNAL_INVALID', 'Candidate digest does not match journal', exit_code=4)
        if before_write is not None:
            before_write()
        if current_digest(path) != observed:
            raise EvolveError('NEEDS_RECOVERY', 'File changed immediately before replacement: ' + item['path'], exit_code=4)
        durable_write(path, content, new=observed is None)
    for item in journal['files']:
        if current_digest(inside(root, item['path'])) != item['candidate_digest']:
            raise EvolveError('NEEDS_RECOVERY', 'File changed before finalization: ' + item['path'], exit_code=4)


def finish_journal(root, journal):
    path = inside(root, '.evolve-local/control/operations/' + journal['operation_id'] + '.json')
    durable_write(path, canonical({**journal, 'state': 'committed'}))


def request_staging_only(root):
    """Recognize host input staging before init without adopting other records."""
    local = Path(root) / '.evolve-local'
    if not local.is_dir() or local.is_symlink() or local.resolve() != local.absolute():
        return False
    required = {'control', 'control/requests'}
    inputs = 0
    for path in local.rglob('*'):
        name = path.relative_to(local).as_posix()
        if path.is_symlink() or path.resolve() != path.absolute():
            return False
        if path.is_dir():
            if name not in required:
                return False
        elif path.is_file() and path.parent == local / 'control/requests' and path.suffix == '.json':
            inputs += 1
        else:
            return False
    return inputs > 0

