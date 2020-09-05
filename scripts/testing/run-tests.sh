#!/usr/bin/env bash
set -e

REPORT_FILE=${REPORT_FILE:-coverage.xml}

# This assumes we are always running in a docker container.
export COVERAGE_PROCESS_START="/var/panoptes/POCS/setup.cfg"

# Testing config-server runs on docker system on full ip.
export PANOPTES_CONFIG_HOST='0.0.0.0'
export PANOPTES_CONFIG_PORT=9999

coverage erase

# Run coverage over the pytest suite.
echo "Starting tests"
coverage run "$(command -v pytest)"

echo "Combining coverage"
coverage combine

echo "Making XML coverage report at ${REPORT_FILE}"
coverage xml -o "${REPORT_FILE}"

coverage report --show-missing

exit 0
