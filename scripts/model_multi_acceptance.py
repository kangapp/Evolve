#!/usr/bin/env python3
"""Prepare or explicitly dispatch seven bounded Codex IMP-009 conversations."""
import sys

sys.dont_write_bytecode = True
from model_data_acceptance import main
from model_multi_checks import PROMPTS, MultiChecks, scope_for


if __name__ == '__main__':
    main(scope_factory=scope_for, checker_type=MultiChecks, prompts=PROMPTS, description=__doc__)
