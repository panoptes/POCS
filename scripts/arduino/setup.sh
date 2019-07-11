#/bin/bash -e 

arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli lib install OneWire
arduino-cli lib install DallasTemperature
arduino-cli lib install "Adafruit Unified Sensor"
arduino-cli lib install "DHT sensor library"
arduino-cli lib install "ArduinoJson"

