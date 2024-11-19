#!/usr/bin/env bash

PANUSER="${PANUSER:-$USER}"
PANDIR="${PANDIR:-${HOME}/pocs}"

function install_services() {
  echo "Installing supervisor services."

  # Make supervisor read our conf file at its current location.
  echo "files = ${HOME}/conf_files/pocs-supervisord.conf" | sudo tee -a /etc/supervisor/supervisord.conf

  # Change the user and home directory.
  sed -i "s/chown=panoptes:panoptes/chown=${PANUSER}:${PANUSER}/g" "${HOME}/conf_files/pocs-supervisord.conf"
  sed -i "s/user=panoptes/user=${PANUSER}/g" "${HOME}/conf_files/pocs-supervisord.conf"
  sed -i "s|/home/panoptes|${HOME}|g" "${HOME}/conf_files/pocs-supervisord.conf"

  # Reread the supervisord conf and restart.
  sudo supervisorctl reread
  sudo supervisorctl update
}

install_services
