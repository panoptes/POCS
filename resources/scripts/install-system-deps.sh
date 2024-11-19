#!/usr/bin/env bash

function system_deps() {
  echo "Installing system dependencies."

  # Set up passwordless sudo for all sudo group.
  echo "%sudo ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/panoptes

  # Clean up problems.
  sudo apt-get -y -qq purge needrestart
  sudo apt-get update --fix-missing -y -qq
  sudo apt-get -y -qq full-upgrade

  sudo apt-get -y -qq install \
    ack \
    astrometry.net \
    astrometry-data-tycho2-10-19 \
    byobu \
    curl \
    dcraw \
    exiftool \
    fonts-powerline \
    gcc \
    gphoto2 \
    htop \
    httpie \
    jo \
    jq \
    libcfitsio-bin \
    make \
    nano \
    vim-nox \
    supervisor \
    wget \
    zsh
  sudo apt-get -y -qq autoremove
}

system_deps
