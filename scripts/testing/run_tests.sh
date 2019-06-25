#!/bin/bash -e

cd "$PANDIR/panoptes-utils"
git checkout move-to-panotpes-utils
git pull

# Install any updated requirements
pip install -r requirements.txt

export PYTHONPATH="$PYTHONPATH:$PANDIR/POCS/scripts/coverage"
export COVERAGE_PROCESS_START=.coveragerc
coverage run $(which pytest) -xvrs --test-databases all

# Only worry about coverage if on travis.
if [[ $TRAVIS ]]; then
    coverage combine
    bash <(curl -s https://codecov.io/bash)
fi

exit 0
