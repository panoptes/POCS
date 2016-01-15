#!/bin/bash

FNAME=$1

# We need to be running python2.7
source activate py27

solve-field --guess-scale --no-plots --downsample 3 --overwrite ${FNAME}