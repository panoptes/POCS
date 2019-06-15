#!/usr/bin/env bash

usage() {
  echo -n "##################################################
# Install POCS and friends.
#
# This script is designed to install the PANOPTES Observatory
# Control System (POCS) on a cleanly install Ubuntu system.
#
# The script will insure that Docker is installed, download the
# latest Docker images (see list below) and clone a copy of the
# relevant PANOPTES repositories.
#
# Docker Images:
#
#   gcr.io/panoptes-survey/pocs
#   gcr.io/panoptes-survey/paws
#
# Github Repositories:
#
# The script will ask for a github user name in order to install
# forked versions of the repos if you are actively developing the
# software. otherwise the default user (panotpes) is okay for
# running the unit.
#
#   github.com/panoptes/POCS
#   github.com/panoptes/PAWS
#   github.com/panoptes/panoptes-utils
#
# The script has been tested with a fresh install of Ubuntu 19.04
# but may work on other linux systems.
#############################################################
 $ $(basename $0) [--user panoptes] [--pandir /var/panoptes]

 Options:
  USER      The default user. This is saved as the PANUSER environment variable.
  PANDIR    Default install directory, defaults to /var/panoptes. Saved as PANDIR
            environment variable.
"
}

if [ -z ${PANUSER} ]; then
    export PANUSER=$USER
    echo "export PANUSER=${PANUSER}" >> ${HOME}/.bashrc
fi
if [ -z ${PANDIR} ]; then
    export PANDIR='/var/panoptes'
    echo "export PANDIR=${PANDIR}" >> ${HOME}/.bashrc
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

do_install() {
    echo "Installing PANOPTES software."
    echo "USER: ${PANUSER}"
    echo "DIR: ${PANDIR}"

    if [[ ! -d ${PANDIR} ]] || [[ $(stat -c "%U" ${PANDIR}) -ne $USER ]]; then
        echo "Creating directories"
        # Make directories
        sudo mkdir -p ${PANDIR}
        sudo chown -R ${PANUSER}:${PANUSER} ${PANDIR}

        mkdir -p ${PANDIR}/logs
        mkdir -p ${PANDIR}/conf_files
        mkdir -p ${PANDIR}/images
    fi

    echo "Log files will be stored in ${PANDIR}/logs/install-pocs.log."

    # apt: git, wget
    echo "Installing system dependencies"
    sudo apt update &>> ${PANDIR}/logs/install-pocs.log
    sudo apt --yes install wget git openssh-server byobu &>> ${PANDIR}/logs/install-pocs.log

    echo "Cloning PANOPTES source code."
    echo "Github user for PANOPTES repos (POCS, PAWS, panoptes-utils)."
    read -p "Github User: [panoptes] " github_user

    cd ${PANDIR}

    declare -a repos=("POCS" "PAWS" "panoptes-utils")

    for repo in "${repos[@]}"; do
        if [ ! -d "${PANDIR}/${repo}" ]; then
            echo "Cloning ${repo}"
            # Just redirect the errors because otherwise looks like it hangs.
            git clone https://github.com/${github_user}/${repo}.git

            # TODO
            # echo "export PANDIR=${PANDIR}" >> ${HOME}/.bashrc
        else
            echo "Repo ${repo} already exists on system."
        fi
    done

    # Get Docker
    if ! hash docker; then
        echo "Installing Docker"
        sh -c "$(wget https://get.docker.com -O -)"
        sudo usermod -aG docker ${PANUSER}
    fi

    if ! hash docker-compose; then
        # Docker compose as container - https://docs.docker.com/compose/install/#install-compose
        sudo curl -L --fail https://github.com/docker/compose/releases/download/1.24.0/run.sh -o /usr/local/bin/docker-compose
        sudo chmod a+x /usr/local/bin/docker-compose
    fi

    echo "Pulling POCS docker images"
    sudo docker pull gcr.io/panoptes-survey/pocs
    sudo docker pull gcr.io/panoptes-survey/paws

    echo "Please reboot your machine before using POCS."

}
# wrapped up in a function so that we have some protection against only getting
# half the file during "curl | sh" - copied from get.docker.com
do_install
