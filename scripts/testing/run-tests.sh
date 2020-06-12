#!/usr/bin/env bash
set -e

cd "${POCS}"

echo "Run test params: $@"

REPORT_FILE=${REPORT_FILE:-coverage.xml}

# This assumes we are always running in a docker container.
export COVERAGE_PROCESS_START="/var/panoptes/panoptes-pocs/setup.cfg"

coverage erase

# Run coverage over the pytest suite.
echo "Starting tests"

if [[ -z ${CLI_ARGS} ]]; then
    coverage run "$(command -v pytest) ${CLI_ARGS}"
else
    coverage run "$(command -v pytest)"
fi

echo "Combining coverage"
coverage combine

echo "Making XML coverage report at ${REPORT_FILE}"
coverage xml -o "${REPORT_FILE}"

coverage report --show-missing

exit 0
