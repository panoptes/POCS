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
  # Time zone and daylight-saving time data
  #
  tzdata
  #
  # Astrometry and cfitsio.
  # Not sure if libcfitsio-dev is directly needed.
  # Not including astrometry-data-* because it is not based on
  # the 2MASS catalog, but instead the Tycho catalog, and our
  # tests fail with it. Instead we need to later copy in the
  # desired index files.
  #
  astrometry.net libcfitsio-bin libcfitsio-dev
  #
  # Not sure if these are needed for testing POCS, or just for running.
  #
  dcraw gphoto2 exiftool
  #
  # Cairo is a graphics library, and matplotlib can use it as a backend
  # for rendering.
  #
  libcairo2-dev
  #
  # Graphviz is used for rendering the state machine of POCS.
  # Not sure if these are needed for testing POCS, or just for running.
  #
  graphviz libgraphviz-dev
  #
  # Improves interaction with pocs_shell (via readline).
  #
  libncurses5-dev
  #
  # Tools needed for installing miniconda.
  #
  ca-certificates wget bzip2
)

apt-get install --no-install-recommends --yes "${PACKAGES[@]}"

# Docker best practices calls for cleaning the apt cache before
# the end of this RUN so that it is not stored in the image.
rm -rf /var/lib/apt/lists/*
