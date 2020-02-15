#!/bin/bash -e

export PYTHONPATH="$PYTHONPATH:$PANDIR/POCS/scripts/coverage"
export COVERAGE_PROCESS_START=.coveragerc


python "${PANDIR}/panoptes-utils/panoptes/utils/data.py --no-wide-field --no-narrow-field"

cd $POCS

# Die on first test for now
coverage run "$(command -v pytest)" -xvvrst --test-databases file

# Only worry about coverage if on travis.
if [[ $TRAVIS ]]; then
    chmod 777 .coverage*
    coverage combine
    bash <(curl -s https://codecov.io/bash)
fi

exit 0
