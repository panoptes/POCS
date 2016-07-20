#!/usr/bin/env bash

FNAME=$1
NAME=$2

JPG=${FNAME/cr2/jpg}
LATEST=${PANDIR}/images/latest.jpg

# Use exiftool to extract preview if it exists
if hash exiftool 2>/dev/null; then
    exiftool -b -PreviewImage ${FNAME} > ${JPG}
else
    # Convert CR2 to JPG
    dcraw -c -q 3 -a -w -H 5 -b 5 ${FNAME} | cjpeg -quality 90 > ${JPG}
fi

# Make thumbnail from jpg.
convert ${JPG} -thumbnail 1280x1024 -background black -fill red \
    -font ubuntu -pointsize 24 label:"${NAME}" -gravity South -append ${LATEST}