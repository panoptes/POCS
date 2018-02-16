#!/bin/sh -ex

# Start running the script tmux_launch as user $PANUSER in a login
# shell, i.e. one that will run that user's shell initialization
# scripts, such as .profile and/or .bashrc.

# This script is designed to be run from /etc/rc.local (or similar)
# by the user root, after the PANOPTES environment variables have
# been set.

# Put the date & time into the log (e.g. /tmp/su_panoptes.log).
echo
echo "Running ${0} at $(/bin/date)"
echo

# Make sure that the PANOPTES environment variables have been setup
# (e.g. by /etc/profile).
if [[ -z "${POCS}" || -z "${PANUSER}" ]] ; then
  echo "The POCS and PANUSER environment variables must be set!"
  exit 1
fi

# Execute tmux_launch.sh in a login shell for user $PANUSER.
/bin/su --login --command \
     "${POCS}/scripts/startup/tmux_launch.sh" "${PANUSER}"

echo "Done at $(/bin/date)"
