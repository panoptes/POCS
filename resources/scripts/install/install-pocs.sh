#!/usr/bin/env bash

CODE_BRANCH=${CODE_BRANCH:-"develop"}
PANDIR="${PANDIR:-${HOME}/POCS}"

echo "Installing hatch."
wget -q https://github.com/pypa/hatch/releases/latest/download/hatch-x86_64-unknown-linux-gnu.tar.gz -O hatch.tgz
tar zxvf hatch.tgz && rm hatch.tgz
mv hatch "${HOME}/bin/hatch"
chmod +x "${HOME}/bin/hatch"

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
${HOME}/bin/hatch run pip install -e ".[all]"

echo "Creating POCS directories."
mkdir -p "${HOME}/logs"
mkdir -p "${HOME}/images"
mkdir -p "${HOME}/json_store"
mkdir -p "${HOME}/keys"

# Link the needed POCS folders.
ln -s "${PANDIR}/conf_files" "${HOME}"
ln -s "${PANDIR}/resources" "${HOME}"
ln -s "${PANDIR}/notebooks" "${HOME}"
