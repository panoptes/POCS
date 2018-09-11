#!/bin/bash

usage() {
  echo -n "##################################################
# Take a picture via gphoto2.
# 
# This will change the camera setting to bulb and then take
# an exposure for the requested amount of time.
##################################################
 $ $(basename $0) PORT EXPTIME FILENAME
 
 Options:
  PORT              USB port as reported by gphoto2 --auto-detect, e.g. usb:001,004.
  EXPTIME           Exposure time in seconds, should be greater than 1 second.
  OUTFILE           Output filename (with .cr2 extension).
"
}

if [ $# -eq 0 ]; then
    usage
    exit 1
fi

PORT=$1
EXPTIME=$2
FILENAME=$3
echo 'Taking picture'
echo "PORT = ${PORT}"
echo "TIME = ${TIME}s"
echo "FILE = ${FILENAME}"

# Open shutter
gphoto2 --port=${PORT} \
        --set-config shutterspeed=0 \
        --set-config capturetarget=0 \
        --set-config eosremoterelease=Immediate \
        --wait-event=${EXPTIME}s \
        --set-config eosremoterelease=4 \
        --wait-event-and-download=2s \
        --filename "${FILENAME}"

echo "Done with pic"
