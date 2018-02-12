#!/bin/bash -ex

# This script is designed to be run from /etc/rc.local (or similar)
# as user $PANUSER with the PANOPTES environment variables set.

echo "Running ${BASH_SOURCE[0]} at $(date)"

# cd to the directory of this script, as that is where the
# other start scripts are located.
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "Setting up logging..."

# Setup a directory into which we can log.
export STARTUP_LOG_DIR_SLASH="${PANLOG}/per-run/startup/"
mkdir -p "${STARTUP_LOG_DIR_SLASH}"

NOW="$(date +%Y%m%d-%H%M%S-%Z)"
LOG_FILE="${STARTUP_LOG_DIR_SLASH}$(basename "${BASH_SOURCE[0]}" .sh)-${NOW}.log"

exec 2> "${LOG_FILE}"  # send stderr to a log file
exec 1>&2              # send stdout to the same log file
set -x

# Record important debugging info into the log file.
# These environment variables do NOT all have to be set.

echo "Running ${BASH_SOURCE[0]} at $(date)"
echo "Current dir: $(pwd)"
echo "Current user: ${USER}"
echo "Current path: ${PATH}"
echo "PANUSER: ${PANUSER}"
echo "PANDIR: ${PANDIR}"
echo "PANLOG: ${PANLOG}"
echo "POCS: ${POCS}"
echo "PAWS: ${PAWS}"
echo "PIAA: ${PIAA}"
echo "MATPLOTLIBRC: ${MATPLOTLIBRC}"
# $- expands to the current option flags as specified upon invocation, by the
# set built-in command, or those set by the shell itself (such as the -i).
echo '$-:' "$-"

# Create a detached (-d) tmux session called panoptes (-s),
# with a scrollback buffer of 5000 lines.
tmux set-option -g history-limit 5000 \; new-session -d \
                -s panoptes ./start_panoptes_in_tmux.sh

exit
