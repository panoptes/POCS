#!/bin/bash

F=$1
echo 'Getting picture'

# Open shutter
gphoto2 --get-file=1 --filename "${F}" && gphoto2 -DR

echo "Done with pic"
