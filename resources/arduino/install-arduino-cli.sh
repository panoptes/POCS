#!/usr/bin/env bash

# Check for arduino-cli tool first.
if command -v arduino-cli &> /dev/null; then
  echo "arduino-cli is already installed."
  exit 0
fi

# Make sure we are at home.
cd

# Get the arduino-cli tool and install.
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

"${HOME}/bin/arduino-cli" config init
"${HOME}/bin/arduino-cli" core update-index
"${HOME}/bin/arduino-cli" core install arduino:avr
"${HOME}/bin/arduino-cli" lib install ArduinoJson

# Ask if the user wants to install the power board software.
read -p "Do you want to install the power board software? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  source ./install-power-board.sh
fi
