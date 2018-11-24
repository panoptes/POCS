#!/bin/bash +e

UPLOAD_DIR=$1
echo "Zipping files found in ${UPLOAD_DIR}"

tar zcf failed-images.tgz $UPLOAD_DIR

echo "Uploading public temporary hosting site"
echo "Download failed images from:" > temp.txt
curl --upload-file failed-images.tgz https://transfer.sh/failed-images.tgz >> temp.txt
echo "\n\nThere will be one subfolder per failed test." >> temp.txt
cat temp.txt
