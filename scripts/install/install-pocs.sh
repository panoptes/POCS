#!/usr/bin/env bash
set -e

usage() {
  echo -n "##################################################
# Install POCS and friends.
#
# Script Version: 2021-07-15
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
PANUSER="${PANUSER:-$USER}"
PANDIR="${PANDIR:-${HOME}/pocs}"
UNIT_NAME="pocs"
HOST="${HOST:-pocs-control-box}"
LOGFILE="${PANDIR}/logs/install-pocs.log"
OS="$(uname -s)"
CONDA_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh"
CONDA_ENV_NAME=conda-pocs
DEV_BOX=false
DEFAULT_GROUPS="dialout,plugdev,input,sudo"
NTP_SERVER=192.168.8.1

DOCKER_BASE=${DOCKER_BASE:-"gcr.io/panoptes-exp"}
DOCKER_TAG=${DOCKER_TAG:-"develop"}

function make_directories() {
  echo "Creating directories in ${PANDIR}"
  sudo mkdir -p "${PANDIR}/logs"
  sudo mkdir -p "${PANDIR}/images"
  sudo mkdir -p "${PANDIR}/json_store"
  sudo mkdir -p "${PANDIR}/keys"
  sudo mkdir -p "${PANDIR}/notebooks"
  sudo mkdir -p "${PANDIR}/conf_files"
  sudo chown -R "${PANUSER}":"${PANUSER}" "${PANDIR}"
}

function name_me() {
  read -p 'What is the name of your unit (e.g. "PAN001" or "Maia")? ' UNIT_NAME
}

function which_docker() {
  read -p 'What docker image tag would you like to use (default: develop)? ' DOCKER_TAG
}

function which_version() {
  PS3='Where are you installing?: '
  versions=("Control box" "Camera box" "My computer")
  select ver in "${versions[@]}"; do
    case $ver in
    "Control box")
      HOST="${UNIT_NAME}-control-box"
      break
      ;;
    "Camera box")
      HOST="${UNIT_NAME}-camera-box"
      break
      ;;
    "My computer")
      echo "Installing on personal computer"
      DEV_BOX=true
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

  # Raspberry Pi stuff
  if [ "$(uname -m)" = "aarch64" ]; then
    echo "Installing Raspberry Pi tools"
    sudo apt-get -y install rpi.gpio-common linux-tools-raspi
  fi

  sudo apt-get -y full-upgrade
  sudo apt-get --yes install \
    ack \
    byobu \
    gcc \
    htop \
    httpie \
    make \
    nano \
    neovim \
    sshfs \
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
  sudo usermod -aG docker "${PANUSER}"
  rm get-docker.sh
}

function get_or_build_images() {
  echo "Pulling POCS docker images from Google Cloud Registry (GCR)."

  sudo docker pull "${DOCKER_BASE}/panoptes-pocs:${DOCKER_TAG}"

  if [[ $HOST == *-control-box ]]; then
    # Copy the docker-compose file
    sudo docker run --rm -it \
      -v "${PANDIR}:/temp" \
      "${DOCKER_BASE}/panoptes-pocs:${DOCKER_TAG}" \
      "cp /panoptes-pocs/docker/docker-compose.yaml /temp/docker-compose.yaml"
    sudo chown "${PANUSER}:${PANUSER}" "${PANDIR}/docker-compose.yaml"

    # Copy the config file
    sudo docker run --rm -it \
      -v "${PANDIR}:/temp" \
      "${DOCKER_BASE}/panoptes-pocs:${DOCKER_TAG}" \
      "cp -rv /panoptes-pocs/conf_files/* /temp/conf_files/"
    sudo chown -R "${PANUSER}:${PANUSER}" "${PANDIR}/conf_files/"
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

  # Install docker-compose via pip (but first install some annoyingly large dependencies via conda).
  "${PANDIR}/conda/bin/conda" install -y -c conda-forge -n "${CONDA_ENV_NAME}" pynacl docopt pyrsistent
  "${PANDIR}/conda/envs/${CONDA_ENV_NAME}/bin/pip" install docker-compose

  rm install-miniforge.sh
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
}

function fix_time() {
  echo "Syncing time."
  sudo apt install -y ntpdate
  sudo timedatectl set-ntp false
  #  sudo dpkg-reconfigure tzdata
  sudo ntpdate -s "${NTP_SERVER}"
  sudo timedatectl set-ntp true
  timedatectl
}

function do_install() {
  clear

  name_me

  which_version

  echo "Installing POCS software for ${UNIT_NAME}"
  echo "PANUSER: ${PANUSER}"
  echo "PANDIR: ${PANDIR}"
  echo "HOST: ${HOST}"
  echo "HOST: ${HOST}"
  echo "OS: ${OS}"
  echo "Logfile: ${LOGFILE}"

  make_directories

  fix_time

  echo "Installing system dependencies."
  system_deps

  if [ "$DEV_BOX" = false ]; then
    install_zsh

    echo "Adding ${PANUSER} to default groups."
    sudo usermod -aG "${DEFAULT_GROUPS}" "${PANUSER}"
  fi

  install_conda

  which_docker

  install_docker

  get_or_build_images

  # Enable byobu
  byobu-enable

  echo "Please reboot your machine before using POCS."

  read -p "Reboot now? [y/N]: " -r
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
  fi
}

do_install
