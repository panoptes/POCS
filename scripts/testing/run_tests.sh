#!/bin/bash -e

# Install any updated requirements
pip install -r requirements.txt

export PYTHONPATH="$PYTHONPATH:$PANDIR/POCS/scripts/coverage"
export COVERAGE_PROCESS_START=.coveragerc
coverage run $(which pytest) -v --test-databases all

# Only worry about coverage if on travis.
if [[ $TRAVIS ]]; then
    coverage combine
    bash <(curl -s https://codecov.io/bash)
fi

exit 0
