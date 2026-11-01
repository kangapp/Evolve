"""Keep known environment credentials out of durable inputs, artifacts, and logs."""
import os
import re

from .errors import EvolveError


def known_credentials():
    return [value for key, value in os.environ.items() if len(value) >= 8
            and re.search(r'(TOKEN|PASSWORD|SECRET|API_KEY)', key, re.I)]


def ensure_recordable(value):
    if isinstance(value, dict):
        for key, item in value.items():
            ensure_recordable(key)
            ensure_recordable(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            ensure_recordable(item)
    else:
        text = value.decode('utf-8', errors='ignore') if isinstance(value, bytes) else value if isinstance(value, str) else ''
        if any(secret in text for secret in known_credentials()):
            raise EvolveError('CREDENTIAL_CONTENT', 'Known credentials cannot be stored in workflow records; use environment references')


def redact(text):
    for value in known_credentials():
        text = text.replace(value, '[REDACTED]')
    return text
