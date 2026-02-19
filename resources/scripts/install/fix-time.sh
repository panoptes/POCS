#!/usr/bin/env bash

# We use htpdate below so this just needs to be a public url w/ trusted time.
TIME_SERVER="${TIME_SERVER:-google.com}"

function fix_time() {
  echo "Syncing time."
  DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq htpdate
  sudo timedatectl set-ntp false
  sudo /usr/sbin/htpdate -as "${TIME_SERVER}"
  sudo timedatectl set-ntp true

  # Add crontab entries for reboot and every hour.
  (
    sudo crontab -l 2>/dev/null || true
    echo "@reboot /usr/sbin/htpdate -as ${TIME_SERVER}"
    echo "13 * * * * /usr/sbin/htpdate -s ${TIME_SERVER}"
  ) | sudo crontab -

  # Show updated time.
  timedatectl
}

fix_time
