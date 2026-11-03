"""Execute previously approved argv checks without holding database transactions."""
import os
import json
import signal
import socket
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone

from .errors import EvolveError
from .workspace import inside, process_alive
from .package import canonical, digest
from .privacy import redact


def group_alive(pid):
    if os.name == 'nt':
        return process_alive(pid)
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def pending_checks(connection, run_id):
    attempts = {}
    for row in connection.execute("SELECT kind,payload_json,recorded_at FROM events WHERE "
                                  "(run_id=? AND kind LIKE 'check_%') OR kind='check_execution_observed' ORDER BY rowid", (run_id,)):
        payload = json.loads(row['payload_json'])
        if row['kind'] == 'check_execution_observed':
            observation = payload['observation']
            attempt = attempts.get(observation['execution_id'])
            if (payload['original_run_id'] == run_id and attempt
                    and all(observation.get(k) == attempt[k] for k in ('command_digest', 'host'))):
                attempts.pop(observation['execution_id'])
            continue
        key = payload.get('execution_id')
        if key is None:
            continue
        if row['kind'] == 'check_dispatch_prepared':
            attempts[key] = {**payload, 'prepared_at': row['recorded_at']}
        elif row['kind'] == 'check_process_started' and key in attempts:
            attempts[key].update(payload)
        elif row['kind'] in ('check_process_finished', 'check_dispatch_aborted'):
            attempts.pop(key, None)
    unresolved = []
    for attempt in attempts.values():
        if 'pid' not in attempt:
            unresolved.append({**attempt, 'state': 'launch_unknown'})
        elif attempt['host'] != socket.gethostname():
            unresolved.append({**attempt, 'state': 'foreign_host'})
        elif group_alive(attempt['pid']):
            unresolved.append({**attempt, 'state': 'process_group_present'})
    return unresolved


def validate_stop_observations(pending, observations):
    if any(item['state'] == 'process_group_present' for item in pending):
        raise EvolveError('CHECK_RUNNING', 'An observed process group is still present; retain its resource ownership', exit_code=4, committed=True)
    if not isinstance(observations, list) or any(not isinstance(item, dict) for item in observations):
        raise EvolveError('CHECK_OBSERVATION', 'Check observations must be an explicit array')
    if pending and not observations:
        raise EvolveError('CHECK_EXECUTION_UNKNOWN', 'Check execution requires specific stopping evidence before recovery', exit_code=4, committed=True)
    by_id = {item['execution_id']: item for item in pending}
    if len(observations) != len(by_id) or {item.get('execution_id') for item in observations if isinstance(item.get('execution_id'), str)} != set(by_id):
        raise EvolveError('CHECK_OBSERVATION', 'Observe each unresolved execution exactly once using its saved identity')
    for item in observations:
        attempt = by_id[item['execution_id']]
        if (any(item.get(k) != attempt[k] for k in ('command_digest', 'host'))
                or item.get('outcome') not in ('not_started', 'stopped')
                or ('pid' in attempt and item['outcome'] == 'not_started')
                or any(not isinstance(item.get(k), str) or not item[k].strip() for k in ('source', 'basis', 'observed_at'))):
            raise EvolveError('CHECK_OBSERVATION', 'Stopping evidence must bind the command, host, outcome, source and actual basis')
        try:
            observed = datetime.fromisoformat(item['observed_at'])
            prepared = datetime.fromisoformat(attempt['prepared_at'])
            if observed.tzinfo is None or not prepared <= observed <= datetime.now(timezone.utc):
                raise ValueError('Observation is not within the actual execution window')
        except (ValueError, TypeError):
            raise EvolveError('CHECK_OBSERVATION', 'Observation time must follow dispatch intent and cannot be in the future')
    return observations


def run_check(root, check, *, event_sink=None):
    start = time.monotonic()
    status, code = 'blocked', None
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    execution_id = str(uuid.uuid4())
    metadata = {'execution_id': execution_id, 'check_id': check['id'],
                'command_digest': digest(canonical(check)), 'host': socket.gethostname()}
    from .check_environment import observe
    observed_environment = observe(root, check)
    metadata['environment_digest'] = observed_environment['digest']
    if event_sink:
        event_sink('check_dispatch_prepared', metadata)
    unfinished = False
    with tempfile.TemporaryFile() as output:
        process = None
        try:
            if observed_environment['status'] != 'ready':
                raise OSError('Required environment is unavailable: ' + json.dumps(observed_environment['missing']))
            process = subprocess.Popen(check['argv'], cwd=inside(root, check.get('cwd', '.')),
                                       env=environment, stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
            if event_sink:
                event_sink('check_process_started', {**metadata, 'pid': process.pid})
            try:
                code = process.wait(timeout=check.get('timeout', 60))
                status = 'passed' if code == 0 else 'failed'
            except subprocess.TimeoutExpired:
                if os.name != 'nt':
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                process.wait()
                status = 'blocked'
                output.write(b'\n[Evolve: check timed out; no passing result recorded]\n')
            unfinished = group_alive(process.pid)
            if unfinished:
                status = 'blocked'
                output.write(b'\n[Evolve: descendants may still be executing; resource ownership retained]\n')
            elif event_sink:
                event_sink('check_process_finished', {**metadata, 'pid': process.pid, 'returncode': code, 'status': status})
        except OSError as error:
            output.write(str(error).encode())
            if process is None and event_sink:
                event_sink('check_dispatch_aborted', metadata)
        except BaseException:
            if process is not None and process.poll() is None:
                if os.name != 'nt':
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                process.wait()
            raise
        size = output.tell()
        output.seek(max(0, size - 65536))
        text = redact(output.read().decode('utf-8', errors='replace'))
    return {'check_id': check['id'], 'status': status, 'returncode': code,
            'argv': [redact(arg) for arg in check['argv']], 'cwd': check.get('cwd', '.'),
            'elapsed_seconds': round(time.monotonic() - start, 6),
            'output': text, 'output_truncated': size > 65536,
            'execution_id': execution_id, 'unfinished_processes': unfinished,
            'environment': observed_environment}
