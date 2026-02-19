#!/usr/bin/env bash

echo "Installing system dependencies."

# Clean up problems.
sudo DEBIAN_FRONTEND=noninteractive apt-get update --fix-missing -y

# Upgrade.
sudo DEBIAN_FRONTEND=noninteractive apt-get -y \
  -o Dpkg::Options::="--force-confdef" \
  -o Dpkg::Options::="--force-confold" \
  full-upgrade

sudo DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
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
  pipx \
  python3-dev \
  starship \
  sudo \
  supervisor \
  vim-nox \
  wget \
  zsh

sudo DEBIAN_FRONTEND=noninteractive apt-get -y autoremove

# Set zsh as the default shell for the current user.
sudo chsh --shell /usr/bin/zsh "${USER}"
