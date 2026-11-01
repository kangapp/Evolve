#!/usr/bin/env python3
"""Bounded IMP-013 actual external effects under the human's unified authorization."""
from model_data_acceptance import main
from model_external_checks import scope_for, ExternalChecks, PROMPTS

if __name__ == '__main__':
    main(scope_factory=scope_for, checker_type=ExternalChecks, prompts=PROMPTS, description=__doc__)
