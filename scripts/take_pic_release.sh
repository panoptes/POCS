#!/bin/bash

F=$1
echo 'Taking picture'

# Open shutter
gphoto2 --camera="Canon EOS 100D"--set-config eosremoterelease=4 --wait-event-and-download=5s --filename "${F}"

echo "Done with pic"
