#!/bin/bash -e

export PYTHONPATH="$PYTHONPATH:$PANDIR/POCS/scripts/coverage"
export COVERAGE_PROCESS_START=.coveragerc
# Die on first test for now
coverage run "$(command -v pytest)" -xvvrs --test-databases all

# Only worry about coverage if on travis.
if [[ $TRAVIS ]]; then
    coverage combine
    bash <(curl -s https://codecov.io/bash)
fi

exit 0
