#!/usr/bin/env bash
set -e

usage() {
  echo -n "###############################################################################
# Take a picture via a gphoto2 using a local or remote server.
#
# Simple wrapper to check for \$REMOTE_GPHOTO2_ENDPOINT env var. If present, will
# use the value of the var as the endpoint for the camera service. If not present,
# use /usr/bin/gphoto2 from the PATH.
#
# Any additional arguments to the script are passed directly to gphoto2.
################################################################################

 Example:
  # This will be run locally and download to the local machine.
  scripts/gphoto2.sh --port usb:001,005 --capture-image-and-download

  # This will be run remotely and download to the remote machine.
  REMOTE_GPHOTO2_ENDPOINT=192.168.1.100:6570/ --port usb:001,005 --capture-image-and-download

"
}

if [ $1 == "--help" ]; then
  usage
  exit 1
fi

if [[ -n "${REMOTE_GPHOTO2_ENDPOINT}" ]]; then
  echo "Using ${REMOTE_GPHOTO2_ENDPOINT}"
  http POST "${REMOTE_GPHOTO2_ENDPOINT}" arguments="$@"
else
  if [ "$(command -v gphoto2)" ]; then
    /usr/bin/gphoto2 "$@"
  else
    echo "/usr/bin/gphoto2 is not installed."
  fi
fi

exit 0
