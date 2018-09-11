#!/bin/bash

P=$1
T=$2
F=$3
echo 'Taking picture'
echo "T = ${T}s"


# Make sure bulb is set
gphoto2 --port=${P} --set-config-index=0 --set-config-index capturetarget=0

# Open shutter
gphoto2 --port=${P} --set-config eosremoterelease=Immediate \
         --wait-event=${T}s --set-config eosremoterelease=4 --wait-event-and-download=2s \
         --filename "${F}"

echo "Done with pic"
