#!/usr/bin/env bash

CONDA_URL="micro.mamba.pm/install.sh"
PANDIR="${PANDIR:-${HOME}/POCS}"

echo "Installing micromamba"

wget -q "${CONDA_URL}" -O install-micromamba.sh
sh install-micromamba.sh
rm install-micromamba.sh
