#!/bin/bash -ex

# Install dependencies related specifically to testing POCS.

# Suppress prompting for input during package processing.
export DEBIAN_FRONTEND=noninteractive

# Update the information we know about package versions.
apt-get update --fix-missing

declare -a PACKAGES=(
    #
    # Astrometry and cfitsio.
    # Not sure if libcfitsio-dev is directly needed.
    #
    astrometry.net "astrometry-data-*" libcfitsio-bin libcfitsio-dev
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
    wget
)

apt-get install --no-install-recommends --yes "${PACKAGES[*]}"

# Docker best practices calls for cleaning the apt cache before
# the end of this RUN so that it is not stored in the image.
rm -rf /var/lib/apt/lists/*
