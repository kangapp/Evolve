#!/usr/bin/env python3
"""Bounded same-project IMP-011 Codex acceptance; exact actual human scope required."""
from model_data_acceptance import main
from model_daily_checks import scope_for, DailyChecks, PROMPTS

if __name__ == '__main__':
    main(scope_factory=scope_for, checker_type=DailyChecks, prompts=PROMPTS, description=__doc__)
