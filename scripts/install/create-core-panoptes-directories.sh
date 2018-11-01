#!/bin/bash -e
#
# Setup directories needed by PANOPTES. Other scripts, such as
# install-dependencies.sh, expect to find these directories.
# We do NOT parameterize these paths (i.e. don't use environment
# variables to permit override). The one override we do allow
# is specifying the user that should own /var/panoptes.

PANUSER="${PANUSER:-$(whoami)}"

if [ "${PANUSER}" == "root" -a "$(whoami)" == "root" ] ; then
  # Supports the docker use case.
  MKDIR_ROOT="${MKDIR_ROOT:-mkdir}"
  MKDIR_PANUSER="${MKDIR:-mkdir}"
  CHOWN="${CHOWN:-echo Skipping chown}"
  CHMOD="${CHMOD:-echo Skipping chmod}"
else
  MKDIR_ROOT="${MKDIR_ROOT:-sudo mkdir}"
  MKDIR_PANUSER="${MKDIR:-sudo --group="${PANUSER}" --user="${PANUSER}" mkdir}"
  CHOWN="${CHOWN:-sudo chown}"
  CHMOD="${CHMOD:-sudo chmod}"
fi

if [ ! -d /var/panoptes ] ; then
  echo "Creating /var/panoptes. You MAY be prompted for your password by sudo."
  (set -x ; ${MKDIR_ROOT} -p /var/panoptes)
else
  echo "/var/panoptes already exists."
fi

echo "Ensuring that all files in /var/panoptes are owned by ${PANUSER}."
(set -x ; ${CHOWN} -R "${PANUSER}:${PANUSER}" /var/panoptes)
(set -x ; ${CHMOD} -R 755 /var/panoptes)

for SUBDIR in POCS PAWS logs astrometry/data
do
  DIR="/var/panoptes/${SUBDIR}"
  if [ ! -d "${DIR}" ] ; then
    echo "Creating ${DIR}. You MAY be prompted for your password by sudo."
    (set -x ; ${MKDIR_PANUSER} -p "${DIR}")
  else
    echo "${DIR} already exists."
  fi
done
