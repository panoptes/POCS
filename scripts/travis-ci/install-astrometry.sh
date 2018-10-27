#!/bin/bash -e

ASTROMETRY_VERSION="${ASTROMETRY_VERSION:-0.72}"
ASTROMETRY_DIR="astrometry.net-${ASTROMETRY_VERSION}"

TAR_NAME="astrometry.net-${ASTROMETRY_VERSION}.tar.gz"
TAR_URL="http://astrometry.net/downloads/${ARCHIVE}"

ZIP_NAME="astrometry.net-${ASTROMETRY_VERSION}.zip"
ZIP_URL="https://github.com/dstndstn/astrometry.net/archive/${ASTROMETRY_VERSION}.zip"

if [ -x $PANDIR/astrometry/bin/solve-field ] ; then
  echo "Astrometry has been cached:"
  find $PANDIR/astrometry -type f -executable -ls
  exit
fi

cd $PANDIR
echo "Downloading tar from astrometry.net..."
wget --tries=2 --output-document="${TAR_NAME}" "${TAR_URL}" || /bin/true
if [ -f "${TAR_NAME}" ] ; then
  echo "Unpacking ${TAR_NAME}"
  tar zxvf "${TAR_NAME}" -C "${ASTROMETRY_DIR}"
else
  echo "Unable to download ${ARCHIVE_URL}. Trying to download the zip from github..."
  wget --tries=2 --output-document="${ZIP_NAME}" "${ZIP_URL}"
  echo "Unpacking ${ZIP_NAME}"
  unzip "${ZIP_NAME}" -d "${ASTROMETRY_DIR}"
fi

echo "Building astrometry in ${ASTROMETRY_DIR}..."
cd "${ASTROMETRY_DIR}"

make
make py
find . -type f -executable -ls

echo "Installing astrometry into $PANDIR/astrometry..."

make install INSTALL_DIR=$PANDIR/astrometry
find $PANDIR/astrometry -type f -executable -ls

mkdir -p $PANDIR/astrometry/data
echo 'add_path $PANDIR/astrometry/data' >> $PANDIR/astrometry/etc/astrometry.cfg
