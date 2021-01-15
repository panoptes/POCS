#!/usr/bin/env bash
set -e

usage() {
  echo -n "##################################################
# Install POCS and friends.
#
# Script Version: 2020-11-08
#
# This script is designed to install the PANOPTES Observatory
# Control System (POCS) on a cleanly installed Ubuntu system
# (ideally on a Raspberry Pi).
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
#   * Install docker and tools on the host computer.
#   * Install zsh and oh-my-zsh on the host computer.
#   * Install anaconda (via miniforge) on the host computer.
#   * Create the needed directory structure for POCS.
#   * Fetch and/or build the docker images needed to run.
#   * If in 'developer' mode, clone user's fork and set panoptes upstream.
#   * Write the environment variables to ${PANDIR}/env
#
# Docker Images:
#
#   ${DOCKER_BASE}/panoptes-utils
#   ${DOCKER_BASE}/pocs
#
# The script will ask if it should be installed in 'developer' mode or not.
#
# The regular install is for running units and will not create local (to the
# host system) copies of the files.
#
# The 'developer' mode will ask for a github username and will clone and
# fetch the repos. The $(docker/setup-local-enviornment.sh) script will then
# be run to build the docker images locally.
#
# If not in 'developer' mode, the docker images will be pulled from GCR.
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
#   * 2020-07-27 (wtgee) - Cleanup and consistency for Unit install.
#   * 2020-11-08 (wtgee) - Add zsh, anaconda. Docker from apt.
#   * 2021-01-15 (wtgee) - Simplify to only install minimal required on host,
#                           removing zsh, etc.
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

# TODO should be checking to matching userid=1000
PANUSER=${PANUSER:-$USER}
PANDIR=${PANDIR:-/var/panoptes}
LOGFILE="${PANDIR}/install-pocs.log"
OS="$(uname -s)"

DOCKER_BASE=${DOCKER_BASE:-"gcr.io/panoptes-exp"}

function command_exists() {
  # https://gist.github.com/gubatron/1eb077a1c5fcf510e8e5
  # this should be a very portable way of checking if something is on the path
  # usage: "if command_exists foo; then echo it exists; fi"
  type "$1" &>/dev/null
}

function make_directories() {
  sudo mkdir -p "${PANDIR}/logs"
  sudo mkdir -p "${PANDIR}/images"
  sudo mkdir -p "${PANDIR}/.key"
  sudo chown -R "${PANUSER}":"${PANUSER}" "${PANDIR}"
}

function system_deps() {
  if [[ "${OS}" == "Linux" ]]; then
    sudo apt-get update | sudo tee -a "${LOGFILE}" 2>&1
    sudo apt-get --yes install \
      ack \
      byobu \
      curl \
      docker.io \
      docker-compose \
      git \
      htop \
      httpie \
      jq \
      openssh-server \
      speedometer \
      vim-nox \
      wget | sudo tee -a "${LOGFILE}" 2>&1
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

  # Add to docker group if not already.
  sudo usermod -aG docker "${PANUSER}" | sudo tee -a "${LOGFILE}" 2>&1

  # Append some statements to .zshrc
  cat <<EOF >>/home/panoptes/.bashrc
export LANG="en_US.UTF-8"

# POCS
export PANDIR=/var/panoptes
export POCS=/var/panoptes/POCS
EOF
}

function get_or_build_images() {
  echo "Pulling PANOPTES docker images from Google Cloud Registry (GCR)."

  sudo docker pull "${DOCKER_BASE}/panoptes-pocs:develop"
  sudo docker pull "${DOCKER_BASE}/aag-weather:latest"
  sudo docker pull quay.io/vektorlab/ctop:latest
}

function do_install() {
  clear

  echo "Installing PANOPTES software."
  echo "PANUSER: ${PANUSER}"
  echo "PANDIR: ${PANDIR}"
  echo "OS: ${OS}"
  echo "Logfile: ${LOGFILE}"

  echo "Creating directories in ${PANDIR}"
  make_directories

  echo "Installing system dependencies"
  system_deps

  get_or_build_images

  echo "Please reboot your machine before using POCS."

  read -p "Reboot now? [y/N]: " -r
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
  fi
}

do_install
