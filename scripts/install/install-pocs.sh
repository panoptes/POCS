#!/usr/bin/env bash
set -e

usage() {
  echo -n "##################################################
# Install POCS and friends.
#
# Script Version: 2020-07-09
#
# This script is designed to install the PANOPTES Observatory
# Control System (POCS) on a cleanly installed Ubuntu system.
#
# This script is meant for quick & easy install via:
#
#   $ curl -fsSL https://install.projectpanoptes.org > install-pocs.sh
#   $ bash install-pocs.sh
#   or
#   $ wget -qO- https://install.projectpanoptes.org > install-pocs.sh
#   $ bash install-pocs.sh
#
# The script will do the following:
#
#   * Create the needed directory structure.
#   * Ensure that docker and docker-compose are installed.
#   * Fetch and/or build the docker images needed to run.
#   * If in "developer" mode, clone user's fork and set panoptes upstream.
#   * Write the environment variables to ${PANDIR}/env
#
# Docker Images:
#
#   ${DOCKER_BASE}/panoptes-utils
#   ${DOCKER_BASE}/pocs
#
# The script will ask if it should be installed in "developer" mode or not.
#
# The regular install is for running units and will not create local (to the
# host system) copies of the files.
#
# The "developer" mode will ask for a github username and will clone and
# fetch the repos. The $(docker/setup-local-enviornment.sh) script will then
# be run to build the docker images locally.
#
# If not in "developer" mode, the docker images will be pulled from GCR.
#
# The script has been tested with a fresh install of Ubuntu 20.04
# but may work on other linux systems.
#
# Changes:
#   * 2020-07-05 - Initial release of versioned script.
#   * 2020-07-06 (wtgee) - Fix the writing of the env file. Cleanup.
#   * 2020-07-08 (wtgee) - Better test for ssh access for developer.
#   * 2020-07-09 (wtgee) - Fix conditional for writing shell rc files. Use 3rd
#                           party docker-compose (linuxserver.io) for arm.
#
#############################################################
 $ $(basename $0) [--developer] [--user panoptes] [--pandir /var/panoptes]

 Options:
  DEVELOPER Install POCS in developer mode, default False.

 If in DEVELOPER mode, the following options are also available:
  USER      The PANUSER environment variable, defaults to current user (i.e. PANUSER=$USER).
  PANDIR    Default install directory, defaults to PANDIR=${PANDIR}. Saved as PANDIR
            environment variable.
"
}

# Better select prompt.
PS3="Select: "

DEVELOPER=${DEVELOPER:-false}
PANUSER=${PANUSER:-$USER}
PANDIR=${PANDIR:-/var/panoptes}
LOGFILE="${PANDIR}/install-pocs.log"
OS="$(uname -s)"
ARCH="$(uname -m)"
ENV_FILE="${PANDIR}/env"

GITHUB_USER="panoptes"
GITHUB_URL="https://github.com/${GITHUB_USER}"

PANOPTES_UPSTREAM_URL="https://github.com/panoptes"

# Repositories to clone.
REPOS=("POCS" "panoptes-utils" "panoptes-tutorials")

DOCKER_COMPOSE_INSTALL="https://raw.githubusercontent.com/linuxserver/docker-docker-compose/master/run.sh"
DOCKER_BASE=${DOCKER_BASE:-"gcr.io/panoptes-exp"}

while [[ $# -gt 0 ]]; do
  key="$1"
  case ${key} in
  --developer)
    DEVELOPER=true
    shift # past bool argument
    ;;
  --install-unit)
    DEVELOPER=false
    shift # past bool argument
    ;;
  -u | --user)
    PANUSER="$2"
    shift # past argument
    shift # past value
    ;;
  -d | --pandir)
    PANDIR="$2"
    shift # past argument
    shift # past value
    ;;
  -h | --help)
    PANDIR="$2"
    usage
    return
    ;;
  esac
done

if ! ${DEVELOPER}; then
  echo "How would you like to install the unit?"
  select mode in "Developer" "PANOPTES Unit"; do
    case ${mode} in
    Developer)
      echo "Enabling developer mode. Note that you will need your GitHub username to proceed."
      DEVELOPER=true
      break
      ;;
    "PANOPTES Unit")
      echo "Installing POCS for a PANOPTES unit."
      break
      ;;
    esac
  done
fi

if "${DEVELOPER}"; then
  echo "To install POCS as a developer make sure you have first forked the following repositories:"
  echo ""
  echo "    https://github.com/panoptes/POCS"
  echo "    https://github.com/panoptes/panoptes-utils"
  echo "    https://github.com/panoptes/panoptes-tutorials"
  echo ""
  echo "You will also need to have an ssh key set up on github.com."
  echo "See https://docs.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh"

  read -p "Github User [panoptes]: " GITHUB_USER

  # If a different user, make sure we can access github as that user, otherwise exit.
  if test "${GITHUB_USER}" != "panoptes"; then
    echo "Testing github ssh access for user: ${GITHUB_USER}"

    # Test for ssh access
    if [[ $(ssh -T git@github.com 2>&1) =~ "success" ]]; then
      GITHUB_URL="git@github.com:${GITHUB_USER}"
    else
      echo "Can't ssh to github.com. Have you set up your ssh keys?"
      echo "See https://docs.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh"
      return
    fi
  fi
fi

function command_exists() {
  # https://gist.github.com/gubatron/1eb077a1c5fcf510e8e5
  # this should be a very portable way of checking if something is on the path
  # usage: "if command_exists foo; then echo it exists; fi"
  type "$1" &>/dev/null
}

