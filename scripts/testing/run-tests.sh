#!/bin/bash -e

export PYTHONPATH="${PYTHONPATH}:${PANDIR}/POCS/scripts/coverage"
export COVERAGE_PROCESS_START="${PANDIR}/POCS/.coveragerc"

# Run coverage over the pytest suite
echo "Staring tests"
coverage run "$(command -v pytest)" -x -vv -rfes --test-databases all

echo "Combining coverage"
coverage combine

echo "Making XML coverage report"
coverage xml

exit 0
