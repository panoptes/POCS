#!/bin/bash -ex

# Start the PANOPTES software in a detached tmux (terminal multiplexer)
# session; this enables the PANOPTES unit's owner/administrator to
# attach to that session later, see the output and take control of all
# the shells. You can attach to the session with this command:

#      tmux attach-session -t panoptes

# This script is intended to be executed in a fully initialized bash
# shell (i.e. one in which .profile, .bashrc, etc. have been executed)
# because those setup the environment variables needed.
# In particular, this script can be run by su_panoptes.sh or by
# a @reboot rule in the crontab of user $PANUSER.

if [[ -z "$BASH_VERSION" ]] ; then
  echo "This script must be run by bash."
  exit 1
fi

# And we need the shell to have the the PANOPTES environment
# setup.
if [[ -z "$PANDIR" || -z "$POCS" || -z "$PANLOG" || -z "$PAWS" ]] ; then
  echo "The PANOPTES environment variables must be set."
  echo "This script should be run from a login shell."
  exit 1
fi

echo "Running ${BASH_SOURCE[0]} at $(date)"

# cd to the directory of this script, as that is where the
# other start scripts are located.
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "Setting up logging..."

# Setup a directory for the log file from this script and from those
# it invokes. By creating a unique directory per startup, we make it
# easier to view the group of files from a single reboot.
export STARTUP_LOG_DIR_SLASH="${PANLOG}/per-run/startup/$(date +%Y%m%d-%H%M%S-%Z)/"
mkdir -p "${STARTUP_LOG_DIR_SLASH}"

LOG_NAME="$(basename "${BASH_SOURCE[0]}" .sh).log"
LOG_FILE="${STARTUP_LOG_DIR_SLASH}${LOG_NAME}"

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

# $- expands to the current option flags as specified upon invocation, by the
# set built-in command, or those set by the shell itself (such as the -i).
echo 'Shell options ($-):' "$-"

set -x

# Finally, the point of this script: create a detached (-d) tmux session
# called panoptes (-s), with a scrollback buffer of 5000 lines, where
# the shell used by new-window is bash.
tmux set-option -g history-limit 5000 \; \
     set-option -g default-shell /bin/bash \; \
     new-session -d -s panoptes ./start_panoptes_in_tmux.sh

exit
