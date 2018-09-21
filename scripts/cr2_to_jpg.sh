#!/bin/bash -e

usage() {
  echo -n "##################################################
# Make a jpeg from the Canon Raw v2 (.CR2) file.
# 
# If exiftool is present this merely extracts the thumbnail from
# the CR2 file, otherwise use dcraw to create a jpeg.
#
# If present the TITLE is added as a title to the jpeg.
##################################################
 $ $(basename $0) FILENAME [TITLE]
 
 Options:
  FILENAME          Name of CR2 file that holds jpeg.
  TITLE             Optional tilte to be placed on jpeg.

 Example:
  scripts/cr2_to_jpg.sh /var/panoptes/images/temp.cr2 \"M42 (Orion's Nebula)\"
"
}

if [ $# -eq 0 ]; then
    usage
    exit 1
fi

FNAME=$1
TITLE="${2}"

JPG="${FNAME%.cr2}.jpg"

echo "Converting CR2 to ${JPG}."

# Use exiftool to extract preview if it exists
if hash exiftool 2>/dev/null; then
    exiftool -b -PreviewImage "${FNAME}" > "${JPG}"
else
    if hash dcraw 2>/dev/null; then
        # Convert CR2 to JPG
        dcraw -c -q 3 -a -w -H 5 -b 5 "${FNAME}" | cjpeg -quality 90 > "${JPG}"
    else
        echo "Can't find either exiftool or dcraw, cannot proceed"
        exit
    fi
fi

if [[ -n "$TITLE" ]]
  then
  	echo "Adding title \"${TITLE}\""
	# Make thumbnail from jpg.
	convert "${JPG}" -background black -fill red \
	    -font ubuntu -pointsize 60 label:"${TITLE}" \
	    -gravity South -append "${JPG}"
fi

echo "${JPG}"