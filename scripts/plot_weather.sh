#!/bin/bash

# Runs scripts/plog_weather.py, which will generate an image in
# $PANDIR/weather_plots/.

# We need the shell to have the the PANOPTES environment setup.

echo "Running ${BASH_SOURCE[0]} at $(date)"

if [[ -z "$PANDIR" || -z "$POCS" || -z "$PANLOG" ]] ; then
  echo "The PANOPTES environment variables must be set."
  echo "This script should be run from a login shell."
  exit 1
fi

echo "Setting up logging..."

# Setup a directory for the log file from this script and from those
# it invokes. By creating a unique directory per startup, we make it
# easier to view the group of files from a single reboot.
export LOG_DIR_SLASH="${PANLOG}/per-run/$(basename "${BASH_SOURCE[0]}" .sh)/"
mkdir -p "${LOG_DIR_SLASH}"

LOG_NAME="$(basename "${BASH_SOURCE[0]}" .sh).$(date +%Y%m%d-%H%M%S-%Z).log"
LOG_FILE="${LOG_DIR_SLASH}${LOG_NAME}"

echo "Will log to ${LOG_FILE}"

exec 2> "${LOG_FILE}"  # send stderr to a log file
exec 1>&2              # send stdout to the same log file
set +x

# Record a bunch of environment variables into the log file. This
# helps us later if we need to debug the execution of this script
# and those it invokes.
echo "Running ${BASH_SOURCE[0]} at $(date)"
echo "Current dir: $(pwd)"
echo "Current user: $(whoami)"
echo "USER: ${USER}"
echo "LOGNAME: ${LOGNAME}"
echo "PATH: ${PATH}"
echo "PANUSER: ${PANUSER}"
echo "PANDIR: ${PANDIR}"
echo "PANLOG: ${PANLOG}"
echo "POCS: ${POCS}"
echo "PAWS: ${PAWS}"
echo "PIAA: ${PIAA}"

set -x

"${POCS}/scripts/plot_weather.py"
