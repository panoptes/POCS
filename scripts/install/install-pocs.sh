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
#   * Source \${PANDIR}/env if it exists.
#
# Docker Images:
#
#   gcr.io/panoptes-exp/panoptes-pocs:develop
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

PANUSER="${PANUSER:-$USER}"
PANDIR="${PANDIR:-${HOME}/pocs}"
UNIT_NAME="pocs"
HOST="${HOST:-pocs-control-box}"
LOGFILE="${HOME}/logs/install-pocs.log"
OS="$(uname -s)"
DEV_BOX=false
USE_ZSH=false
INSTALL_SERVICES=false
DEFAULT_GROUPS="dialout,plugdev,input,sudo,docker"

ROUTER_IP="${ROUTER_IP:-192.168.8.1}"

CONDA_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh"
CONDA_ENV_NAME=conda-pocs

CODE_BRANCH=${CODE_BRANCH:-"develop"}

function name_me() {
  read -rp 'What is the name of your unit (e.g. "PAN001" or "Maia")? ' UNIT_NAME
}

function which_branch() {
  read -rp "What branch of the code would you like to use (default: ${CODE_BRANCH})? " USER_CODE_BRANCH
  CODE_BRANCH="${USER_CODE_BRANCH:-$CODE_BRANCH}"
}

function get_time_settings() {
  read -rp "What is the IP address of your router (default: ${ROUTER_IP})? " USER_NTP_SERVER
  ROUTER_IP="${USER_NTP_SERVER:-$ROUTER_IP}"
  sudo dpkg-reconfigure tzdata
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

  if [ "${DEV_BOX}" != true ]; then
    echo "Setting hostname to ${HOST}"
    sudo hostnamectl set-hostname "$HOST"
  fi

  read -p "Would you like to use zsh as the default shell? [Y/n]: " -r
  if [[ -z $REPLY || $REPLY =~ ^[Yy]$ ]]; then
    USE_ZSH=true
  fi

  read -p "Would you like to install the Config Server and Power Monitor services? [Y/n]: " -r
  if [[ -z $REPLY || $REPLY =~ ^[Yy]$ ]]; then
    INSTALL_SERVICES=true
  fi
}

function system_deps() {
  echo "Installing system dependencies."

  DEBIAN_FRONTEND=noninteractive sudo apt-get -y -qq purge needrestart | sudo tee -a "${LOGFILE}"
  DEBIAN_FRONTEND=noninteractive sudo apt-get update --fix-missing -y -qq | sudo tee -a "${LOGFILE}"
  DEBIAN_FRONTEND=noninteractive sudo apt-get -y -qq full-upgrade | sudo tee -a "${LOGFILE}"

  # Raspberry Pi stuff
  if [ "$(uname -m)" = "aarch64" ]; then
    echo "Installing Raspberry Pi tools."
    DEBIAN_FRONTEND=noninteractive sudo apt-get -y -qq install \
      rpi.gpio-common linux-tools-raspi linux-modules-extra-raspi python3-lgpio | sudo tee -a "${LOGFILE}"
  fi

  DEBIAN_FRONTEND=noninteractive sudo apt-get -y -qq install \
    ack \
    byobu \
    docker.io \
    gcc \
    htop \
    httpie \
    jq \
    make \
    nano \
    neovim \
    sshfs \
    usbmount \
    wget | sudo tee -a "${LOGFILE}"
  DEBIAN_FRONTEND=noninteractive sudo apt-get -y -qq autoremove | sudo tee -a "${LOGFILE}"

  sudo usermod -aG "${DEFAULT_GROUPS}" "${PANUSER}"

  # Add an SSH key if one doesn't exist.
  if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
    echo "Adding ssh key"
    ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa"
  fi

}

function get_or_build_docker_images() {
  echo "Pulling POCS docker images from Google Cloud Registry (GCR)."

  sudo docker pull "${DOCKER_IMAGE}:${CODE_BRANCH}"

  if [[ $HOST == *-control-box ]]; then
    # Copy the docker-compose file
    sudo docker run --rm -it \
      -v "${PANDIR}:/temp" \
      "${DOCKER_IMAGE}:${CODE_BRANCH}" \
      "cp /panoptes-pocs/docker/docker-compose.yaml /temp/docker-compose.yaml"
    sudo chown "${PANUSER}:${PANUSER}" "${PANDIR}/docker-compose.yaml"

    # Copy the config file
    sudo docker run --rm -it \
      -v "${PANDIR}:/temp" \
      "${DOCKER_IMAGE}:${CODE_BRANCH}" \
      "cp -rv /panoptes-pocs/conf_files/* /temp/conf_files/"
    sudo chown -R "${PANUSER}:${PANUSER}" "${PANDIR}/conf_files/"
  fi
}

