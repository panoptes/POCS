#!/usr/bin/env bash
set -e

COVERAGE_REPORT_FILE=${COVERAGE_REPORT_FILE:-/var/panoptes/logs/coverage.xml}
PANOPTES_CONFIG_HOST="${PANOPTES_CONFIG_HOST:-localhost}"
PANOPTES_CONFIG_PORT="${PANOPTES_CONFIG_PORT:-8765}"

# This assumes we are always running in a docker container.
export COVERAGE_PROCESS_START="/var/panoptes/POCS/setup.cfg"

coverage erase

# Run coverage over the pytest suite.
echo "Starting config server in background"
echo "PANOPTES_CONFIG_FILE=${PANOPTES_CONFIG_FILE}"
echo "PANOPTES_CONFIG_HOST=${PANOPTES_CONFIG_HOST}"
echo "PANOPTES_CONFIG_PORT=${PANOPTES_CONFIG_PORT}"
panoptes-config-server --host "${PANOPTES_CONFIG_HOST}" --port "${PANOPTES_CONFIG_PORT}" run --no-load-local --no-save-local &

echo "Checking to make sure panoptes-config-server is running"
scripts/wait-for-it.sh --timeout=30 --strict "${PANOPTES_CONFIG_HOST}:${PANOPTES_CONFIG_PORT}" -- echo "Config-server up"

echo "Starting testing"
coverage run "$(command -v pytest)"
echo "Stopping config server"
panoptes-config-server --verbose --host "${PANOPTES_CONFIG_HOST}" --port "${PANOPTES_CONFIG_PORT}" stop

echo "Combining coverage for ${COVERAGE_REPORT_FILE}"
coverage combine

echo "Making XML coverage report at ${COVERAGE_REPORT_FILE}"
coverage xml -o "${COVERAGE_REPORT_FILE}"
coverage report --show-missing

exit 0
