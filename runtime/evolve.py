#!/usr/bin/env python3
"""Evolve deterministic entry point. Resolves resources from this installed file."""
import sys
sys.dont_write_bytecode = True
if sys.version_info < (3, 11):
    print('{"ok":false,"error":{"code":"PYTHON_VERSION","message":"Evolve requires Python 3.11+","next_steps":["Use Python 3.11 or newer"]}}')
    raise SystemExit(2)
try:
    from evolve_core.cli import main
except ImportError:
    print('{"ok":false,"error":{"code":"PACKAGE_INCOMPLETE","message":"Missing Evolve runtime; reinstall the complete package","next_steps":["Install the complete Evolve package"]}}')
    raise SystemExit(2)
raise SystemExit(main())