function install_conda() {
  echo "Installing miniforge conda"

  wget -q "${CONDA_URL}" -O install-miniforge.sh
  /bin/sh install-miniforge.sh -b -f -p "${HOME}/conda" >>"${LOGFILE}"
  rm install-miniforge.sh

  # Initialize conda for the shells.
  "${HOME}/conda/bin/conda" init bash >>"${LOGFILE}"
  "${HOME}/conda/bin/conda" init zsh >>"${LOGFILE}"

  echo "Creating POCS conda environment"
  "${HOME}/conda/bin/conda" create -y -q -n "${CONDA_ENV_NAME}" python=3 mamba

  # Activate by default
  echo "conda activate ${CONDA_ENV_NAME}" >>"${HOME}/.zshrc"

  cat <<EOF >environment.yaml
channels:
  - https://conda.anaconda.org/conda-forge
dependencies:
  - astroplan
  - astropy
  - docopt
  - fastapi
  - google-cloud-storage
  - google-cloud-firestore
  - gsutil
  - jupyter_console
  - matplotlib-base
  - numpy
  - pandas
  - photutils
  - pip
  - pynacl
  - pyrsistent
  - scipy
  - streamz
  - uvicorn[standard]
  - pip:
      - "git+https://github.com/panoptes/POCS@${CODE_BRANCH}#egg=panoptes-pocs[google,focuser,sensors]"
      - docker-compose
EOF

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
  echo "Creating panoptes-config-server service."

  sudo bash -c 'cat > /etc/systemd/system/panoptes-config-server.service' <<EOF
[Unit]
Description=PANOPTES Config Server
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=ubuntu
WorkingDirectory=~
ExecStart=${HOME}/conda/envs/${CONDA_ENV_NAME}/bin/panoptes-config-server --host 0.0.0.0 --port 6563 run --config-file ${PANDIR}/conf_files/pocs.yaml

[Install]
WantedBy=multi-user.target
EOF

  echo "Creating panoptes power service."

  sudo bash -c 'cat > /etc/systemd/system/panoptes-power-server.service' <<EOF
[Unit]
Description=PANOPTES Power Monitor
After=panoptes-config-server.service
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=ubuntu
WorkingDirectory=~
ExecStartPre=/bin/sleep 10
ExecStart=${HOME}/conda/envs/${CONDA_ENV_NAME}/bin/uvicorn --host 0.0.0.0 --port 6564 panoptes.pocs.utils.service.power:app

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl enable panoptes-config-server
  sudo systemctl enable panoptes-power-server
}

function install_zsh() {
  if [ ! -d "$ZSH_CUSTOM" ]; then
    echo "Using zsh for a better shell experience."

    DEBIAN_FRONTEND=noninteractive sudo apt-get -y -qq install zsh

    sudo chsh --shell /usr/bin/zsh "${PANUSER}"

    # Oh my zsh
    wget -q https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh -O /tmp/install-ohmyzsh.sh
    bash /tmp/install-ohmyzsh.sh --unattended >>"${LOGFILE}"

    export ZSH_CUSTOM="$HOME/.oh-my-zsh"

    # Autosuggestions plugin
    git clone https://github.com/zsh-users/zsh-autosuggestions "${ZSH_CUSTOM:-~/.oh-my-zsh/custom}"/plugins/zsh-autosuggestions

    # Spaceship theme
    git clone https://github.com/denysdovhan/spaceship-prompt.git "$ZSH_CUSTOM/themes/spaceship-prompt" --depth=1
    ln -s "$ZSH_CUSTOM/themes/spaceship-prompt/spaceship.zsh-theme" "$ZSH_CUSTOM/themes/spaceship.zsh-theme"

    write_zshrc
  fi
}

function write_zshrc() {
  cat >"${HOME}/.zshrc" <<EOT

export PATH="\$HOME/.local/bin:/usr/local/bin:\$PATH"
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
  DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq ntpdate | sudo tee -a "${LOGFILE}"
  sudo timedatectl set-ntp false
  sudo ntpdate -s "${ROUTER_IP}"
  sudo timedatectl set-ntp true

  # Add crontab entries for reboot and every hour.
  (
    sudo crontab -l
    echo "@reboot ntpdate -s ${ROUTER_IP}"
  ) | sudo crontab -
  (
    sudo crontab -l
    echo "13 * * * * ntpdate -s ${ROUTER_IP}"
  ) | sudo crontab -

  # Show updated time.
  timedatectl
}

function setup_nfs_host() {
  sudo apt-get install -y nfs-kernel-server
  sudo mkdir -p "${HOME}/images"
  echo "${HOME}/images ${ROUTER_IP}/24 (rw,async,no_subtree_check)" | sudo tee -a /etc/exports

  sudo exportfs -a
  sudo systemctl restart nfs-kernel-server
}

function do_install() {
  clear

  # Set up directory for log file.
  mkdir -p "${HOME}/logs"
  echo "Starting POCS install at $(date)" >>"${LOGFILE}"  

  name_me

  which_version

  which_branch

  if [ "$(uname -m)" = "aarch64" ]; then
    get_time_settings
  fi

  echo "Installing POCS software for ${UNIT_NAME}"
  echo "OS: ${OS}"
  echo "PANUSER: ${PANUSER}"
  echo "PANDIR: ${PANDIR}"
  echo "HOST: ${HOST}"
  echo "Logfile: ${LOGFILE}"
  #  echo "DOCKER_IMAGE: ${DOCKER_IMAGE}"
  echo "CODE_BRANCH: ${CODE_BRANCH}"

  # Make sure the time setting is correct on RPi.
  if [ "$(uname -m)" = "aarch64" ]; then
    echo "ROUTER_IP: ${ROUTER_IP}"
    fix_time
  fi

  system_deps

  if [[ "${USE_ZSH}" == true ]]; then
    install_zsh
  fi

  install_conda

  get_pocs_repo

  make_directories

  if [[ "${INSTALL_SERVICES}" == true ]]; then
    install_services
  fi

  # get_or_build_docker_images

  echo "Please reboot your machine before using POCS."

  read -p "Reboot now? [y/N]: " -r
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
  fi
}

do_install
