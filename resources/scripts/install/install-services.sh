#!/usr/bin/env bash

echo "Installing supervisor services."

# Make supervisor read our conf file at its current location.
echo "files = ${HOME}/conf_files/pocs-supervisord.conf" | sudo tee -a /etc/supervisor/supervisord.conf

# Change the user and home directory.
sed -i "s/chown=panoptes:panoptes/chown=${USER}:${USER}/g" "${HOME}/conf_files/pocs-supervisord.conf"
sed -i "s/user=panoptes/user=${USER}/g" "${HOME}/conf_files/pocs-supervisord.conf"
sed -i "s|/home/panoptes|${HOME}|g" "${HOME}/conf_files/pocs-supervisord.conf"

# Reread the supervisord conf and restart.
sudo supervisorctl reread
sudo supervisorctl update
