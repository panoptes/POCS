#!/bin/bash

T=$1
echo 'Taking picture'
echo "T = ${T}s"

# gphoto2 --port $P --reset
gphoto2 --camera="Canon EOS 100D" --port `readlink -f /dev/canon0 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --set-config eosremoterelease=Immediate &> /dev/null
# gphoto2 --camera="Canon EOS 100D" --port `readlink -f /dev/canon1 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --set-config eosremoterelease=Immediate &> /dev/null
sleep ${T}
gphoto2 --port `readlink -f /dev/canon0 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --set-config eosremoterelease=4 &> /dev/null
# gphoto2 --port `readlink -f /dev/canon1 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --set-config eosremoterelease=4 &> /dev/null

gphoto2 --port `readlink -f /dev/canon0 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --wait-event-and-download=2s --filename "${F}" &> /dev/null
# gphoto2 --port `readlink -f /dev/canon1 | cut -d "/" -f4-6 | sed 's/\//:/' | sed 's/\//,/'` --wait-event-and-download=1s --filename "${F}" &> /dev/null

echo "Done with pic"
