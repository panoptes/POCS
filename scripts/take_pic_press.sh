#!/bin/bash

echo 'Taking picture'

# Open shutter
gphoto2 --camera="Canon EOS 100D" --set-config eosremoterelease=Immediate 

echo "Shutter pressed"
