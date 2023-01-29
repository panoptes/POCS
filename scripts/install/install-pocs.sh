#!/usr/bin/env bash
set -e

usage() {
  echo -n "##################################################
# Install POCS and friends.
#
# Script Version: 2023-01-29
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
##
# The script has been tested with a fresh install of Ubuntu Server 22.10
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
#   * 2023-01-29 (wtgee) - Simplified options. Added supervisor. Clean up.
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

PANUSER="${PANUSER:-$USER}"
PANDIR="${PANDIR:-${HOME}/pocs}"
UNIT_NAME="pocs"
LOGFILE="${HOME}/logs/install-pocs.log"
OS="$(uname -s)"
DEV_BOX=false
USE_ZSH=false
INSTALL_SERVICES=false
DEFAULT_GROUPS="dialout,plugdev,input,sudo"

# We use htpdate below so this just needs to be a public url w/ trusted time.
TIME_SERVER="${TIME_SERVER:-google.com}"

CONDA_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh"
CONDA_ENV_NAME=conda-pocs

CODE_BRANCH=${CODE_BRANCH:-"develop"}

function system_deps() {
  echo "Installing system dependencies."

  # Clean up problems.
  sudo apt-get -y -qq purge needrestart
  sudo apt-get update --fix-missing -y -qq 
  sudo apt-get -y -qq full-upgrade

  sudo apt-get -y -qq install \
    ack \
    byobu \
    docker.io \
    fonts-powerline \
    gcc \
    htop \
    httpie \
    jo \
    jq \
    make \
    nano \
    vim-nox \
    supervisor \
    wget
  sudo apt-get -y -qq autoremove

  sudo usermod -aG "${DEFAULT_GROUPS}" "${PANUSER}"

  # Add an SSH key if one doesn't exist.
  if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
    echo "Adding ssh key"
    ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa"
  fi

}

function install_conda() {
  echo "Installing miniforge conda"

  wget -q "${CONDA_URL}" -O install-miniforge.sh
  /bin/sh install-miniforge.sh -b -f -p "${HOME}/conda"
  rm install-miniforge.sh

  # Initialize conda for the shells.
  "${HOME}/conda/bin/conda" init bash 
  "${HOME}/conda/bin/conda" init zsh 

  echo "Creating POCS conda environment"
  "${HOME}/conda/bin/conda" create -y -q -n "${CONDA_ENV_NAME}" python=3 mamba

  # Activate by default
  echo "conda activate ${CONDA_ENV_NAME}" >>"${HOME}/.zshrc"

  cd "${PANDIR}"
  "${HOME}/conda/envs/${CONDA_ENV_NAME}/bin/mamba" env update -p "${HOME}/conda/envs/${CONDA_ENV_NAME}" -f environment.yaml
}

function get_pocs_repo() {
  echo "Cloning POCS repo."

  git clone https://github.com/panoptes/POCS "${PANDIR}"
  cd "${PANDIR}"
  git checkout "$CODE_BRANCH"
}

function make_directories() {
  echo "Creating directories."
  mkdir -p "${HOME}/logs"
  mkdir -p "${HOME}/images"
  mkdir -p "${HOME}/json_store"
  mkdir -p "${HOME}/keys"
  mkdir -p "${HOME}/notebooks"

  # Link the needed POCS folders.
  ln -s "${PANDIR}/conf_files" "${HOME}"
  ln -s "${PANDIR}/resources" "${HOME}"
}

function install_services() {
  echo "Installing supervisor services."

  # Make supervisor read our conf file at its current location.
  echo "files = {HOME}/conf_files/pocs-supervisord.conf" | sudo tee -a /etc/supervisor/supervisord.conf

  # Reread the supervisord conf and restart.
  sudo supervisorctl reread
  sudo supervisorctl update
}

function install_zsh() {
  if [ ! -d "$ZSH_CUSTOM" ]; then
    echo "Using zsh for a better shell experience."

    DEBIAN_FRONTEND=noninteractive sudo apt-get -y -qq install zsh

    sudo chsh --shell /usr/bin/zsh "${PANUSER}"

    # Oh my zsh
    wget -q https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh -O /tmp/install-ohmyzsh.sh
    bash /tmp/install-ohmyzsh.sh --unattended 

    export ZSH_CUSTOM="$HOME/.oh-my-zsh"

    # Autosuggestions plugin
    git clone https://github.com/zsh-users/zsh-autosuggestions "${ZSH_CUSTOM:-~/.oh-my-zsh/custom}"/plugins/zsh-autosuggestions

    write_zshrc
  fi
}

function write_zshrc() {
  cat >"${HOME}/.zshrc" <<EOT

zstyle ':omz:update' mode disabled 

export PATH="\$HOME/.local/bin:/usr/local/bin:\$PATH"
export ZSH="/home/${PANUSER}/.oh-my-zsh"
export PANDIR="${PANDIR}"

ZSH_THEME="agnoster"

plugins=(git sudo zsh-autosuggestions docker docker-compose python)
source \$ZSH/oh-my-zsh.sh
unsetopt share_history

EOT
}

function fix_time() {
  echo "Syncing time."
  DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq htpdate
  sudo timedatectl set-ntp false
  sudo /usr/sbin/htpdate -as "${TIME_SERVER}"
  sudo timedatectl set-ntp true

  # Add crontab entries for reboot and every hour.
  (
    sudo crontab -l
    echo "@reboot /usr/sbin/htpdate -as ${TIME_SERVER}"
  ) | sudo crontab -
  (
    sudo crontab -l
    echo "13 * * * * /usr/sbin/htpdate -s ${TIME_SERVER}"
  ) | sudo crontab -

  # Show updated time.
  timedatectl
}

function do_install() {
  clear

  # Set up directory for log file.
  mkdir -p "${HOME}/logs"
  echo "Starting POCS install at $(date)" 

  # Get the unit name.
  read -rp 'What is the name of your unit (e.g. "PAN001" or "Maia")? ' UNIT_NAME

  # Check if user wants zsh.
  read -p "Would you like to use zsh as the default shell? [Y/n]: " -r
  if [[ -z $REPLY || $REPLY =~ ^[Yy]$ ]]; then
    USE_ZSH=true
  fi

  # Install services by default.
  read -p "Would you like to install supervisor services automatically? [Y/n]: " -r
  if [[ -z $REPLY || $REPLY =~ ^[Yy]$ ]]; then
    INSTALL_SERVICES=true
  fi

  # Github code branch.
  read -rp "What branch of the code would you like to use (default: ${CODE_BRANCH})? " USER_CODE_BRANCH
  CODE_BRANCH="${USER_CODE_BRANCH:-$CODE_BRANCH}"

  echo "Installing POCS software for ${UNIT_NAME}"
  echo "OS: ${OS}"
  echo "PANUSER: ${PANUSER}"
  echo "PANDIR: ${PANDIR}"
  echo "CODE_BRANCH: ${CODE_BRANCH}"

  fix_time
  system_deps

  if [[ "${USE_ZSH}" == true ]]; then
    install_zsh
  fi

  get_pocs_repo

  install_conda

  make_directories

  if [[ "${INSTALL_SERVICES}" == true ]]; then
    install_services
  fi

  echo "Please reboot your machine before using POCS."

  read -p "Reboot now? [y/N]: " -r
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
  fi
}

do_install
