#!/usr/bin/env bash

BRANCH="${BRANCH:-develop}"

git clone https://github.com/panoptes/POCS
cd POCS
git checkout "${BRANCH}"
cd resources/scripts
./install.sh

"${HOME}/conda/envs/conda-pocs/bin/pocs" config setup

echo
echo "POCS installed, please reboot."
