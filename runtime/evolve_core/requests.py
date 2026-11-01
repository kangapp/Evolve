"""Validate explicit requests supplied by the host adapter, not inferred authority."""
import copy
import re

from .errors import EvolveError
from .store import identifier
from .privacy import ensure_recordable


def normalize(payload):
    if not isinstance(payload, dict):
        raise EvolveError('INPUT', 'Request must be a JSON object')
    result = copy.deepcopy(payload)
    ensure_recordable(result)
    result.setdefault('request_id', identifier())
    if not isinstance(result['request_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', result['request_id']):
        raise EvolveError('INPUT', 'Invalid internal request identity')
    if not isinstance(result.get('input'), dict):
        raise EvolveError('INPUT', 'Request input must be an object')
    authorization = result.get('authorization')
    if not isinstance(authorization, dict):
        raise EvolveError('AUTHORIZATION', 'Explicit authorization source is required')
    if not isinstance(authorization.get('source'), str) or not authorization['source'].strip():
        raise EvolveError('AUTHORIZATION', 'Authorization must identify its actual source')
    if not isinstance(authorization.get('text'), str) or not authorization['text'].strip():
        raise EvolveError('AUTHORIZATION', 'Authorization must preserve the actual user instruction')
    effects = authorization.get('effect_kinds')
    if not isinstance(effects, list) or not effects or any(not isinstance(x, str) for x in effects):
        raise EvolveError('AUTHORIZATION', 'Authorization must state permitted effect kinds')
    paths = authorization.get('paths', [])
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise EvolveError('AUTHORIZATION', 'Authorized paths must be a string array')
    versions = result.get('expected_versions')
    if versions is not None:
        if not isinstance(versions, dict):
            raise EvolveError('INPUT', 'Expected versions must be an object')
        for key, value in versions.items():
            if key == 'tasks':
                valid = (isinstance(value, dict) and bool(value) and all(isinstance(task_id, str) and task_id
                         and type(version) is int and version > 0 for task_id, version in value.items()))
            else:
                valid = type(value) is int and value > 0
            if not valid:
                raise EvolveError('INPUT', 'Expected entity versions must be positive integers; tasks is an explicit identity/version map')
    return result


def require_effect(request, effect):
    if effect not in request['authorization']['effect_kinds']:
        raise EvolveError('AUTHORIZATION', 'Request does not authorize ' + effect)
