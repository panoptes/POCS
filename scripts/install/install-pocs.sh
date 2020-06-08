#!/usr/bin/env bash
set -e

usage() {
  echo -n "##################################################
# Install POCS and friends.
#
# This script is designed to install the PANOPTES Observatory
# Control System (POCS) on a cleanly installed Ubuntu system.
#
# This script is meant for quick & easy install via:
#
#   $ curl -L https://install.projectpanoptes.org | bash
#   or
#   $ wget -O - https://install.projectpanoptes.org | bash
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
#
# The script will ask if it should be installed in "developer" mode or not.
#
# The regular install is for running units and will not create local (to the
# host system) copies of the files.
#
# The "developer" mode will ask for a github username and will clone and
# fetch the repos. The `docker/setup-local-enviornment.sh` script will then
# be run to build the docker images locally.
#
# If not in "developer" mode, the docker images will be pulled from GCR.
#
# The script has been tested with a fresh install of Ubuntu 20.04
# but may work on other linux systems.
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


DEVELOPER=${DEVELOPER:-false}
PANUSER=${PANUSER:-$USER}
PANDIR=${PANDIR:-/var/panoptes}
LOGFILE="${PANDIR}/install-pocs.log"
OS="$(uname -s)"
ARCH="$(uname -m)"
ENV_FILE="${PANDIR}/env"

DOCKER_COMPOSE_VERSION="${DOCKER_COMPOSE_VERSION:-1.26.0}"
DOCKER_COMPOSE_INSTALL="https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-${OS}-${ARCH}"
DOCKER_BASE=${DOCKER_BASE:-"gcr.io/panoptes-exp"}


while [[ $# -gt 0 ]]
do
key="$1"
case ${key} in
    --developer)
    DEVELOPER=true
    shift # past bool argument
    ;;
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

if ! ${DEVELOPER}; then
    echo -n "Are you installing POCS as a developer? (for PANOPTES units, select No)"
    select yn in "Yes" "No"; do
        case ${yn} in
            Yes ) echo "Enabling developer mode. Note that you will need your GitHub username to proceed"; DEVELOPER=true; break;;
            No ) echo "Installing POCS in production mode"; break;;
        esac
    done
fi

if "${DEVELOPER}"; then
    while [[ -z "${GITHUB_USER}" ]]; do
        read -p "Github User [NOTE: you must have a fork created already]: " GITHUB_USER
    done
fi

echo "DEVELOPER=${DEVELOPER} PANDIR=${PANDIR} PANUSER=${PANUSER} GITHUB_USER=${GITHUB_USER}"

function command_exists {
    # https://gist.github.com/gubatron/1eb077a1c5fcf510e8e5
    # this should be a very portable way of checking if something is on the path
    # usage: "if command_exists foo; then echo it exists; fi"
  type "$1" &> /dev/null
}

function make_directories {
    if [[ ! -d "${PANDIR}" ]]; then
        # Make directories and make PANUSER the owner.
        sudo mkdir -p "${PANDIR}"
    else
        echo "WARNING ${PANDIR} already exists. You can exit and specify an alternate directory with --pandir or continue."
        select yn in "Yes" "No"; do
            case ${yn} in
                Yes ) echo "Proceeding with existing directory"; break;;
                No ) echo "Exiting"; exit 1;;
            esac
        done
    fi

    sudo mkdir -p "${PANDIR}/logs"
    sudo mkdir -p "${PANDIR}/images"
    sudo mkdir -p "${PANDIR}/config_files"
    sudo mkdir -p "${PANDIR}/.key"
    sudo chown -R "${PANUSER}":"${PANUSER}" "${PANDIR}"
}

function setup_env_vars {
    echo "Writing environment variables to ${ENV_FILE}"
    if  [[ -f "${ENV_FILE}" ]]; then
        echo "\n**** Added by install-pocs script ****\n" >> "${ENV_FILE}"
    fi

    cat >> "${ENV_FILE}" <<EOF
export PANUSER=${PANUSER}
export PANDIR=${PANDIR}
export POCS=${PANDIR}/POCS
export PANLOG=${PANDIR}/logs
EOF

    echo '. /var/panoptes/env' >> ~/.bashrc
}



