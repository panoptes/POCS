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

sleep "${SLEEP_TIME:-5}"

# Hard-coded paths are *inside* the docker image and should not be changed.
docker run --rm -i \
  --init \
  --network "host" \
  -e "PANOPTES_CONFIG_FILE=/var/panoptes/POCS/tests/testing.yaml" \
  -e "PANOPTES_CONFIG_HOST=0.0.0.0" \
  -e "PANOPTES_CONFIG_PORT=8765" \
  -v "${POCS}":/var/panoptes/POCS \
  -v "${PANLOG}":/var/panoptes/logs \
  panoptes-pocs:develop \
  "/var/panoptes/POCS/scripts/testing/run-tests.sh"

echo "test output dir ${PANLOG}:"
ls "${PANLOG}/panoptes-testing.log"
