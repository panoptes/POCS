#!/bin/bash -e

usage() {
  echo -n "##################################################
# Take a series of bias frame images.
# 
# This will change the camera setting to the quickest
# exposure possible and then take a number of photos
# before changing camera back to bulb setting.
##################################################

 $ $(basename $0) PORT [OUTFILE] [NUM_FRAMES] [SHUTTER_INDEX]
 
 Options:
  PORT              USB port as reported by gphoto2 --auto-detect, e.g. usb:001,004.
  OUTFILE           Output filename, defaults to bias-YMD-HMS.cr2.
  SHUTTER_INDEX     The camera shutter index to use, defaults to 52 (1/4000s) on
                    EOS100D.
  NUM_FRAMES        Number of exposures to take, defaults to 1.
"
}

if [ $# -eq 0 ]; then
  usage
  exit 1
fi

PORT=$1

SAVE_FILE=${2:-"bias-%Y%m%d-%H%M%S.cr2"}
echo "Taking bias frames on port ${PORT}: ${SAVE_FILE}"

SHUTTER_INDEX=${3:-52} # 1/4000s on EOS 100D
ISO=${4:-100}
NUM_FRAMES=${5:-1}

# Set shutter speed.
gphoto2 --port="${PORT}" --set-config-index shutterspeed="${SHUTTER_INDEX}"
sleep 0.5
# Set iso.
gphoto2 --port="${PORT}" --set-config iso="${ISO}"

COUNTER=0
until [[ ${COUNTER} -eq ${NUM_FRAMES} ]]; do
  gphoto2 --port="${PORT}" --wait-event=1s --capture-image-and-download --filename="${SAVE_FILE}"
  let COUNTER+=1
done

echo "Done with bias"
