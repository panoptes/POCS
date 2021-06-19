#!/usr/bin/env bash
set -e

usage() {
  echo -n "###############################################################################
# Take a picture via a gphoto2 using a local or remote server.
#
# Simple wrapper to check for \$REMOTE_GPHOTO2_SERVER env var. If present, will
# use the value of the var as the ip address for ssh. It is assumed that ssh
# keys have already been set between the two servers. If not present, use
# /usr/bin/gphoto2 from the PATH.
#
# This file should be symlinked into the PATH under the name 'gphoto2'.
#
# Any additional arguments to the script are passed directly to gphoto2.
################################################################################

 Example:
  # This will be run locally and download to the local machine.
  scripts/gphoto2.sh --port usb:001,005 --capture-image-and-download

  # This will be run remotely and download to the remote machine.
  REMOTE_GPHOTO2_SERVER=192.168.1.100 scripts/gphoto2.sh --port usb:001,005 --capture-image-and-download

"
}

if [ $1 == "--help" ]; then
  usage
  exit 1
fi

echo "${REMOTE_GPHOTO2_SERVER}"

if [[ -n "${REMOTE_GPHOTO2_SERVER}" ]]; then
  echo "Using ${REMOTE_GPHOTO2_SERVER}"
  ssh "${REMOTE_GPHOTO2_SERVER}" gphoto2 "$@"
else
  if [ "$(command -v gphoto2)" ]; then
    /usr/bin/gphoto2 "$@"
  else
    echo "/usr/bin/gphoto2 is not installed."
  fi
fi

exit 0
