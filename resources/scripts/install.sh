#!/usr/bin/env bash
set -e

echo "Installing POCS"

echo "Setting up user."
source ./setup-user.sh

echo "Fixing system time."
source ./fix-time.sh

echo "Installing system dependencies."
source ./install-system-deps.sh

echo "Installing POCS software."
source ./install-pocs.sh

echo "Installing conda python."
source ./install-conda.sh

echo "Installing ZSH for a better shell."
source ./install-zsh.sh

echo "Installing services so things run at startup."
source ./install-services.sh
