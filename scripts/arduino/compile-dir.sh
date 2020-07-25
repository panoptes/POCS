#/bin/bash -e 

BOARD=${1:-uno}

arduino-cli compile --fqbn "arduino:avr:${BOARD}" .

