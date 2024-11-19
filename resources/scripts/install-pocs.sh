#!/usr/bin/env bash

CODE_BRANCH=${CODE_BRANCH:-"develop"}
PANDIR="${PANDIR:-${HOME}/POCS}"

function get_pocs_repo() {
  # Check if PANDIR exists and if not, clone.
  if [ -d "${PANDIR}" ]; then
    echo "POCS repo already exists."
    return
  fi

  echo "Cloning POCS repo."
  git clone https://github.com/panoptes/POCS "${PANDIR}"
  cd "${PANDIR}"
  git checkout "${CODE_BRANCH}"
  cd
}

function make_directories() {
  echo "Creating directories."
  mkdir -p "${HOME}/logs"
  mkdir -p "${HOME}/images"
  mkdir -p "${HOME}/json_store"
  mkdir -p "${HOME}/keys"

  # Link the needed POCS folders.
  ln -s "${PANDIR}/conf_files" "${HOME}"
  ln -s "${PANDIR}/resources" "${HOME}"
  ln -s "${PANDIR}/notebooks" "${HOME}"
}

get_pocs_repo
make_directories
