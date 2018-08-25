#!/bin/bash

P=$1
T=$2
F=$3
echo 'Taking picture'
echo "T = ${T}s"

# Open shutter
gphoto2 --port=${P} \
		--set-config shutterspeed=0 \
		--set-config capturetarget=0 \
		--set-config eosremoterelease=Immediate \
        --wait-event=${T}s \
        --set-config eosremoterelease=4 \
        --wait-event-and-download=2s \
        --filename "${F}"

echo "Done with pic"
