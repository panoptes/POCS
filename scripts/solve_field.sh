#!/bin/bash

if [[ $# == 1 ]]; then
    echo "Using options: --guess-scale --no-plots --downsample 3 --overwrite"
    solve-field --guess-scale --no-plots --downsample 3 --overwrite $1
else
    solve-field $@
fi
