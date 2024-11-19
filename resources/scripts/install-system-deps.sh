#!/usr/bin/env bash

echo "Installing system dependencies."

# Clean up problems.
apt-get update --fix-missing -y

# Upgrade.
apt-get -y full-upgrade

apt-get -y install \
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
  python3 \
  python3-pip \
  supervisor \
  vim-nox \
  wget \
  zsh

apt-get -y autoremove
