#!/bin/bash
# auto-install.sh installs git if it isn't installed, then clones POCS and
# installs its dependencies.
#
# To fetch this from github and execute it immediately, run this command:
#
#    bash <(curl -s https://raw.githubusercontent.com/panoptes/POCS/develop/scripts/install/auto-install.sh)

# Exit immediately if a command fails.
set -e

################################################################################
# Functions COPIED from install-helper-functions.sh
# Print the disk location of the first arg.
function safe_which() {
  type -p "${1}" || /bin/true
}

################################################################################

function do_sudo() {
  if [ "$(id -u -n)" == "root" ] ; then
    echo "Running ${*}"
    "$@"
  else
    echo "Running sudo ${*}; you may be prompted for your password."
    (set -x ; sudo "$@")
  fi
}

# COPIED from default-env-vars.sh
[[ -z "${PANUSER}" ]] && export PANUSER="panoptes"      # Default user
[[ -z "${PANDIR}" ]] && export PANDIR="/var/panoptes"   # Main Dir
[[ -z "${PANLOG}" ]] && export PANLOG="${PANDIR}/logs"  # Log files
[[ -z "${POCS}" ]] && export POCS="${PANDIR}/POCS"      # Main Observatory Control
[[ -z "${PAWS}" ]] && export PAWS="${PANDIR}/PAWS"      # Web Interface

if [[ "$(whoami)" != "${PANUSER}" ]] ; then
  echo >2 "Please run this script as ${PANUSER}, not as $(whoami)"
  exit 1
fi

# Let's assume we'll need to run apt-get install, so first run apt-get update
# which will refresh caches used during apt-get install.
do_sudo apt-get update

if [ ! -x "$(safe_which git)" ]
then
  echo "git is not installed, so installing it..."
  do_sudo apt-get install -y git
fi

echo "Ensuring that ${PANDIR} exists"
if [ ! -d "${PANDIR}" ]
then
  do_sudo mkdir -p "${PANDIR}"
fi

echo "Ensuring that ${PANDIR} is owned by user ${PANUSER}"
do_sudo chown "${PANUSER}" "${PANDIR}"

cd "${PANDIR}"

if [ ! -d "${POCS}/.git" ]
then
  if [ -d "${POCS}" ]
  then
    echo 2> "
The POCS directory (${POCS}) already exists, but doesn't appear
to be a valid git repository. Please remove it (or move it out
of the way) and re-run this script.
"
    exit 1
  fi
  echo "Cloning the POCS git repository into ${POCS}"
  git clone https://github.com/panoptes/POCS.git "${POCS}"
  cd "${POCS}"
  git checkout master
else
  echo "Pulling the latest software into the POCS worktree (${POCS})"
  cd "${POCS}"
  git fetch --all
  git checkout master
  git pull
fi

echo "
Executing ${POCS}/scripts/install/install-dependencies.sh, which will
install the tools needed to run POCS.
"

${POCS}/scripts/install/install-dependencies.sh
