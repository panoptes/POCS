#!/bin/bash -e

# This script is designed to be run inside tmux, launched by
# tmux_launch.sh. Make sure that is so.
echo "Running ${BASH_SOURCE[0]} at $(date)"
if [[ -z "${STARTUP_LOG_DIR_SLASH}" ]] ; then
  echo "This script must be run by tmux_launch.sh"
  exit 1
fi

NOW="$(date +%Y%m%d-%H%M%S-%Z)"
LOG_FILE="${STARTUP_LOG_DIR_SLASH}$(basename "${BASH_SOURCE[0]}" .sh)-${NOW}.log"

exec 2> "${LOG_FILE}"  # send stderr to a log file
exec 1>&2              # send stdout to the same log file
set -x

echo "Running ${BASH_SOURCE[0]} at $(date)"

# Record important debugging info into the log file. These
# environment variables do NOT all have to be set. Note that
# this script is executed inside of a tmux session, which
# SHOULD be treated as interactive (i.e. have the full .bashrc
# executed). Let's check (PATH and conda info are the giveaway).

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
# Just in case conda isn't setup as expected, don't die here.
(set +e ; conda info)

# We get noisy complaints from astroplan about the IERS Bulletin A
# being too old, and this can cause some concern for those running
# this software. Avoid these by downloading fresh data,; ignore
# errors, such as due to the lack of an internet connection.
(set +e ; python "${POCS}/pocs/utils/data.py")

# Create a window running the zeromq message forwarders.
# These provide connections between message publishers and subscribers.
tmux new-window -n messaging
./start_messaging_hub.sh :messaging

# Start PAWS, the PANOPTES Administrative Web Server.
tmux new-window -n paws
./start_paws.sh :paws

# Start PEAS, the PANOPTES Environmental Analysis System
# (primarily takes care of reading from the sensors and loading
# the data into a Mongo Db).
tmux new-window -n peas
./start_peas.sh :peas

# Start POCS, the PANOPTES Observatory Control System,
# the main software we're interested in having running.
tmux new-window -n pocs
./start_pocs.sh :pocs

exit
