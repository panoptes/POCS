#!/usr/bin/env bash

echo "Installing system dependencies."

# Clean up problems.
sudo apt-get update --fix-missing -y

# Upgrade.
sudo apt-get -y full-upgrade

sudo apt-get -y install --no-install-recommends \
  ack \
  astrometry.net \
  astrometry-data-tycho2-10-19 \
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
  sudo \
  supervisor \
  vim-nox \
  wget \
  zsh

sudo apt-get -y autoremove
