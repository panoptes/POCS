#!/bin/sh

# This file is to be copied into /etc/profile.d/ and SOURCED by
# /etc/rc.local. We have the shebang line at the top to help shellcheck
# recognize the type of script.

export PANUSER=panoptes          # User that runs PANOPTES software.
export PANDIR=/var/panoptes      # Main directory.
export PANLOG="${PANDIR}/logs"   # Log file storage.
export POCS="${PANDIR}/POCS"     # PANOPTES Observatory Control Software
export PAWS="${PANDIR}/PAWS"     # PANOPTES Web Interface
