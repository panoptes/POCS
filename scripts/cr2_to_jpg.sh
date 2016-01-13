#!/usr/bin/env bash

FNAME=$1

dcraw -c -q 3 -a -w -H 5 -b 5 ${FNAME} | cjpeg -quality 80 > ${FNAME/cr2/jpg}
