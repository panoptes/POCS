#!/bin/bash

SOLVE_FIELD="${PANDIR}/astrometry/bin/solve-field"

if [[ $# == 1 ]]; then
    echo "Using options: --guess-scale --no-plots --downsample 3 --overwrite"
    ${SOLVE_FIELD} --guess-scale --no-plots --downsample 3 --overwrite $1
else
    ${SOLVE_FIELD} $@
fi
