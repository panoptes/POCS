#!/bin/bash
# auto-install.sh installs git if it isn't installed, then clones POCS and
# installs its dependencies.
#
# To fetch this script from github and execute it immediately,
# run these commands:
#
# AUTO_INSTALL_GITHUB_USER="panoptes"
# AUTO_INSTALL_BRANCH="develop"
# BASE_RAW_POCS_URL="https://raw.githubusercontent.com/${AUTO_INSTALL_GITHUB_USER}/POCS/${AUTO_INSTALL_BRANCH}"
# export AUTO_INSTALL_RAW_URL="${BASE_RAW_POCS_URL}/scripts/install/auto-install.sh"
# wget -q -O - "${AUTO_INSTALL_RAW_URL}" | bash

################################################################################
# Env vars used for debugging of this script; these allow you to point to your
# fork of POCS on github, so that you can download your fork instead of the
# primary repo. There is no support for doing the same with PAWS.

[[ -z "${POCS_GITHUB_USER}" ]] && export POCS_GITHUB_USER="panoptes"
[[ -z "${POCS_GIT_URL}" ]] && export POCS_GIT_URL="https://github.com/${POCS_GITHUB_USER}/POCS.git"
[[ -z "${POCS_BRANCH}" ]] && export POCS_BRANCH="develop"

################################################################################
# Functions COPIED from install-helper-functions.sh
# Print the disk location of the first arg.
function safe_which() {
  type -p "${1}" || /bin/true
}

# Print a separator bar of # characters.
function echo_bar() {
  local terminal_width="${COLUMNS}"
  if [ -z "${terminal_width}" ] && [ -n "${TERM}" ] && [ -t 0 ] ; then
    if [[ -n "$(which resize)" ]] ; then
      terminal_width="$(resize 2>/dev/null | grep COLUMNS= | cut -d= -f2)"
    elif [[ -n "$(which stty)" ]] ; then
      terminal_width="$(stty size 2>/dev/null | cut '-d ' -f2)"
    fi
  fi
  printf "%${terminal_width:-80}s\n" | tr ' ' '#'
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

function clone_or_update() {
  local -r REPO_DIR="${1}"
  local -r REPO_URL="${2}"
  local -r BRANCH="${3}"

  echo_bar

  if [ ! -d "${REPO_DIR}/.git" ]
  then
    if [ -d "${REPO_DIR}" ]
    then
      echo 2> "
The directory (${REPO_DIR}) already exists, but doesn't appear
to be a valid git repository. Please remove it (or move it out
of the way) and re-run this script.
  "
      exit 1
    fi
    echo "
Cloning ${REPO_URL} into ${REPO_DIR}
"
    (set -x ; git clone "${REPO_URL}" "${REPO_DIR}")
    cd "${REPO_DIR}"
    git checkout "${BRANCH}"
  else
    echo "
Pulling the latest software into the worktree at ${REPO_DIR}
"
    cd "${REPO_DIR}"
    git fetch --all
    git checkout "${BRANCH}"
    git pull
  fi
}

function maybe_print_example() {
  if [[ -n "${AUTO_INSTALL_RAW_URL}" ]]
  then
    >&2 cat <<ENDOFMESSAGE
For example:

  wget -q -O - "${AUTO_INSTALL_RAW_URL}" | bash

ENDOFMESSAGE
  fi
}

# Exit immediately if a command fails:
set -e

# COPIED from default-env-vars.sh
[[ -z "${PANUSER}" ]] && export PANUSER="panoptes"      # Default user
[[ -z "${PANDIR}" ]] && export PANDIR="/var/panoptes"   # Main Dir
[[ -z "${PANLOG}" ]] && export PANLOG="${PANDIR}/logs"  # Log files
[[ -z "${POCS}" ]] && export POCS="${PANDIR}/POCS"      # Main Observatory Control
[[ -z "${PAWS}" ]] && export PAWS="${PANDIR}/PAWS"      # Web Interface

# Do we need to create the user PANUSER?

if ! id -u "${PANUSER}" 2>/dev/null 1>/dev/null
then
  >&2 cat <<ENDOFMESSAGE
The user ${PANUSER} doesn't exist yet. Please create it by running:

  sudo adduser --shell /bin/bash --add_extra_groups ${PANUSER}

You will be prompted to enter a password for this new user. You may also be
prompted to provide contact info as if this were a user on a shared computer
(e.g. Full Name and Home Phone). Press Enter to leave these unset.

After the command completes, we need to ensure that the user is a
member of some key groups:

  sudo usermod --append --groups adm,dialout,plugdev,sudo ${PANUSER}

Next, login as ${PANUSER} and re-execute the command you used to
run this script.
ENDOFMESSAGE

  maybe_print_example
  exit 1
fi

# Do we need to login as the user PANUSER?

if [[ "$(whoami)" != "${PANUSER}" ]]
then
  echo >&2 "
This script should be executed by the user ${PANUSER}, not as $(whoami).
Please login as ${PANUSER} and re-execute the command you used to
run this script.
"

  maybe_print_example
  exit 1
fi

# Let's assume we'll need to run apt-get install, so first run apt-get update
# which will refresh caches used during apt-get install.
echo_bar
echo
do_sudo apt-get update
echo

if [ ! -x "$(safe_which git)" ]
then
  echo_bar
  echo "
git is not installed, so installing it...
"
  do_sudo apt-get install -y git
  echo
fi

echo_bar
echo "
Ensuring that ${PANDIR} exists
"
if [ ! -d "${PANDIR}" ]
then
  do_sudo mkdir -p "${PANDIR}"
  echo
fi

PANGROUP="$(id -gn "${PANUSER}")"

echo_bar
echo "
Ensuring that ${PANDIR} is owned by user ${PANUSER}, and by group ${PANGROUP}
"
do_sudo chown --recursive "${PANUSER}:${PANGROUP}" "${PANDIR}"
echo

clone_or_update "${POCS}" "${POCS_GIT_URL}" "${POCS_BRANCH}"
clone_or_update "${PAWS}" "https://github.com/panoptes/PAWS.git" "develop"

echo
echo_bar
echo_bar
echo "
Executing ${POCS}/scripts/install/install-dependencies.sh, which will
install the tools needed to run POCS.
"

${POCS}/scripts/install/install-dependencies.sh

exit $?
