#!/bin/bash -ex

if [[ -z "$BASH_VERSION" ]] ; then
  echo "This script must be run by bash."
  exit 1
fi

# This script is designed to be run inside tmux, launched by
# tmux_launch.sh. Make sure that is so.
echo "Running ${BASH_SOURCE[0]} at $(date)"
if [[ -z "${STARTUP_LOG_DIR_SLASH}" ]] ; then
  echo "This script must be run by tmux_launch.sh"
  exit 1
fi

# And we need the shell to have the the PANOPTES environment
# setup.
if [[ -z "$PANDIR" || -z "$POCS" || -z "$PANLOG" || -z "$PAWS" ]] ; then
  echo "The PANOPTES environment variables must be set."
  echo "This script should be run from a login shell."
  exit 1
fi

LOG_NAME="$(basename "${BASH_SOURCE[0]}" .sh).log"
LOG_FILE="${STARTUP_LOG_DIR_SLASH}${LOG_NAME}"

echo "Will log to ${LOG_FILE}"

exec 2> "${LOG_FILE}"  # send stderr to a log file
exec 1>&2              # send stdout to the same log file

set +x
# set +x turns off the verbose logging of each line. This makes
# the following block of echoes easier to read in the log file.

echo "Running ${BASH_SOURCE[0]} at $(date)"

# Record important debugging info into the log file. These
# environment variables do NOT all have to be set. Note that
# this script is executed inside of a tmux session, which
# SHOULD be treated as interactive (i.e. have the full .bashrc
# executed). Let's check (PATH and conda info are the giveaway).

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
# $- expands to the current option flags as specified upon invocation, by the
# set built-in command, or those set by the shell itself (such as the -i).
echo '$-:' "$-"
# Just in case conda isn't setup as expected, don't die here.
(set +e ; conda info)

function create_and_init_window() {
    local -r WINDOW="${1}"
    shift
    local -r SCRIPT="${1}"
    shift
    local -r LOG_NAME="$(basename "${SCRIPT}" .sh)-in-${WINDOW}.log"
    local -r LOCAL_LOG_FILE="${STARTUP_LOG_DIR_SLASH}${LOG_NAME}"

    echo "Will run ${SCRIPT} in window ${WINDOW}, logging to ${LOCAL_LOG_FILE}"

    # Create the window.
    tmux new-window -n "${WINDOW}"

    # Give the window a little while to start up (i.e. to start bash, and
    # for bash to run the initialization script). 8 seconds was chosen
    # based on how long it takes on PAN006 for a new tmux window to
    # print the bash prompt.
    sleep 8s

    # Run the script in a separate process, and prevent it from being
    # killed when this script ends.
    nohup "./${SCRIPT}" ":${WINDOW}" "${@}" > "${LOCAL_LOG_FILE}" 2>&1 &

    # And give that script a couple of seconds to get started. This
    # may not be strictly necessary.
    sleep 2s
}

# Resume verbose logging in order to support debugging these scripts.
set -x

# We get noisy complaints from astroplan about the IERS Bulletin A
# being too old, and this can cause some concern for those running
# this software. Avoid these by downloading fresh data,; ignore
# errors, such as due to the lack of an internet connection.
(set +e ; python "${POCS}/pocs/utils/data.py")

# Create a window running the zeromq message forwarders.
# These provide connections between message publishers and subscribers.
create_and_init_window messaging start_messaging_hub.sh

# Start PAWS, the PANOPTES Administrative Web Server.
create_and_init_window paws start_paws.sh

# Monitor the PEAS log file.
create_and_init_window log_peas start_log_viewer.sh \
    "${PANLOG}/peas_shell-all.log"

# Monitor the POCS log file.
create_and_init_window log_pocs start_log_viewer.sh \
    "${PANLOG}/pocs_shell-all.log"

# Start PEAS, the PANOPTES Environmental Analysis System
# (primarily takes care of reading from the sensors and loading
# the data into a Mongo Db).
create_and_init_window peas start_peas.sh

# Start POCS, the PANOPTES Observatory Control System,
# the main software we're interested in having running.
create_and_init_window pocs start_pocs.sh

exit
