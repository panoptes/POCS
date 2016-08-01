#!/usr/bin/env bash

if [ -z ${PANDIR+x} ]; then
	echo 'PANDIR="/var/panoptes"; export PANDIR' >> $HOME/.profile
	source $HOME/.profile
	echo "Setting PANDIR=$PANDIR"
fi

if [ ! -d $PANDIR ]; then
	echo "Creating $PANDIR"
	sudo mkdir -p ${PANDIR}/logs
	sudo chown -R 777 $PANDIR
	sudo chown -R $USER:$USER $PANDIR
fi

if [ -z ${POCS+x} ]; then
	echo 'POCS="$PANDIR/POCS"; export POCS' >> $HOME/.profile
	source $HOME/.profile
	echo "Setting POCS=$POCS"
fi

if [ ! -d $POCS ]; then
	echo "Getting POCS from github"
	cd $PANDIR
	git clone https://github.com/panoptes/POCS.git
fi


