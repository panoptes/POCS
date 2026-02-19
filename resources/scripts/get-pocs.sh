#!/usr/bin/env bash

BRANCH="${BRANCH:-develop}"

# We don't check certificate because the Pi doesn't have an RTC.
# The first install step is to fix system time.
git -c http.sslVerify=false clone https://github.com/panoptes/POCS
cd POCS
git checkout "${BRANCH}"
cd resources/scripts/install
./install.sh

echo
echo "POCS installed, please reboot."
