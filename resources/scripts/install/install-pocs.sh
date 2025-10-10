#!/usr/bin/env bash

CODE_BRANCH=${CODE_BRANCH:-"develop"}
PANDIR="${PANDIR:-${HOME}/POCS}"

# Check if PANDIR exists and if not, clone.
if [ -d "${PANDIR}" ]; then
  echo "POCS repo already exists."
else
  echo "Cloning POCS repo."
  cd
  git clone --depth 1 https://github.com/panoptes/POCS "${PANDIR}"
  cd "${PANDIR}"
  git checkout "${CODE_BRANCH}"
  cd
fi

echo "Installing POCS"
cd "$PANDIR"
/home/panoptes/.local/bin/hatch run pip install -e ".[all]"

echo "Creating POCS directories."
mkdir -p "${HOME}/logs"
mkdir -p "${HOME}/images"
mkdir -p "${HOME}/json_store"
mkdir -p "${HOME}/keys"

# Link the needed POCS folders.
ln -s "${PANDIR}/conf_files" "${HOME}"
ln -s "${PANDIR}/resources" "${HOME}"
ln -s "${PANDIR}/notebooks" "${HOME}"

# Create a symlink to the bin dir for our hatch environment.
ln -s "$(/home/panoptes/.local/bin/hatch env find default)/bin/" "${HOME}/"
echo "source ${HOME}/bin/activate" >> "${HOME}/.bashrc"
echo "source ${HOME}/bin/activate" >> "${HOME}/.zshrc"
