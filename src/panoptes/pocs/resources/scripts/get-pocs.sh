#!/usr/bin/env bash

BRANCH="${BRANCH:-develop}"

git clone https://github.com/panoptes/POCS
cd POCS
git checkout "${BRANCH}"
cd resources/scripts/install
./install.sh

echo
echo "POCS installed, please reboot."
