#!/bin/bash -e

export PYTHONPATH="${PYTHONPATH}:${PANDIR}/POCS/scripts/coverage"
export COVERAGE_PROCESS_START="${PANDIR}/POCS/.coveragerc"

coverage run "$(command -v pytest)" -x -vv -rfes --test-databases all

cp "${PANDIR}/logs/panoptes.log" "${POCS}/"

exit 0
