#!/usr/bin/env bash

FNAME=$1
LINK=$2

dcraw -c -q 3 -a -w -H 5 -b 5 ${FNAME} | cjpeg -quality 80 > ${FNAME/cr2/jpg}

if [[ $LINK == 'link' ]]; then
    ln -s ${FNAME/cr2/jpg} /var/panoptes/images/latest.jpg
fi
