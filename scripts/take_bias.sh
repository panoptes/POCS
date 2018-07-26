#!/bin/bash -e

##################################################
# Take a bias from
# 
# This will change the camera setting to the quickest
# exposure possible and then take a number of photos
##################################################

P=$1
SAVE_FILE=${2:-"bias-%Y%m%d-%H%M%S.cr2"}
echo "Taking bias frames on port ${P}: ${SAVE_FILE}"

SHUTTER_INDEX=52
NUM_FRAMES=5

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