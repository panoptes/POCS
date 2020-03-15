#!/usr/bin/env bash

usage() {
  echo -n "##################################################
# Install POCS and friends.
#
# This script is designed to install the PANOPTES Observatory
# Control System (POCS) on a cleanly installed Ubuntu system.
#
# The script will insure that Docker is installed, download the
# latest Docker images (see list below) and clone a copy of the
# relevant PANOPTES repositories.
#
# Docker Images:
#
#   ${DOCKER_BASE}/panoptes-utils
#   ${DOCKER_BASE}/pocs
#
# The script will ask for a github user name. If you are a developer
# you can enter your github username to work from your fork. Otherwise
# the default user (panoptes) is okay for running the unit.
#
# The script has been tested with a fresh install of Ubuntu 19.04
# but may work on other linux systems.
#############################################################
 $ $(basename $0) [--user panoptes] [--pandir /var/panoptes]

 Options:
  USER      The PANUSER environment variable, defaults to 'panoptes'.
  PANDIR    Default install directory, defaults to /var/panoptes. Saved as PANDIR
            environment variable.
"
}

DOCKER_BASE="gcr.io/panoptes-exp"

if [ -z "${PANUSER}" ]; then
    export PANUSER='panoptes'
    echo "export PANUSER=${PANUSER}" >> ${HOME}/.zshrc
fi
if [ -z "${PANDIR}" ]; then
    export PANDIR='/var/panoptes'
    echo "export PANDIR=${PANDIR}" >> ${HOME}/.zshrc
fi

while [[ $# -gt 0 ]]
do
key="$1"
case $key in
    -u|--user)
    PANUSER="$2"
    shift # past argument
    shift # past value
    ;;
    -d|--pandir)
    PANDIR="$2"
    shift # past argument
    shift # past value
    ;;
    -h|--help)
    PANDIR="$2"
    usage
    exit 1
    ;;
esac
done

function command_exists {
    # https://gist.github.com/gubatron/1eb077a1c5fcf510e8e5
    # this should be a very portable way of checking if something is on the path
    # usage: "if command_exists foo; then echo it exists; fi"
  type "$1" &> /dev/null
}

do_install() {
    clear

    OS="$(uname -s)"
    case "${OS}" in
        Linux*)     machine=Linux;;
        Darwin*)    machine=Mac;;
        *)          machine="UNKNOWN:${unameOut}"
    esac
    echo ${machine}

    LOGFILE="${PANDIR}/logs/install-pocs.log"

    echo "Installing PANOPTES software."
    echo "USER: ${PANUSER}"
    echo "OS: ${OS}"
    echo "DIR: ${PANDIR}"
    echo "Logfile: ${LOGFILE}"

    # System time doesn't seem to be updating correctly for some reason.
    # Perhaps just a VirtualBox issue but running on all linux.
    if [[ "${OS}" = "Linux" ]]; then
        sudo systemctl start systemd-timesyncd.service
    fi

    # Directories
    if [[ ! -d "${PANDIR}" ]]; then
        echo "Creating directories in ${PANDIR}"
        # Make directories
        sudo mkdir -p "${PANDIR}"
        sudo chown -R "${PANUSER}":"${PANUSER}" "${PANDIR}"

        mkdir -p "${PANDIR}/logs"
        mkdir -p "${PANDIR}/images"
        mkdir -p "${PANDIR}/conf_files"
        mkdir -p "${PANDIR}/.key"
    else
        echo "WARNING ${PANDIR} already exists. You can exit and specify an alternate directory with --pandir or continue."
        select yn in "Yes" "No"; do
            case $yn in
                Yes ) echo "Proceeding with existing directory"; break;;
                No ) echo "Exiting"; exit 1;;
            esac
        done
    fi

    # apt: git, wget
    echo "Installing system dependencies"

    if [[ "${OS}" = "Linux" ]]; then
        sudo apt-get update >> "${LOGFILE}" 2>&1
        sudo apt-get --yes install wget curl git openssh-server ack jq httpie byobu vim-nox zsh >> "${LOGFILE}" 2>&1
    elif [[ "${OS}" = "Darwin" ]]; then
        sudo brew update | sudo tee -a "${LOGFILE}"
        sudo brew install wget curl git jq httpie | sudo tee -a "${LOGFILE}"
    fi

    echo "Cloning PANOPTES source code."
    echo "Github user for PANOPTES repos (POCS, PAWS, panoptes-utils)."

    # Default user
    read -p "Github User [press Enter for default]: " github_user
    github_user=${github_user:-panoptes}
    echo "Using repositories from user '${github_user}'."

    GIT_BRANCH="develop"

    cd "${PANDIR}"
    declare -a repos=("POCS" "panoptes-utils")
    for repo in "${repos[@]}"; do
        if [ ! -d "${PANDIR}/${repo}" ]; then
            echo "Cloning ${repo}"
            # Just redirect the errors because otherwise looks like it hangs.
            git clone "https://github.com/${github_user}/${repo}.git" >> "${LOGFILE}" 2>&1
        else
            echo "Repo ${repo} already exists on system."
        fi
    done

    # Link env_file from POCS
    if ! test -f "${PANDIR}/.env"; then
        ln -sf "${PANDIR}/POCS/docker/env_file" "${PANDIR}/.env"
        echo "source ${PANDIR}/.env" >> "${HOME}/.zshrc"
    fi

    # Get Docker
    if ! command_exists docker; then
        echo "Installing Docker"
        if [[ "${OS}" = "Linux" ]]; then
            /bin/bash -c "$(wget -qO- https://get.docker.com)" &>> ${PANDIR}/logs/install-pocs.log

            if ! command_exists docker-compose; then
                # Docker compose as container - https://docs.docker.com/compose/install/#install-compose
                sudo wget -q https://github.com/docker/compose/releases/download/1.25.4/docker-compose-`uname -s`-`uname -m` -O /usr/local/bin/docker-compose
                sudo chmod a+x /usr/local/bin/docker-compose
                sudo docker pull docker/compose
            fi

            echo "Adding ${PANUSER} to docker group"
            sudo usermod -aG docker "${PANUSER}" >> "${LOGFILE}" 2>&1
        elif [[ "${OS}" = "Darwin" ]]; then
            brew cask install docker
            echo "Adding ${PANUSER} to docker group"
            sudo dscl -aG docker "${PANUSER}"
        fi

        echo "Pulling POCS docker images"
        sudo docker pull "${DOCKER_BASE}/panoptes-utils:latest"
        sudo docker pull "${DOCKER_BASE}/pocs:latest"
        sudo docker pull "${DOCKER_BASE}/aag-weather:latest"
    else
        echo "WARNING: Docker images not installed/downloaded."
    fi

    # Add an SSH key if one doesn't exists
    if [ ! -f "${HOME}/.ssh/id_rsa" ]; then
        echo "Looks like you don't have an SSH key set up yet, adding one now."
        ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa";
    fi

    echo "Please reboot your machine before using POCS."

    read -p "Reboot now? [y/N]: " -r
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
        sudo reboot
    fi

}

# wrapped up in a function so that we have some protection against only getting
# half the file during "curl | sh" - copied from get.docker.com
do_install
