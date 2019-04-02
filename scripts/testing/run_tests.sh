#!/bin/bash -e 

export PYTHONPATH="$PYTHONPATH:$PANDIR/POCS/scripts/coverage"
export COVERAGE_PROCESS_START=.coveragerc
coverage run $(which pytest) -v --test-databases all
coverage combine
bash <(curl -s https://codecov.io/bash)