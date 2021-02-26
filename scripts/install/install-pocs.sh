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

# run docker-compose:
#  * copy pocs.yaml and docker-compose.yaml from container to host
#  * set PANOPTES_CONFIG_FILE=conf_files above

# TODO should be checking to matching userid=1000
PANUSER="${PANUSER:-$USER}"
PANDIR="${PANDIR:-/panoptes}"
HOST="${HOST:-pocs-control-box}"
TAG_NAME=${TAG_NAME:-develop}
LOGFILE="${PANDIR}/logs/install-pocs.log"
OS="$(uname -s)"
CONDA_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh"
CONDA_ENV_NAME=conda-pocs

DOCKER_BASE=${DOCKER_BASE:-"gcr.io/panoptes-exp"}

function make_directories() {
  echo "Creating directories in ${PANDIR}"
  sudo mkdir -p "${PANDIR}/logs"
  sudo mkdir -p "${PANDIR}/images"
  sudo mkdir -p "${PANDIR}/json_store"
  sudo mkdir -p "${PANDIR}/conf_files"
  sudo mkdir -p "${PANDIR}/notebooks"
  sudo chown -R "${PANUSER}":"${PANUSER}" "${PANDIR}"
}

function which_version() {
  PS3='Where are you installing?: '
  versions=("Control box" "Camera Box")
  select ver in "${versions[@]}"; do
    case $ver in
    "Control box")
      HOST="pocs-control-box"
      break
      ;;
    "Camera box")
      HOST="pocs-camera-box"
      break
      ;;
    *) echo "invalid option $REPLY" ;;
    esac
  done

  echo "Setting hostname to ${HOST}"
  sudo hostnamectl set-hostname "$HOST"
}

function system_deps() {
  sudo apt-get update --fix-missing
  sudo apt-get -y full-upgrade
  sudo apt-get --yes install \
    ack \
    byobu \
    gcc \
    htop \
    make \
    wget \
    zsh
  sudo apt-get -y autoremove

  # Use zsh
  sudo chsh --shell /usr/bin/zsh "${PANUSER}"

  # Add an SSH key if one doesn't exist.
  if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
    echo "Adding ssh key"
    ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa"
  fi

}

function install_docker() {
  wget -q https://get.docker.com -O get-docker.sh
  bash get-docker.sh

  # Add to docker group if not already.
  sudo usermod -aG docker "${PANUSER}"

  "${PANDIR}/conda/envs/${CONDA_ENV_NAME}/bin/pip" install docker-compose
}

function get_or_build_images() {
  echo "Pulling POCS docker images from Google Cloud Registry (GCR)."

  sudo docker pull "${DOCKER_BASE}/panoptes-pocs:${TAG_NAME}"

  if [ $HOST == "pocs-control-box" ]; then
    # Copy the docker-compose file
    sudo docker run --rm -it \
      -v "${PANDIR}:/temp" \
      "${DOCKER_BASE}/panoptes-pocs:${TAG_NAME}" \
      "cp /app/docker/docker-compose.yaml /temp/pocs-compose.yaml"
    sudo chown "${PANUSER}:${PANUSER}" pocs-compose.yaml

    # Copy the docker-compose file
    sudo docker run --rm -it \
      -v "${PANDIR}:/temp" \
      "${DOCKER_BASE}/panoptes-pocs:${TAG_NAME}" \
      "cp /app/docker/conf_files/pocs.yaml /temp/conf_files/pocs.yaml"
    sudo chown "${PANUSER}:${PANUSER}" conf_files/pocs.yaml
  fi
}

function install_conda() {
  echo "Installing miniforge conda"

  wget "${CONDA_URL}" -O install-miniforge.sh
  /bin/sh install-miniforge.sh -b -f -p "${PANDIR}/conda"
  # Initialize conda for the shells.
  "${PANDIR}/conda/bin/conda" init bash
  "${PANDIR}/conda/bin/conda" init zsh

  "${PANDIR}/conda/bin/conda" create -y -n "${CONDA_ENV_NAME}" python=3

  # Activate by default
  echo "conda activate ${CONDA_ENV_NAME}" >>"${HOME}/.zshrc"

  # Install panoptes-utils (so we get panoptes-config-server)
  "${PANDIR}/conda/envs/${CONDA_ENV_NAME}/bin/pip" install docker-compose
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
  cat >"${HOME}/.zshrc" <<EOT

export PATH="\$HOME/bin:\$HOME/.local/bin:/usr/local/bin:\$PATH"
export ZSH="/home/${PANUSER}/.oh-my-zsh"
export PANDIR="${PANDIR}"

ZSH_THEME="spaceship"

plugins=(git sudo zsh-autosuggestions docker docker-compose python)
source \$ZSH/oh-my-zsh.sh
unsetopt share_history

EOT

  # Enable byobu by defaul on the shells.
  cat >>"${HOME}/.profile" <<EOT
_byobu_sourced=1 . /usr/bin/byobu-launch 2>/dev/null || true
EOT
}

function do_install() {
  clear

  which_version

  echo "Installing POCS software for ${HOST}"
  echo "PANUSER: ${PANUSER}"
  echo "PANDIR: ${PANDIR}"
  echo "HOST: ${HOST}"
  echo "OS: ${OS}"
  echo "Logfile: ${LOGFILE}"

  make_directories

  echo "Installing system dependencies"
  system_deps

  install_zsh

  install_conda

  install_docker

  get_or_build_images

  echo "Please reboot your machine before using POCS."

  read -p "Reboot now? [y/N]: " -r
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
  fi
}

do_install
