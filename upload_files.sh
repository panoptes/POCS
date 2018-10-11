#!/bin/bash -e

usage() {
  echo -n "##################################################
# Upload files to Google Cloud Storage bucket.
# 
# This script will call the underlying gsutil utility, using
# the parallel options (-m) by default. This will also write
# a manifest log into the directory which can be used for upload
# valildation.
#
# For more information, see documentation at:
# https://cloud.google.com/storage/docs/gsutil/commands/cp
#
# Note:
# The SEARCH_PATH and DESTINATION are often similar. Normal invocation
# is done via $POCS/scripts/upload_image_dir.py. See also the utils in
# $POCS/pocs/utils/google/storage.py.
#
# Note:
# The SEARCH_PATH can be any pattern, e.g:
#     - 'PAN006'  # All images for unit
#     - 'PAN006/Hd189733/7bab97' # All images for unit, field, camera
#     - 'PAN006/Hd189733/7bab97/20180327T071126/' # Specific observation
#############################################################
 $ $(basename $0) SEARCH_PATH DESTINATION MANIFEST_PATH
 
 Options:
  SEARCH_PATH     The string path to be searched.
  DESTINATION     Remote upload destination.
  MANIFEST_PATH   Path to manifest file for tracking uploads.

 NOTE: $POCS/scripts/upload_image_dir.py may be more approrpriate.
"
}

if [ $# -ne 3 ]; then
    usage
    exit 1
fi

SEARCH_PATH="$1"
DESTINATION="$2"
MANIFEST_PATH="$3"
echo 'Uploading files'
echo "SEARCH_PATH = ${SEARCH_PATH}"
echo "DESTINATION = ${DESTINATION}"
echo "MANIFEST_PATH = ${MANIFEST_PATH}"

# Loops until all files are uploaded. See `gsutil cp` documentation.
until gsutil -mq cp -c -L "${MANIFEST_PATH}" -r "${SEARCH_PATH}" "${DESTINATION}"; do
  sleep 1
done