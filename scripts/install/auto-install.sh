#!/bin/bash
# auto-install.sh installs git if it isn't installed, then clones POCS and
# installs its dependencies.
#
# To fetch this script from github and execute it immediately,
# run these commands:
#
# export POCS_GITHUB_USER="panoptes"
# export POCS_BRANCH="develop"
# BASE_RAW_POCS_URL="https://raw.githubusercontent.com/${POCS_GITHUB_USER}/POCS/${POCS_BRANCH}"
# export AUTO_INSTALL_RAW_URL="${BASE_RAW_POCS_URL}/scripts/install/auto-install.sh"
# wget -q -O - "${AUTO_INSTALL_RAW_URL}" | bash

################################################################################
# Functions COPIED from install-helper-functions.sh
# Print the disk location of the first arg.
function safe_which() {
  type -p "${1}" || /bin/true
}

# Print a separator bar of # characters.
function echo_bar() {
  local terminal_width="${COLUMNS}"
  if [ -z "${terminal_width}" ] && [ -n "${TERM}" ]
  then
    if [[ -n "$(safe_which tput)" ]]
    then
      terminal_width="$(tput cols)"
    elif [[ -n "$(safe_which resize)" ]]
    then
      terminal_width="$(resize 2>/dev/null | grep COLUMNS= | cut -d= -f2)"
    elif [[ -n "$(safe_which stty)" ]]
    then
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
    echo <<ENDOFMESSAGE
Running:
    sudo ${*}
You may be prompted for your password.
ENDOFMESSAGE
    (set -x ; sudo "$@")
  fi
}

function clone_or_update() {
  local -r REPO_DIR="${1}"
  local -r REPO_URL="${2}"
  local -r ORIGIN_NAME="${3}"
  local -r BRANCH="${4}"

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
    (set -x ; git clone --origin "${ORIGIN_NAME}" "${REPO_URL}" "${REPO_DIR}")
    cd "${REPO_DIR}"
    git checkout "${BRANCH}"
  else
    echo "
Pulling the latest software into the worktree at ${REPO_DIR}.
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

function ensure_ownership() {
  local -r path="${1}"
  local -r user="${2}"
  local -r group="${3}"
  echo_bar
  echo "
Ensuring that ${path} is owned by user ${user}, and by group ${group}.
"
  time do_sudo chown --recursive "${user}:${group}" "${path}"
  echo
}

function ensure_directory_ownership() {
  local -r path="${1}"
  local -r user="${2}"
  local -r group="${3}"

  echo_bar
  echo "
Ensuring that directory ${path} exists.
"
  if [ ! -d "${path}" ]
  then
    do_sudo mkdir -p "${path}"
    echo
  fi

  ensure_ownership "${path}" "${user}" "${group}"
}

# End of functions.
################################################################################

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

# I (James Synge) have noticed that if $HOME/.cache/ doesn't exist, then at some
# point during the install it gets created, but is owned by root:root, which
# then messes up later steps that attempt to use it. So, we make sure here that
# it exists with the correct ownership.

PANGROUP="$(id -gn "${PANUSER}")"
ensure_directory_ownership "${HOME}/.cache" "${PANUSER}" "${PANGROUP}"

# Do the same with PANDIR (usually /var/panoptes).
ensure_directory_ownership "${PANDIR}" "${PANUSER}" "${PANGROUP}"

if [ ! -x "$(safe_which git)" ]
then
  echo_bar
  echo "
git is not installed. Updating package cache, then installing git.
"
  do_sudo apt-get update
  echo
  echo
  do_sudo apt-get install -y git
  echo
fi

################################################################################
# Clone the POCS repo from github.

clone_or_update "${POCS}" https://github.com/panoptes/POCS.git upstream develop

# If the user specified another repo via POCS_GITHUB_USER, use that as
# the origin, and checkout the branch POCS_BRANCH.

if [[ -n "${POCS_GITHUB_USER}" && "${POCS_GITHUB_USER}" != "panoptes" ]]
then
  cd "${POCS}"
  git remote add -f origin "https://github.com/${POCS_GITHUB_USER}/POCS.git" || true
  git checkout "origin/${POCS_BRANCH:-develop}"
fi

clone_or_update \
    "${PAWS}" "https://github.com/panoptes/PAWS.git" upstream develop

echo
echo_bar
echo_bar
echo "
Executing ${POCS}/scripts/install/install-dependencies.sh, which will
install the tools needed to run POCS.
"

${POCS}/scripts/install/install-dependencies.sh

# QUESTION: Should we add these lines here:
# source $PANDIR/set-panoptes-env.sh
# cd $POCS
# python setup.py install
# pytest --test-databases=all --solve

exit $?
