"""Edit only supported single-line TOML values, retaining unrelated bytes/comments."""
import copy
import json
import re
import tomllib

from .errors import EvolveError


def encoded_check(check):
    return {'id': check['id'], 'argv': check['argv'], 'cwd': check.get('cwd', '.'), 'timeout': check.get('timeout', 60)}


def set_value(lines, start, end, key, value):
    matches = [i for i in range(start, end) if re.match(r'^\s*' + re.escape(key) + r'\s*=', lines[i])]
    if len(matches) > 1:
        raise EvolveError('CONFIG_UNSUPPORTED', 'Ambiguous TOML field location: ' + key)
    text = json.dumps(value, ensure_ascii=False)
    if not matches:
        newline = '\r\n' if any(line.endswith('\r\n') for line in lines) else '\n'
        prefix = lines[:end]
        if prefix and not prefix[-1].endswith(('\n', '\r')):
            prefix[-1] += newline
        return prefix + [key + ' = ' + text + newline] + lines[end:]
    i = matches[0]
    match = re.match(r'^(\s*' + re.escape(key) + r'\s*=\s*)(.*)$', lines[i], re.S)
    try:
        _, consumed = json.JSONDecoder().raw_decode(match.group(2))
    except ValueError:
        raise EvolveError('CONFIG_UNSUPPORTED', 'Existing field uses unsupported multiline/literal TOML: ' + key)
    suffix = match.group(2)[consumed:]
    if suffix.strip() and not suffix.lstrip().startswith('#'):
        raise EvolveError('CONFIG_UNSUPPORTED', 'Cannot isolate the existing TOML value: ' + key)
    return lines[:i] + [match.group(1) + text + suffix] + lines[i + 1:]


def edit_configuration(original, data):
    before = tomllib.loads(original.decode('utf-8'))
    expected = copy.deepcopy(before)
    text = original.decode('utf-8')
    if 'name' in data and data['name'] != before['project'].get('name'):
        lines = text.splitlines(keepends=True)
        starts = [i for i, line in enumerate(lines) if re.match(r'^\[project\]\s*(?:#.*)?$', line.strip())]
        if len(starts) != 1:
            raise EvolveError('CONFIG_UNSUPPORTED', 'Cannot uniquely locate project table without rewriting configuration')
        start = starts[0] + 1
        end = next((i for i in range(start, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
        text = ''.join(set_value(lines, start, end, 'name', data['name']))
        expected['project']['name'] = data['name']
    current = before.get('verification', {}).get('checks', [])
    if not isinstance(current, list):
        raise EvolveError('CONFIG_UNSUPPORTED', 'Unsupported existing verification check structure')
    for raw in data.get('checks', []):
        candidate = encoded_check(raw)
        old = next((c for c in current if c['id'] == candidate['id']), None)
        if old == candidate:
            continue
        if old is not None:
            if set(old) - set(candidate):
                raise EvolveError('CONFIG_UNSUPPORTED', 'Unknown check fields must be preserved, not reinterpreted')
            for key, value in candidate.items():
                if old.get(key) == value:
                    continue
                lines = text.splitlines(keepends=True)
                tables = [i for i, line in enumerate(lines) if re.match(r'^\[\[verification\.checks\]\]\s*(?:#.*)?$', line.strip())]
                selected = []
                for start in tables:
                    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
                    parsed = tomllib.loads(''.join(lines[start:end]))['verification']['checks'][0]
                    if parsed['id'] == candidate['id']:
                        selected.append((start + 1, end))
                if len(selected) != 1:
                    raise EvolveError('CONFIG_UNSUPPORTED', 'Cannot isolate requested check without rewriting other content')
                text = ''.join(set_value(lines, *selected[0], key, value))
            index = next(i for i, c in enumerate(expected['verification']['checks']) if c['id'] == candidate['id'])
            expected['verification']['checks'][index] = candidate
        else:
            newline = '\r\n' if '\r\n' in text else '\n'
            text += ('' if text.endswith(('\n', '\r')) else newline) + newline + '[[verification.checks]]' + newline
            text += ''.join(key + ' = ' + json.dumps(value, ensure_ascii=False) + newline for key, value in candidate.items())
            expected.setdefault('verification', {}).setdefault('checks', []).append(candidate)
    if tomllib.loads(text) != expected:
        raise EvolveError('CONFIG_UNSUPPORTED', 'Configuration round-trip changed unrelated meaning')
    return text.encode('utf-8')
