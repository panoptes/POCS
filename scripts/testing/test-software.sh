#!/bin/bash -e

clear;

cat << EOF
Beginning test of POCS software.  This will start a single docker container, mapping the
host $PANDIR into the running docker container, which allows for testing of any local changes.

You can view the output for the tests in a separate terminal:

grc tail -F ${PANDIR}/log/pytest-all.log

The tests will start by updating: ${PANDIR}/POCS/requirements.txt

Tests will begin in 5 seconds. Press Ctrl-c to cancel.
EOF

sleep 5;

docker run --rm -it -v /var/panoptes/:/var/panoptes gcr.io/panoptes-survey/pocs \
    /bin/zsh -ic "scripts/testing/run-tests.sh"
