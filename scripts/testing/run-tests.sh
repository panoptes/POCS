#!/bin/bash -e

REPORT_FILE=${REPORT_FILE:-coverage.xml}

# This assumes we are always running in a docker container.
export COVERAGE_PROCESS_START="/var/panoptes/POCS/setup.cfg"

coverage erase

# Run coverage over the pytest suite.
echo "Starting tests"
PY_IGNORE_IMPORTMISMATCH=1 coverage run "$(command -v pytest-3)"

echo "Combining coverage"
coverage combine

echo "Making XML coverage report at ${REPORT_FILE}"
coverage xml -o "${REPORT_FILE}"

coverage report --show-missing

exit 0
