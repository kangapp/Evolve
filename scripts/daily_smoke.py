#!/usr/bin/env python3
"""Replay four composed daily cases through an independent public CLI; no models."""
import argparse
import json
from pathlib import Path
from multiple_work_smoke import run

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.package, args.out, daily_cycle=True), ensure_ascii=False, indent=2))