function system_deps {
    if [[ "${OS}" = "Linux" ]]; then
        sudo apt-get update >> "${LOGFILE}" 2>&1
        # TODO(wtgee) figure out why we needed openssh-server on the host.
        sudo apt-get --yes install \
            wget curl git openssh-server ack jq httpie byobu \
            >> "${LOGFILE}" 2>&1
    elif [[ "${OS}" = "Darwin" ]]; then
        sudo brew update | sudo tee -a "${LOGFILE}"
        sudo brew install \
            wget curl git jq httpie \
            | sudo tee -a "${LOGFILE}"
    fi

    # Add an SSH key if one doesn't exist.
    if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
        echo "Adding ssh key"
        ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa";
    fi
}

function get_repos {
    PUBLIC_GITHUB_URL="https://github.com/panoptes"

    if "${DEVELOPER}"; then
        echo "Using repositories from user: ${GITHUB_USER}"
        declare -a repos=("POCS" "panoptes-utils" "panoptes-tutorials")
        GITHUB_URL="git@github.com:${GITHUB_USER}"
    else
        declare -a repos=("POCS" "panoptes-utils")
        GITHUB_URL="${PUBLIC_GITHUB_URL}"
    fi

    for repo in "${repos[@]}"; do
        if [[ ! -d "${PANDIR}/${repo}" ]]; then
            cd "${PANDIR}"
            echo "Cloning ${repo}"
            # Just redirect the errors because otherwise looks like it hangs.
            # TODO handle errors if repo doesn't exist (e.g. bad github name).
            git clone "https://github.com/${GITHUB_USER}/${repo}.git" >> "${LOGFILE}" 2>&1

            # Set panoptes as upstream
            cd "${repo}"
            git remote add upstream "${PUBLIC_GITHUB_URL}/${repo}"
        else
            # TODO Figure out how to do updates.
            echo "${repo} already exists in ${PANDIR}. No auto-update for now, skipping repo."
        fi
    done
}

function get_docker {
    # Get Docker
    if ! command_exists docker; then
        echo "Installing Docker"
        if [[ "${OS}" = "Linux" ]]; then
            /bin/bash -c "$(wget -qO- https://get.docker.com)" &>> "${LOGFILE}"

            echo "Adding ${PANUSER} to docker group"
            sudo usermod -aG docker "${PANUSER}" >> "${LOGFILE}" 2>&1
        elif [[ "${OS}" = "Darwin" ]]; then
            brew cask install docker
            echo "Adding ${PANUSER} to docker group"
            sudo dscl -aG docker "${PANUSER}"
        fi
    fi

    if ! command_exists docker-compose; then
        echo "Installing docker-compose"
        # Docker compose as container - https://docs.docker.com/compose/install/#install-compose
        sudo wget -q "${DOCKER_COMPOSE_INSTALL}" -O /usr/local/bin/docker-compose
        sudo chmod a+x /usr/local/bin/docker-compose
    fi
}

function get_or_build_images {
    if ${DEVELOPER}; then
        echo "Building local PANOPTES docker images."

        cd "${POCS}"
        ./docker/setup-local-environment.sh
    else
        echo "Pulling PANOPTES docker images from Google Cloud Registry (GCR)."

        docker pull "${DOCKER_BASE}/panoptes-pocs:latest"
        docker pull "${DOCKER_BASE}/panoptes-utils:latest"
        docker pull "${DOCKER_BASE}/aag-weather:latest"
    fi
}

function do_install {
    clear

    if ${DEVELOPER}; then
        echo ""
        echo "**** Developer Mode ****"
        echo ""
    fi
    echo "Installing PANOPTES software."
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

    echo "Cloning PANOPTES source code"
    get_repos

    get_or_build_images

    echo "Please reboot your machine before using POCS."

    read -p "Reboot now? [y/N]: " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo reboot
    fi

    exit 0;
}

do_install
