#!/bin/bash -e

# TODO Make sure we are being run from $POCS root.
clear;

cat << EOF
POCS Software Testing

This script runs the POCS testing suite in a virtualized environment using docker images.

The pocs:testing image will be built on your local machine if needed, then the tests will be
run inside the virtualized container.

The $PANDIR directory will be mapped into the running docker container, which allows for testing local changes.

You can view the output for the tests in a separate terminal:

tail -F ${PANDIR}/log/panoptes-testing.log

The tests will start by updating: ${POCS}/requirements.txt

Tests will begin in 5 seconds. Press Ctrl-c to cancel.
EOF

sleep 5;

# Build the testing container.
docker build \
    -t pocs:testing \
    -f docker/latest.Dockerfile \
    .

# TODO Have the option to map just $POCS instead of $PANDIR.

docker run --rm -it \
    -e PANDIR=/var/panoptes \
    -e POCS=/var/panoptes/POCS \
    -e LOCAL_USER_ID=$(id -u) \
    -v $PANDIR:/var/panoptes \
    pocs:testing \
    "/var/panoptes/POCS/scripts/testing/run-tests.sh"
