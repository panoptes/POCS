#!/bin/bash +e

UPLOAD_DIR=$1
echo "Zipping files found in ${UPLOAD_DIR}"

tar zcf failed-images.tgz $UPLOAD_DIR

echo "Uploading public temporary hosting site"
echo "Files can be downloaded from:" > temp.txt
curl --upload-file failed-images.tgz https://transfer.sh/failed-images.tgz >> temp.txt
cat temp.txt
