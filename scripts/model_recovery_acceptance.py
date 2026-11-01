#!/usr/bin/env python3
"""Bounded IMP-012 archive recovery acceptance under actual uniform authorization."""
from model_data_acceptance import main
from model_recovery_checks import scope_for, RecoveryChecks, PROMPTS

if __name__ == '__main__':
    main(scope_factory=scope_for, checker_type=RecoveryChecks, prompts=PROMPTS, description=__doc__)
