#!/bin/bash -e

KEY_FILE=${1}
PANDIR=${2:-/var/panoptes}

echo "Starting fresh install at `date`" > install.log

echo "Using ${KEY_FILE}"

echo "Creating ${PANDIR}"
mkdir -p ${PANDIR}/.key

echo "Moving ${KEY_FILE} to hidden directory ${PANDIR}/.key"
mv ${KEY_FILE} ${PANDIR}/.key

echo "Updating computer..."

# Create environment variable for correct distribution
export CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)"

# Add the Cloud SDK distribution URI as a package source
echo "deb http://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Import the Google Cloud Platform public key
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -

sudo apt update &>> install.log
sudo apt install -y docker  google-cloud-sdk &>> install.log

# Install miniconda and docker-compose
wget https://repo.continuum.io/miniconda/Miniconda3-3.7.0-Linux-x86_64.sh -O ~/miniconda.sh &>> install.log
bash ~/miniconda.sh -b -p ${PANDIR}/miniconda
export PATH="${PANDIR}/miniconda/bin:$PATH"
source ${PANDIR}/miniconda/bin/activate
rm ~/miniconda.sh

conda create -n panoptes python=3.7 docker-compose &>> install.log

conda activate panoptes
conda install -y docker-compose

echo "Authenticating with google"
gcloud auth activate-service-account --key-file ${PANDIR}/.key/${KEY_FILE}
gcloud auth configure-docker

echo "Pulling POCS files from cloud"
echo "WARNING: This is a large file that can take a long time!"
docker pull gcr.io/panoptes-survey/pocs-base
docker pull gcr.io/panoptes-survey/paws