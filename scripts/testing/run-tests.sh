#!/bin/bash -e

export PYTHONPATH="${PYTHONPATH}:${PANDIR}/POCS/scripts/coverage"
export COVERAGE_PROCESS_START="${PANDIR}/POCS/.coveragerc"

# Run coverage over the pytest suite
coverage run "$(command -v pytest)" -x -vv -rfes --test-databases all
coverage combine

exit 0
