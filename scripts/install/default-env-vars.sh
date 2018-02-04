#!/bin/bash

[[ -z "$PANUSER" ]] && export PANUSER=panoptes     # Default user
[[ -z "$PANDIR" ]] && export PANDIR=/var/panoptes  # Main Dir
[[ -z "$PANLOG" ]] && export PANLOG=$PANDIR/logs   # Log files
[[ -z "$POCS" ]] && export POCS=$PANDIR/POCS       # Main Observatory Control
[[ -z "$PAWS" ]] && export PAWS=$PANDIR/PAWS       # Web Interface