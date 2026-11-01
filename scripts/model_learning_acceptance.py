#!/usr/bin/env python3
"""Prepare a bounded IMP-010 Codex learning cycle; exact new human scope required."""
from model_data_acceptance import main
from model_learning_checks import scope_for, LearningChecks, PROMPTS

if __name__ == '__main__':
    main(scope_factory=scope_for, checker_type=LearningChecks, prompts=PROMPTS, description=__doc__)
