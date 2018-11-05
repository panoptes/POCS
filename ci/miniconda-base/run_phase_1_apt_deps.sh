#!/bin/bash -ex

# Install dependencies that are very stable.

# Suppress prompting for input during package processing.
export DEBIAN_FRONTEND=noninteractive

# Update the information we know about package versions.
apt-get update --fix-missing

# apt-utils is used later when we install some other packages, so
# reduce the number of error messages from debconf by installing
# this early.
apt-get install --no-install-recommends --yes apt-utils

declare -a PACKAGES=(
  #
  # Tools needed for installing miniconda.
  #
  ca-certificates wget bzip2
)

apt-get install --no-install-recommends --yes "${PACKAGES[@]}"

# Docker best practices calls for cleaning the apt cache before
# the end of this RUN so that it is not stored in the image.
rm -rf /var/lib/apt/lists/*
