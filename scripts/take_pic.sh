#!/bin/bash

P=$1
T=$2
F=$3
echo 'Taking picture'
echo "P=${P}"
echo "T=${T}"
echo "F=${F}"

gphoto2 --port $P --reset
gphoto2 --camera="Canon EOS 100D" --port $P --set-config eosremoterelease=Immediate &> /dev/null
sleep ${T}
gphoto2 --port $P --set-config eosremoterelease=4 &> /dev/null
gphoto2 --port $P --wait-event-and-download=1s --filename "${F}_%H%M%S.cr2" &> /dev/null

echo "Done with pic"
