#!/usr/bin/env bash

CODE_BRANCH=${CODE_BRANCH:-"develop"}
CONDA_ENV_NAME=conda-pocs
PANDIR="${PANDIR:-${HOME}/POCS}"

# Check if PANDIR exists and if not, clone.
if [ -d "${PANDIR}" ]; then
  echo "POCS repo already exists."
else
  echo "Cloning POCS repo."
  git clone https://github.com/panoptes/POCS "${PANDIR}"
  cd "${PANDIR}"
  git checkout "${CODE_BRANCH}"
  cd
fi

echo "Installing POCS into ${CONDA_ENV_NAME} environment."
"${HOME}/conda/bin/conda" env update -p "${HOME}/conda/envs/${CONDA_ENV_NAME}" -f "${PANDIR}/environment.yaml"

echo "Creating POCS directories."
mkdir -p "${HOME}/logs"
mkdir -p "${HOME}/images"
mkdir -p "${HOME}/json_store"
mkdir -p "${HOME}/keys"

# Link the needed POCS folders.
ln -s "${PANDIR}/conf_files" "${HOME}"
ln -s "${PANDIR}/resources" "${HOME}"
ln -s "${PANDIR}/notebooks" "${HOME}"
