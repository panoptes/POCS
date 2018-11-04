#!/bin/bash -ex

THIS_DIR="$(dirname "$(readlink -f "${0}")")"

source "${THIS_DIR}/install-functions.sh"

DO_CONDA="${DO_CONDA:-1}"
DO_REBUILD_CONDA_ENV="${DO_REBUILD_CONDA_ENV:-0}"
DO_INSTALL_CONDA_PACKAGES="${DO_INSTALL_CONDA_PACKAGES:-1}"
DO_PIP_REQUIREMENTS="${DO_PIP_REQUIREMENTS:-1}"

if [ -n "${REQUIREMENTS_PATH}" ] ; then
  if [ -n "${POCS}" ] ; then
    REQUIREMENTS_PATH="${POCS}/requirements.txt"
  else
    REQUIREMENTS_PATH="${THIS_DIR}/requirements.txt"
  fi
fi

# Install Conda, a Python package manager from Anaconda, Inc. Supports both
# pure Python packages (just as pip does) and packages with non-Python parts
# (e.g. native libraries).
if [[ "${DO_CONDA}" -eq 1 ]] ; then
  maybe_install_conda
fi

if [[ -f "${CONDA_SH}" ]] ; then
  . "${CONDA_SH}"
else
  echo_bar
  echo "
Error: conda is not installed, but remaining installation steps make
use of the conda environment for PANOPTES (panoptes-env).
"
  exit 1
fi

if [[ "${DO_CONDA}" -eq 1 || \
      "${DO_REBUILD_CONDA_ENV}" -eq 1 || \
      "${DO_INSTALL_CONDA_PACKAGES}" -eq 1 ]] ; then
  prepare_panoptes_conda_env
fi

# Activate the PANOPTES environment in this shell.
conda activate panoptes-env

# Install pure Python packages using pip; note that we prefer to
# install these with conda if they are available that way, as we
# try to reduce the number of package managers and repositories
# we have to deal with.
if [[ "${DO_PIP_REQUIREMENTS}" -eq 1 ]] ; then
  echo_bar
  echo
  echo "Upgrading pip before installing other python packages."
  pip install --quiet --upgrade pip

  echo_bar
  echo
  echo "Installing python packages using pip."
  pip install --quiet --requirement "${REQUIREMENTS_PATH}"
fi
