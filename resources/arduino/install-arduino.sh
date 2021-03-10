#!/usr/bin/env bash

FQBN="${FQBN:-arduino:avr:uno}"
SKETCH_LOCATION="${SKETCH_LOCATION:-PowerBoard}"
ARDUINO_PORT="${ARDUINO_PORT:-/dev/ttyACM0}"

arduino-cli config init
arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli lib install ArduinoJson
arduino-cli compile -b "${FQBN}" "${SKETCH_LOCATION}"
arduino-cli upload -p "${ARDUINO_PORT}" -b "${FQBN}" "${SKETCH_LOCATION}"
