#!/usr/bin/env bash

# Set up passwordless sudo for all sudo group.
echo "Setting up passwordless sudo for users in the sudo group."
echo "%panoptes ALL=(ALL) NOPASSWD: ALL" | sudo tee -a /etc/sudoers.d/panoptes

# Add an SSH key if one doesn't exist.
echo "Creating SSH key if needed."
if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
  echo "Adding ssh key"
  ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa"
fi
