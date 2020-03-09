#!/bin/bash -e

export PYTHONPATH="${PYTHONPATH}:${PANDIR}/POCS/scripts/coverage"
export COVERAGE_PROCESS_START="${PANDIR}/POCS/.coveragerc"

coverage run "$(command -v pytest)" -vv -rfes --test-databases all

# Only worry about coverage if on travis.
if [[ $TRAVIS ]]; then
    chmod 777 .coverage*
    coverage combine
    bash <(curl -s https://codecov.io/bash)
fi

exit 0
