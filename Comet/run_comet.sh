#!/bin/sh

/usr/bin/env twistd -n comet \
	--verbose						\
	--recieve						\
	--local-ivo=ivo://fpstoolstest/foo#bar			\
	--remote=voevent.4pisky.org				\
	--save-event-directory=~/huntsman/Comet/incoming_vo	\
	--cmd=python alert_pocs.py

