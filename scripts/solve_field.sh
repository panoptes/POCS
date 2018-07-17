#!/bin/bash

# If SOLVE_FIELD is not set, try the default; warn if default unavailable.
SOLVE_FIELD=${SOLVE_FIELD:-"${PANDIR}/astrometry/bin/solve-field"}
if [ ! -f $SOLVE_FIELD ]
then
	echo 2>&1 ""
	echo 2>&1 "Please install astrometry into ${PANDIR}/astrometry to enable $0"
	echo 2>&1 ""
	exit 3 # Command not found
fi

if [[ $# == 1 ]]; then
    echo "Using options: --guess-scale --no-plots --downsample 3 --overwrite"
    ${SOLVE_FIELD} --guess-scale --no-plots --downsample 3 --overwrite $1
else
    ${SOLVE_FIELD} $@
fi
