#!/usr/bin/env bash

FNAME=$1
NAME=$2
LINK=$3

JPG=${FNAME/cr2/jpg}
LATEST=${PANDIR}/images/latest.jpg

# We only make a thumb of latest
THUMB=${LATEST/.jpg/_tn.png}

# Convert CR2 to JPG
dcraw -c -q 3 -a -w -H 5 -b 5 ${FNAME} | cjpeg -quality 90 > ${JPG}

if [[ $LINK == 'link' ]]; then
    # Make thumbnail from jpg. Roughly 1/8th original
    convert ${JPG} -thumbnail 651x450 -background black -fill red \
        -font ubuntu -pointsize 12 label:"${NAME}" -gravity South -append ${THUMB}

    # Remove symlink
    rm ${LATEST}
    ln -s ${JPG} ${LATEST}
    # Annotate the symlink
    convert ${LATEST} -orient bottom-right -background black -fill red -font ubuntu -pointsize 72 \
        label:"${NAME}" -gravity South -append ${LATEST}
fi
