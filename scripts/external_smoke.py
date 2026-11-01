#!/usr/bin/env python3
"""Run controlled IMP-013 actual public CLI effects; never calls a model."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    lab = args.out.resolve()
    lab.mkdir(parents=True, exist_ok=False)
    child = subprocess.run([sys.executable, '-B', str(ROOT / 'tests/external_acceptance_driver.py'),
        str(args.package.resolve()), str(ROOT), str(lab), str(lab / 'public-evidence')], capture_output=True, text=True, timeout=100)
    (lab / 'execution.json').write_text(json.dumps({'exit_code': child.returncode, 'stdout': child.stdout, 'stderr': child.stderr}, ensure_ascii=False, indent=2))
    if child.returncode:
        raise SystemExit(child.stderr + child.stdout[-4000:])
    print(child.stdout.strip())
