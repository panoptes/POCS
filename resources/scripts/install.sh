#!/usr/bin/env bash
set -e

echo "Installing POCS"
echo "Installing POCS" >> install.log

echo "Setting up user."
source ./setup-user.sh 2>&1 | tee -a install.log

echo "Fixing system time."
source ./fix-time.sh 2>&1 | tee -a install.log

echo "Installing system dependencies."
source ./install-system-deps.sh 2>&1 | tee -a install.log

echo "Installing POCS software."
source ./install-pocs.sh 2>&1 | tee -a install.log

echo "Installing conda python."
source ./install-conda.sh 2>&1 | tee -a install.log

echo "Installing ZSH for a better shell."
source ./install-zsh.sh 2>&1 | tee -a install.log

echo "Installing services so things run at startup."
source ./install-services.sh 2>&1 | tee -a install.log
