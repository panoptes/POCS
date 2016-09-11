#!/bin/bash

# We need to be running python2.7
source activate py27 || source activate python2

if [[ $# == 1 ]]; then
    echo "Using options: --guess-scale --no-plots --downsample 3 --overwrite"
    solve-field --guess-scale --no-plots --downsample 3 --overwrite $1
else
    solve-field $@
fi
