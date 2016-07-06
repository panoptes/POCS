#!/bin/bash

P=$1
T=$2
F=$3
echo 'Taking picture'
echo "P=${P}"
echo "T=${T}"
echo "F=${F}"

# gphoto2 --port $P --reset
gphoto2 --camera="Canon EOS 100D" --port `readlink -f /dev/canon0 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --set-config eosremoterelease=Immediate &> /dev/null
gphoto2 --camera="Canon EOS 100D" --port `readlink -f /dev/canon1 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --set-config eosremoterelease=Immediate &> /dev/null
sleep ${T}
gphoto2 --port `readlink -f /dev/canon0 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --set-config eosremoterelease=4 &> /dev/null
gphoto2 --port `readlink -f /dev/canon1 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --set-config eosremoterelease=4 &> /dev/null

gphoto2 --port `readlink -f /dev/canon0 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --wait-event-and-download=1s --filename "${F}" &> /dev/null
gphoto2 --port `readlink -f /dev/canon1 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --wait-event-and-download=1s --filename "${F}" &> /dev/null

#gphoto2 --port $P --reset

# Open shutter
# gphoto2 --camera="Canon EOS 100D" --port $P --set-config eosremoterelease=Immediate \
#         --wait-event=${T}s --set-config eosremoterelease=4 --wait-event-and-download=2s \
#         --filename "${F}"

echo "Done with pic"
