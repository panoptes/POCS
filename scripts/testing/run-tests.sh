#!/bin/bash -e

cd "${PANDIR}/panoptes-utils"
# Install any updated requirements
pip install -e ".[all]"

# Install any updated requirements
cd "${PANDIR}/POCS"
pip install -r requirements.txt

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
