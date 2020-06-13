#!/usr/bin/env bash
set -e

cd "${POCS}"
PYTEST_CMD="$(command -v pytest)"

echo "Run test params: ${PYTEST_CMD} $@"

REPORT_FILE=${REPORT_FILE:-coverage.xml}

# This assumes we are always running in a docker container.
export COVERAGE_PROCESS_START="/var/panoptes/panoptes-pocs/setup.cfg"

# Run coverage over the pytest suite.
echo "Starting tests"

coverage erase
coverage run "${PYTEST_CMD}"

coverage combine
coverage xml -o "${REPORT_FILE}"
coverage report --show-missing

exit 0
