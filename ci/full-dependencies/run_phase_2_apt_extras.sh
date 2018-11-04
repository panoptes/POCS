#!/bin/bash -ex

# Install dependencies that are less stable; i.e. ones that we
# might want to change the package spec for more often. 

declare -a PACKAGES=(
  # Package description...

  # Apparently needed for cython

)

if [ ${#PACKAGES[@]} -ne 0 ] ; then
  echo "Installing extra packages."

  # Suppress prompting for input during package processing.
  export DEBIAN_FRONTEND=noninteractive

  # Update the information we know about package versions.
  apt-get update --fix-missing

  apt-get install --no-install-recommends --yes "${PACKAGES[@]}"

  # Docker best practices calls for cleaning the apt cache before
  # the end of this RUN so that it is not stored in the image.
  rm -rf /var/lib/apt/lists/*
else
  echo "No extra packages are listed."
fi
