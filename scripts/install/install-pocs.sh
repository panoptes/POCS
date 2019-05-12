#!/bin/bash -e

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
    -d|--dir)
    PANDIR="$2"
    shift # past argument
    shift # past value
    ;;
esac
done

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
sudo apt --yes install wget git &>> ${PANDIR}/logs/install-pocs.log

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
    else
        echo "Repo ${repo} already exists on system."
    fi
done

# Get Docker
if ! hash docker; then
    echo "Installing Docker"
    sh -c "$(wget https://get.docker.com -O -)"
    sudo usermod -aG docker ${PANUSER}
    # Docker compose as container - https://docs.docker.com/compose/install/#install-compose
    sudo curl -L --fail https://github.com/docker/compose/releases/download/1.24.0/run.sh -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    sudo chmod a+x /usr/local/bin/docker-compose
fi

echo "Pulling POCS docker images"
sudo docker pull gcr.io/panoptes-survey/pocs
sudo docker pull gcr.io/panoptes-survey/paws

echo "Installing docker-compose"
sudo curl -L --fail https://github.com/docker/compose/releases/download/1.24.0/run.sh -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "You must logout and log back in to  before using POCS."