function make_directories() {
  if [[ ! -d "${PANDIR}" ]]; then
    # Make directories and make PANUSER the owner.
    sudo mkdir -p "${PANDIR}"
  else
    echo "Would you like to continue with the existing directory?"
    select yn in "Yes" "No"; do
      case ${yn} in
      Yes)
        echo "Proceeding with existing directory"
        break
        ;;
      No)
        echo "Exiting script"
        return
        ;;
      esac
    done
  fi

  sudo mkdir -p "${PANDIR}/logs"
  sudo mkdir -p "${PANDIR}/images"
  sudo mkdir -p "${PANDIR}/config_files"
  sudo mkdir -p "${PANDIR}/.key"
  sudo chown -R "${PANUSER}":"${PANUSER}" "${PANDIR}"
}

function setup_env_vars() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Writing environment variables to ${ENV_FILE}"
    cat >>"${ENV_FILE}" <<EOF
#### Added by install-pocs script ####
export PANUSER=${PANUSER}
export PANDIR=${PANDIR}
export POCS=${PANDIR}/POCS
export PANLOG=${PANDIR}/logs
#### End install-pocs script ####
EOF

    # Source the files in the shell.
    SHELLS=(".bashrc" ".zshrc")

    for SHELL_RC in "${SHELLS[@]}"; do
      SHELL_RC_PATH="$HOME/${SHELL_RC}"
      if test -f "${SHELL_RC_PATH}"; then
        # Check if we have already added the file.
        if ! grep -qm 1 ". ${PANDIR}/env" "${SHELL_RC_PATH}"; then
          printf "\n. ${PANDIR}/env\n" >>"${SHELL_RC_PATH}"
        fi
      fi
    done
  fi
}

function system_deps() {
  if [[ "${OS}" == "Linux" ]]; then
    sudo apt-get update >>"${LOGFILE}" 2>&1
    sudo apt-get --yes install \
      wget curl git openssh-server ack jq httpie byobu \
      >>"${LOGFILE}" 2>&1
  elif [[ "${OS}" == "Darwin" ]]; then
    sudo brew update | sudo tee -a "${LOGFILE}"
    sudo brew install \
      wget curl git jq httpie |
      sudo tee -a "${LOGFILE}"
  fi

  # Add an SSH key if one doesn't exist.
  if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
    echo "Adding ssh key"
    ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa"
  fi
}

function get_repos() {
  echo "Cloning ${REPOS}"
  for repo in "${REPOS[@]}"; do
    if [[ ! -d "${PANDIR}/${repo}" ]]; then
      cd "${PANDIR}"
      echo "Cloning ${GITHUB_URL}/${repo}"
      # Just redirect the errors because otherwise looks like it hangs.
      git clone --single-branch --quiet "${GITHUB_URL}/${repo}.git" &>>"${LOGFILE}"

      # Set panoptes as upstream if clone succeeded.
      if [ $? -eq 0 ]; then
        cd "${repo}"
        git remote add upstream "${PANOPTES_UPSTREAM_URL}/${repo}"
      fi
    else
      echo "${repo} already exists in ${PANDIR}. No auto-update for now, skipping repo."
    fi
  done
}

function get_docker() {
  if ! command_exists docker; then
    echo "Installing Docker"
    if [[ "${OS}" == "Linux" ]]; then
      /bin/bash -c "$(wget -qO- https://get.docker.com)" &>>"${LOGFILE}"

      echo "Adding ${PANUSER} to docker group"
      sudo usermod -aG docker "${PANUSER}" >>"${LOGFILE}" 2>&1
    elif [[ "${OS}" == "Darwin" ]]; then
      brew cask install docker
      echo "Adding ${PANUSER} to docker group"
      sudo dscl -aG docker "${PANUSER}"
    fi
  fi

  if ! command_exists docker-compose; then
    echo "Installing docker-compose"
    sudo wget -q "${DOCKER_COMPOSE_INSTALL}" -O /usr/local/bin/docker-compose
    sudo chmod a+x /usr/local/bin/docker-compose
  fi
}

function get_or_build_images() {
  if ${DEVELOPER}; then
    echo "Building local PANOPTES docker images."

    cd "${PANDIR}/POCS"
    ./docker/setup-local-environment.sh
  else
    echo "Pulling PANOPTES docker images from Google Cloud Registry (GCR)."

    sudo docker pull "${DOCKER_BASE}/panoptes-pocs:latest"
    sudo docker pull "${DOCKER_BASE}/panoptes-utils:latest"
    sudo docker pull "${DOCKER_BASE}/aag-weather:latest"
  fi
}

function do_install() {
  clear

  echo "Installing PANOPTES software."
  if ${DEVELOPER}; then
    echo "**** Developer Mode ****"
    echo "GITHUB_USER=${GITHUB_USER}"
  fi
  echo "PANUSER: ${PANUSER}"
  echo "PANDIR: ${PANDIR}"
  echo "OS: ${OS}"
  echo "Logfile: ${LOGFILE}"

  echo "Creating directories in ${PANDIR}"
  make_directories

  echo "Setting up environment variables in ${ENV_FILE}"
  setup_env_vars

  echo "Installing system dependencies"
  system_deps

  echo "Installing docker and docker-compose"
  get_docker

  if ${DEVELOPER}; then
    echo "Cloning PANOPTES source code"
    get_repos
  fi

  get_or_build_images

  echo "Please reboot your machine before using POCS."

  read -p "Reboot now? [y/N]: " -r
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
  fi
}

do_install
