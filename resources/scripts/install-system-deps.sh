#!/usr/bin/env bash

function system_deps() {
  echo "Installing system dependencies."

  # Clean up problems.
  apt-get -y -qq purge needrestart
  apt-get update --fix-missing -y -qq
  apt-get -y -qq full-upgrade

  apt-get -y -qq install \
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
  apt-get -y -qq autoremove
}

system_deps
