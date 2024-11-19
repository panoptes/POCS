#!/usr/bin/env bash
set -e

echo "Installing POCS"

echo "Setting up user."
source ./setup-user.sh > install.log 2>&1

echo "Fixing system time."
source ./fix-time.sh >> install.log 2>&1

echo "Installing system dependencies."
source ./install-system-deps.sh >> install.log 2>&1

echo "Installing POCS software."
source ./install-pocs.sh >> install.log 2>&1

echo "Installing conda python."
source ./install-conda.sh >> install.log 2>&1

echo "Installing ZSH for a better shell."
source ./install-zsh.sh >> install.log 2>&1

echo "Installing services so things run at startup."
source ./install-services.sh >> install.log 2>&1
