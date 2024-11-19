#!/usr/bin/env bash
set -e

echo "Installing POCS"
sudo /bin/bash install-system-deps.sh
source ./install-pocs.sh
source ./install-conda.sh
source ./install-zsh.sh
source ./install-services.sh
