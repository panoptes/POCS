#!/bin/bash -e

REPORT_FILE=${REPORT_FILE:-coverage.xml}

export PYTHONPATH="$PYTHONPATH:$PANDIR/POCS/scripts/coverage"
export COVERAGE_PROCESS_START="${PANDIR}/POCS/setup.cfg"

# Run coverage over the pytest suite
echo "Starting tests"
coverage run "$(command -v pytest)" -x -vv -rfes --test-databases all

echo "Combining coverage"
coverage combine

echo "Making XML coverage report at ${REPORT_FILE}"
coverage xml -o "${REPORT_FILE}"

exit 0
