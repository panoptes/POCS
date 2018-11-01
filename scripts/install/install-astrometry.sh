#!/bin/bash -ex

ASTROMETRY_VERSION="${ASTROMETRY_VERSION:-0.72}"
ASTROMETRY_DIR="astrometry.net-${ASTROMETRY_VERSION}"

TAR_NAME="astrometry.net-${ASTROMETRY_VERSION}.tar.gz"
TAR_URL="http://astrometry.net/downloads/${TAR_NAME}"

ZIP_NAME="astrometry.net-${ASTROMETRY_VERSION}.zip"
ZIP_URL="https://github.com/dstndstn/astrometry.net/archive/${ASTROMETRY_VERSION}.zip"

DO_WGET="wget --dns-timeout=30 --connect-timeout=30 --read-timeout=60 --tries=1"

if [ -x $PANDIR/astrometry/bin/solve-field ] ; then
  echo "Astrometry has been cached:"
  find $PANDIR/astrometry -type f -executable -ls
  exit
fi

cd $PANDIR
echo "Downloading ${TAR_URL} ..."
$DO_WGET "${TAR_URL}" || /bin/true
if [ -f "${TAR_NAME}" ] ; then
  echo "Unpacking ${TAR_NAME} ..."
  tar zxf "${TAR_NAME}"
else
  echo "Unable to download ${TAR_URL}"
  echo "Downloading ${ZIP_URL} ..."
  $DO_WGET --output-document="${ZIP_NAME}" "${ZIP_URL}"
  echo "Unpacking ${ZIP_NAME} ..."
  unzip "${ZIP_NAME}"
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