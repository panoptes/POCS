#!/bin/sh
source activate py27

/usr/bin/env twistd -n comet \
	--verbose						\
	--receive			\
	--local-ivo=ivo://fpstoolstest/foo#bar			\
	--remote=voevent.4pisky.org				\
	--save-event-directory=$POCS/Comet/incoming_vo/	\
	--cmd=python\ alert_pocs.py

