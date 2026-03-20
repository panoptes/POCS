#!/usr/bin/env bash

# Check for arduino-cli tool first.
if command -v arduino-cli &> /dev/null; then
  echo "arduino-cli is already installed."
  exit 0
fi

# Make sure we are at home or give a warning and exit.
cd "$HOME" || { echo "Could not change to home directory."; exit 1; }

# Get the arduino-cli tool and install.
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

"${HOME}/bin/arduino-cli" config init
"${HOME}/bin/arduino-cli" core update-index
"${HOME}/bin/arduino-cli" core install arduino:avr
"${HOME}/bin/arduino-cli" lib install ArduinoJson
