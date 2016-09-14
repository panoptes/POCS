#!/bin/bash

F=$1
echo 'Taking picture'

# Open shutter
gphoto2 --set-config eosremoterelease=4 --wait-event-and-download=5s --filename "${F}"

echo "Done with pic"
