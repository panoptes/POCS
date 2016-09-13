#!/bin/bash

F=$1
echo 'Taking picture'
echo "T = ${T}s"

# Open shutter
gphoto2 --camera="Canon EOS 100D"--set-config eosremoterelease=4 --wait-event-and-download=2s \
         --filename "${F}"

echo "Done with pic"
