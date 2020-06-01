#!/bin/bash -e

usage() {
  echo -n "
#############################################################
# Transfer files to/from a Google Cloud Storage bucket.
#
# This script will call the underlying gsutil utility, using
# the parallel options (-m) by default. This will also write
# a manifest log into the directory which can be used for transfer
# validation.
#
# For more information, see documentation at:
# https://cloud.google.com/storage/docs/gsutil/commands/cp
#
# Note:
# The FROM_PATH and TO_PATH are often similar. Normal invocation
# is done via $POCS/scripts/upload_image_dir.py. See also the utils in
# $POCS/pocs/utils/google/storage.py.
#
# Note:
# The transfer path can be any pattern, e.g:
#     - 'PAN006'  # All images for unit
#     - '*/Hd189733'  # All images for field
#     - 'PAN006/Hd189733/7bab97' # All images for unit, field, camera
#     - 'PAN006/*/7bab97' # All images for unit, camera
#     - 'PAN006/Hd189733/7bab97/20180327T071126/' # Specific observation
#############################################################
 $ $(basename "$0") FROM_PATH TO_PATH MANIFEST_FILE

 Options:
  FROM_PATH     File(s) to be moved.
  TO_PATH       Where file(s) are to be placed.
  MANIFEST_FILE Path to manifest file for tracking uploads. Optional, defaults
                to manifest_file.log in the current directory.

 NOTE: $POCS/scripts/upload_image_dir.py may be more appropriate.

 Example:
    # Upload a sample file
    scripts/transfer-files upload-example.txt gs://panoptes-temp-bucket/temp/

    # Download directory to dest_temp with different manifest_file
    scripts/transfer-files gs://panoptes-temp-bucket/temp/ dest_temp/ upload-log.txt
"
}

if [ $# -ne 3 ]; then
    usage
    exit 1
fi

FROM_PATH="${1}"
TO_PATH="${2}"
MANIFEST_FILE="${3:-manifest_file.log}"
echo 'Uploading files'
echo "FROM_PATH = ${FROM_PATH}"
echo "TO_PATH = ${TO_PATH}"
echo "MANIFEST_FILE = ${MANIFEST_FILE}"

# Loops until all files are uploaded. See `gsutil cp` documentation.
until gsutil -mq cp -c -L "${MANIFEST_FILE}" -r "${FROM_PATH}" "${TO_PATH}"; do
  sleep 1
done
