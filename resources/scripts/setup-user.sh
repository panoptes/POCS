#!/usr/bin/env bash

# Set up passwordless sudo for all sudo group.
echo "%sudo ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/panoptes

# Add an SSH key if one doesn't exist.
if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
  echo "Adding ssh key"
  ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa"
fi
