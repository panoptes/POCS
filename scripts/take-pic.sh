#!/usr/bin/env bash
set -e

usage() {
  echo -n "##################################################
# Take a picture via gphoto2.
#
# This will change the camera setting to bulb and then take
# an exposure for the requested amount of time.
#
# This script has only been tested with Canon EOS100D models
# but should be generic to any gphoto2 camera that supports
# bulb settings.
#
# Fixed settings include:
#    * shutterspeed=0       Bulb (manual) exposure time.
#    * capturetarget=0      Capture to RAM.
##################################################
 $ $(basename $0) PORT EXPTIME OUTFILE

 Options:
  PORT              USB port as reported by gphoto2 --auto-detect, e.g. usb:001,004.
  EXPTIME           Exposure time in seconds, should be greater than 1 second.
                    Can be either an integer or string.
  OUTFILE           Output filename with appropriate extension, e.g. .cr2 for Canon.
  ISO               ISO value. Must be a valid ISO value for the camera, default 100.

 Example:
  scripts/take-pic.sh usb:001,005 5 /var/panoptes/images/temp.cr2
"
}

if [ $# -eq 0 ]; then
  usage
  exit 1
fi

PORT=$1
EXPTIME=$2
FILENAME=$3
ISO=${4:-100}
echo 'Taking picture'
echo "PORT = ${PORT}"
echo "TIME = ${TIME}s"
echo "FILE = ${FILENAME}"
echo "ISO = ${ISO}"

gphoto2 --port="${PORT}" \
  --set-config-index shutterspeed=0 \
  --set-config-index capturetarget=0 \
  --set-config iso="${ISO}" \
  --wait-event="1s" \
  --set-config-index eosremoterelease=2 \
  --wait-event="${EXPTIME}s" \
  --set-config-index eosremoterelease=4 \
  --wait-event-and-download=1s \
  --filename "${FILENAME}"

echo "Done with pic"

exit 0
