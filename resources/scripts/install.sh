#!/usr/bin/env bash
set -e

echo "Installing POCS"
source ./install-system-deps.sh
source ./install-conda.sh
source ./install-pocs.sh
source ./install-zsh.sh
source ./install-services.sh
