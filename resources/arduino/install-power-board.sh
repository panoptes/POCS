#!/usr/bin/env bash

FQBN="${FQBN:-arduino:avr:uno}"
SKETCH_LOCATION="${SKETCH_LOCATION:-PowerBoard}"
ARDUINO_PORT="${ARDUINO_PORT:-/dev/ttyACM0}"
DO_UPLOAD="${DO_UPLOAD:-true}"

# Change to the directory of this script.
cd "$(dirname "${BASH_SOURCE[0]}")" || { echo "Could not change to script directory."; exit 1; }

arduino-cli compile -b "${FQBN}" "${SKETCH_LOCATION}"
if [ "${DO_UPLOAD}" = "true" ]; then
  arduino-cli upload -p "${ARDUINO_PORT}" -b "${FQBN}" "${SKETCH_LOCATION}"
fi
