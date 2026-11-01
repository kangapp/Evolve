#!/usr/bin/env python3
"""Build a closed, versioned local distribution using only the standard library."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from evolve_core import VERSION, PROTOCOL_VERSION, SCHEMA_VERSION, DESIGN_BASELINE
from evolve_core.package import AVAILABLE, canonical, digest, check_package

STATIC = ['README.md', 'LICENSE', 'NOTICE.md', 'CHANGELOG.md',
          '.codex-plugin/plugin.json', '.claude-plugin/plugin.json',
          '.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json',
          'docs/installation.md', 'docs/usage.md', 'docs/troubleshooting.md', 'docs/development.md', 'docs/compatibility.md', 'docs/project-layout.md']


def sources():
    files = list(STATIC)
    for pattern in ('runtime/**/*.py', 'skills/**/SKILL.md', 'shared/**/*.md', 'assets/templates/*'):
        files.extend(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file())
    return sorted(set(files))


def rendered(name):
    path = ROOT / name
    if path.is_symlink():
        raise ValueError('Refuse linked source: ' + name)
    data = path.read_bytes()
    if path.suffix == '.md':
        text = re.sub(r'<!-- source-only -->.*?<!-- /source-only -->', '', data.decode('utf-8'), flags=re.S)
        return text.encode('utf-8')
    return data



def validate_python(contents):
    for name, body in contents.items():
        if name.endswith('.py'):
            try:
                compile(body, name, 'exec', dont_inherit=True)
            except SyntaxError as error:
                raise ValueError(f'Invalid Python resource {name}:{error.lineno}: {error.msg}') from error


def inventory(contents):
    files = {name: digest(data) for name, data in sorted(contents.items())}
    return {'name': 'evolve', 'package_version': VERSION, 'design_baseline': DESIGN_BASELINE,
            'protocol_version': PROTOCOL_VERSION, 'schema_version': SCHEMA_VERSION,
            'stage': 'IMP-014-local-private-first-version', 'python_requires': '>=3.11',
            'available_methods': sorted(AVAILABLE), 'files': files, 'content_digest': digest(canonical(files))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='New independent package directory (must not exist)')
    parser.add_argument('--check', action='store_true', help='Check source inventory without modifying it')
    args = parser.parse_args()
    if args.check and args.out:
        parser.error('--check and --out cannot be combined')
    if args.check:
        try:
            validate_python({name: (ROOT / name).read_bytes() for name in sources()})
        except ValueError as error:
            parser.error(str(error))
        package = check_package()
        expected = {name: digest((ROOT / name).read_bytes()) for name in sources()}
        if package['files'] != expected:
            parser.error('Source inventory is stale; run build_package.py without options')
        print(json.dumps({'ok': True, 'version': VERSION, 'files': len(expected), 'digest': package['content_digest']}))
        return
    contents = {name: (rendered(name) if args.out else (ROOT / name).read_bytes()) for name in sources()}
    try:
        validate_python(contents)
    except ValueError as error:
        parser.error(str(error))
    package = inventory(contents)
    data = json.dumps(package, ensure_ascii=False, indent=2).encode('utf-8') + b'\n'
    if args.out:
        target = args.out.absolute()
        if target.exists() or target.is_symlink():
            parser.error('Output already exists; refusing to overwrite: ' + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.evolve-build-', dir=target.parent))
        try:
            for name, body in contents.items():
                path = staging / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            (staging / 'evolve-package.json').write_bytes(data)
            check_package(staging)
            staging.rename(target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    else:
        (ROOT / 'evolve-package.json').write_bytes(data)
    print(json.dumps({'ok': True, 'version': VERSION, 'files': len(contents), 'digest': package['content_digest']}))


if __name__ == '__main__':
    main()
