#!/usr/bin/env bash

CONDA_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh"
PANDIR="${PANDIR:-${HOME}/POCS}"
CONDA_ENV_NAME=conda-pocs

echo "Installing miniforge conda"

wget -q "${CONDA_URL}" -O install-miniforge.sh
/bin/sh install-miniforge.sh -b -f -p "${HOME}/conda"
rm install-miniforge.sh

source "${HOME}/conda/etc/profile.d/conda.sh"

# Initialize conda for the shells.
"${HOME}/conda/bin/conda" init bash zsh

echo "Creating POCS conda environment"
"${HOME}/conda/bin/conda" create -y -q -n "${CONDA_ENV_NAME}" python=3.12

# Activate by default
echo "conda activate ${CONDA_ENV_NAME}" >>"${HOME}/.zshrc"
