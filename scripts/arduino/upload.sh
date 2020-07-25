#/bin/bash -e 

DEVICE=${1:-/dev/ttyACM0}
BOARD=${2:-uno}

arduino-cli upload -p "${DEVICE}" --fqbn "arduino:avr:${BOARD}" .


