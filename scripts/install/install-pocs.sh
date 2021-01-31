#!/usr/bin/env bash
set -e

usage() {
  echo -n "##################################################
# Install POCS and friends.
#
# Script Version: 2021-01-18
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
#   * Create
#   * Create the needed directory structure for POCS.
#   * Install docker and tools on the host computer.
#   * Fetch the docker images needed to run.
#   * Source ${PANDIR}/env if it exists.
#
# Docker Images:
#
#   ${DOCKER_BASE}/panoptes-pocs:latest
#   ${DOCKER_BASE}/aag-weather:latest
#
# The regular install is for running units.
#
# The script has been tested with a fresh install of Ubuntu Server 20.10
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
#   * 2021-01-18 (wtgee) - Simplify to only install minimal required on host,
#                           removing zsh, etc. Removed Darwin options.
#
#############################################################
 $ $(basename $0) [--user panoptes] [--pandir /panoptes]

 Options:
  USER      The PANUSER environment variable, defaults to current user (i.e. PANUSER=$USER).
  PANDIR    Default install directory, defaults to PANDIR=${PANDIR}. Saved as PANDIR
            environment variable.
"
}

# Better select prompt.
PS3="Select: "

# TODO should be checking to matching userid=1000
PANUSER=${PANUSER:-$USER}
PANDIR=${PANDIR:-/panoptes}
TAG_NAME=${TAG_NAME:-develop}
LOGFILE="${PANDIR}/logs/install-pocs.log"
OS="$(uname -s)"

DOCKER_BASE=${DOCKER_BASE:-"gcr.io/panoptes-exp"}

function make_directories() {
  sudo mkdir -p "${PANDIR}/logs"
  sudo mkdir -p "${PANDIR}/images"
  sudo chown -R "${PANUSER}":"${PANUSER}" "${PANDIR}"
}

function system_deps() {
  sudo apt-get update | sudo tee -a "${LOGFILE}" 2>&1
  sudo apt-get --yes install \
    ack \
    byobu \
    docker-compose \
    docker.io \
    htop \
    httpie \
    jq \
    openssh-server \
    wget \
    zsh | sudo tee -a "${LOGFILE}" 2>&1

  # Add an SSH key if one doesn't exist.
  if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
    echo "Adding ssh key"
    ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa"
  fi

  # Add to docker group if not already.
  sudo usermod -aG docker "${PANUSER}" | sudo tee -a "${LOGFILE}" 2>&1
}

function get_or_build_images() {
  echo "Pulling POCS docker images from Google Cloud Registry (GCR)."

  sudo docker pull "${DOCKER_BASE}/panoptes-pocs:${TAG_NAME}"
}

function install_zsh() {
  echo "Setting up zsh for a better experience."

  # Oh my zsh
  wget -q https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh -O /tmp/install-ohmyzsh.sh
  bash /tmp/install-ohmyzsh.sh --unattended

  export ZSH_CUSTOM="$HOME/.oh-my-zsh"

  # Autosuggestions plugin
  git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

  # Spaceship theme
  git clone https://github.com/denysdovhan/spaceship-prompt.git "$ZSH_CUSTOM/themes/spaceship-prompt" --depth=1
  ln -s "$ZSH_CUSTOM/themes/spaceship-prompt/spaceship.zsh-theme" "$ZSH_CUSTOM/themes/spaceship.zsh-theme"

  write_zshrc
}

function write_zshrc() {
  cat >"${HOME}/.zshrc" <<'EOT'
export PATH=$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH
export ZSH="/home/panoptes/.oh-my-zsh"
ZSH_THEME="spaceship"
plugins=(git sudo zsh-autosuggestions docker docker-compose python)
source $ZSH/oh-my-zsh.sh
unsetopt share_history
EOT
}

function do_install() {
  clear

  echo "Installing POCS software."
  echo "PANUSER: ${PANUSER}"
  echo "PANDIR: ${PANDIR}"
  echo "OS: ${OS}"
  echo "Logfile: ${LOGFILE}"

  echo "Creating directories in ${PANDIR}"
  make_directories

  echo "Installing system dependencies"
  system_deps

  get_or_build_images

  install_zsh

  echo "Please reboot your machine before using POCS."

  read -p "Reboot now? [y/N]: " -r
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
  fi
}

do_install
