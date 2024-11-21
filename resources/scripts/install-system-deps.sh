#!/usr/bin/env bash

echo "Installing system dependencies."

# Clean up problems.
sudo apt-get update --fix-missing -y

# Upgrade.
sudo apt-get -y full-upgrade

sudo apt-get -y install \
  ack \
  astrometry.net \
  astrometry-data-tycho2-10-19 \
  byobu \
  curl \
  dcraw \
  exiftool \
  fonts-powerline \
  gcc \
  git \
  gphoto2 \
  htop \
  httpie \
  jo \
  jq \
  libcfitsio-bin \
  make \
  nano \
  supervisor \
  vim-nox \
  wget \
  zsh

sudo apt-get -y autoremove
