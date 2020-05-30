#!/bin/bash -e

clear;

cat << EOF
Beginning test of pocs software. This software is run inside a virtualized docker
container that has all of the required dependencies installed.

This will start a single docker container, mapping the host $PANDIR into the running docker
container, which allows for testing of any local changes.

You can view the output for the tests in a separate terminal:

grc tail -F ${PANDIR}/log/pytest-all.log

The tests will start by updating: ${PANDIR}/pocs/requirements.txt inside the container.

Tests will begin in 5 seconds. Press Ctrl-c to cancel.
EOF

sleep 5;

docker run --rm -it \
    -e LOCAL_USER_ID=$(id -u) \
    -v /var/panoptes/POCS:/var/panoptes/POCS \
    -v /var/panoptes/logs:/var/panoptes/logs \
    pocs:testing \
    "/var/panoptes/POCS/scripts/testing/run-tests.sh"

