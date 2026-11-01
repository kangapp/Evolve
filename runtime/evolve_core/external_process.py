"""Observe an owned external sender; command status never substitutes for data effects."""
import json
import os
import signal
import subprocess

from .checks import group_alive
from .errors import EvolveError
from .privacy import ensure_recordable, redact

OUTPUT_BYTES = 65536


def finish_process(process, output, timeout):
    """Caller launched this POSIX process in its own session and saved its PID first."""
    if os.name != 'posix' or not hasattr(os, 'pread'):
        raise EvolveError('EXTERNAL_UNSUPPORTED', 'This environment cannot safely observe this owned sender process group')
    timed_out = False
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            if os.getpgid(process.pid) != process.pid:
                raise EvolveError('EXTERNAL_PROCESS_CONTEXT', 'Refusing to signal an unowned process group', exit_code=4)
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        code = process.wait()
    present = group_alive(process.pid)
    size = os.fstat(output.fileno()).st_size
    # Positional reads do not move the shared stdout offset if descendants remain.
    encoded = os.pread(output.fileno(), OUTPUT_BYTES, max(0, size - OUTPUT_BYTES))
    sanitized = redact(encoded.decode('utf-8', errors='replace'))
    return {'returncode': code, 'timed_out': timed_out, 'process_group_present': present,
            'output': sanitized[-OUTPUT_BYTES:],
            'output_truncated': size > OUTPUT_BYTES or len(sanitized) > OUTPUT_BYTES, 'output_bytes_observed': size,
            'command_exit_is_business_success': False}


def receipt(observation, operation_id, provider_identity):
    """A transport receipt only selects the subsequent independent target probe."""
    if (observation['returncode'] != 0 or observation['timed_out'] or observation['process_group_present']):
        return None
    lines = observation['output'].strip().splitlines()
    try:
        value = json.loads(lines[-1]) if lines else None
        if (not isinstance(value, dict) or value.get('operation_id') != operation_id
                or value.get('target_identity') != provider_identity
                or not isinstance(value.get('provider_operation_ref'), str) or not value['provider_operation_ref']):
            return None
        ensure_recordable(value)
        return {'operation_id': operation_id, 'target_identity': provider_identity,
                'provider_operation_ref': value['provider_operation_ref']}
    except (ValueError, TypeError, EvolveError):
        return None
