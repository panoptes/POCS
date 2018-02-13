#!/bin/sh -ex

# Start the PANOPTES software running as user $PANUSER in a detached
# tmux session; this enables an admin to attach to that session
# later, see the output and take control of all the shells.

# Put the date & time into the log (e.g. /tmp/su_panoptes.log).
echo
echo "Running ${0} at $(/bin/date)"
echo

# Execute tmux_launch.sh in a login shell for user $PANUSER.
/bin/su --login --command \
     "${POCS}/scripts/startup/tmux_launch.sh" "${PANUSER}"

echo "Done at $(/bin/date)"
