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
  NUM_FRAMES        Number of exposures to take, defaults to 1.
  SHUTTER_INDEX     The camera shutter index to use, defaults to 52 (1/4000s) on
                    EOS100D.
"
}

if [ $# -eq 0 ]; then
    usage
    exit 1
fi

P=$1

SAVE_FILE=${2:-"bias-%Y%m%d-%H%M%S.cr2"}
echo "Taking bias frames on port ${P}: ${SAVE_FILE}"

NUM_FRAMES=${4:-1}
SHUTTER_INDEX=${3:-52} # 1/4000s on EOS 100D

# Set to fast speed
gphoto2 --port=${P} --set-config-index shutterspeed=${SHUTTER_INDEX}

COUNTER=0
until [[ ${COUNTER} -eq ${NUM_FRAMES} ]]; do
    gphoto2 --port=${P} --filename=${SAVE_FILE} --capture-image-and-download
    let COUNTER+=1
done

# Set back to bulb
gphoto2 --port=${P} --set-config-index shutterspeed=0

echo "Done with bias"