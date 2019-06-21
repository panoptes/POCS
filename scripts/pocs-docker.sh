#!/bin/bash -e

usage() {
  echo -n "##################################################
# Start POCS via Docker.
#
##################################################

 $ $(basename $0) [COMMAND]

 Options:
  COMMAND 	These options are passed at the end of the docker-compose command.
  			To start all service simply pass 'up'.

 Examples:

	# Start all services in the foreground.
	$POCS/scripts/pocs-docker.sh up

 	# Start config-server and messaging-hub serivces in the background.
	$POCS/scripts/pocs-docker.sh up --no-deps -d config-server messaging-hub

 	# Read the logs from the config-server
	$POCS/scripts/pocs-docker.sh logs config-server

    # Run the software tests (no hardware)
    $POCS/scripts/pocs-docker.sh up
"
}

START=${1:-help}
if [ "${START}" = 'help' ] || [ "${START}" = '-h' ] || [ "${START}" = '--help' ]; then
	usage
	exit 1
fi

cd "$PANDIR"
docker-compose \
    	--project-directory "${PANDIR}" \
	-f panoptes-utils/docker/docker-compose.yaml \
	-f PAWS/docker/docker-compose.yaml \
	-f POCS/docker/docker-compose.yaml \
	-p panoptes "$@"

