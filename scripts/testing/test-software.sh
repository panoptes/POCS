#!/usr/bin/env bash

clear

cat <<EOF
Beginning test of panoptes-pocs software. This software is run inside a virtualized docker
container that has all of the required dependencies installed.

This will start a single docker container, mapping the host PANDIR=${PANDIR} into the running docker
container, which allows for testing of any local changes.

You can view the output for the tests in a separate terminal:

tail -F ${PANDIR}/logs/panoptes-testing.log

Tests will begin in 5 seconds. Press Ctrl-c to cancel.
EOF

SLEEP_TIME=${1:-5}

sleep "${SLEEP_TIME}"

docker run --rm -it \
  --init \
  -v "${PANDIR}/POCS":/var/panoptes/POCS \
  -v "${PANDIR}/logs":/var/panoptes/logs \
  panoptes-pocs:develop \
  "/var/panoptes/POCS/scripts/testing/run-tests.sh"
