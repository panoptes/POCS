#!/bin/bash -e

usage() {
  echo -n "##################################################
# Start POCS via Docker.
# 
##################################################

 $ $(basename $0) [START]
 
 Options:
  START 	Program to start. Currently only option is 'jupyterlab'. If no
  		option is given then start the state machine in the background.
"
}

if [ $# -eq 0 ]; then
	docker-compose \
		-f $POCS/resources/docker_files/docker-compose.yml \
		-p panoptes up
else
	START=${1}

	if [ ${START} = 'help' ] || [ ${START} = '-h' ] || [ ${START} = '--help' ]; then
		usage
		exit 1
	else
		docker-compose \
			-f $POCS/resources/docker_files/docker-compose.yml \
			-f $POCS/resources/docker_files/docker-compose.${START}.yml \
			-p panoptes up
	fi

fi
