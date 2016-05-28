#!/bin/bash

P=$1
T=$2
F=$3
# echo 'Taking picture'
# echo "P=${P}"
# echo "T=${T}"
# echo "F=${F}"


# echo $opts

/usr/bin/gphoto2 --port $P --reset
/usr/bin/gphoto2 --camera="Canon EOS 100D" --debug --debug-logfile=$HOME/gphoto2.log \
    --port ${P} --set-config eosremoterelease=Immediate --wait-event=${T}s \
    --set-config eosremoterelease=4 --wait-event-and-download=1s --filename="${F}%03n.cr2" > /dev/null