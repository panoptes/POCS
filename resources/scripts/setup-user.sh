#!/usr/bin/env bash

PANUSER="${PANUSER:-$USER}"
DEFAULT_GROUPS="dialout,plugdev,input,sudo"

function setup_user() {
  sudo usermod -aG "${DEFAULT_GROUPS}" "${PANUSER}"

  # Add an SSH key if one doesn't exist.
  if [[ ! -f "${HOME}/.ssh/id_rsa" ]]; then
    echo "Adding ssh key"
    ssh-keygen -t rsa -N "" -f "${HOME}/.ssh/id_rsa"
  fi
}

setup_user
