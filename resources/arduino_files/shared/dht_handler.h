#ifndef RESOURCES_ARDUINO_FILES_SHARED_DHT_HANDLER_H
#define RESOURCES_ARDUINO_FILES_SHARED_DHT_HANDLER_H

#include <stdlib.h>

#include "DHT.h"

// Reads and reports Humidity & Temperature values.
class DHTHandler {
  public:
    DHTHandler(uint8_t pin, uint8_t type);

    // Initialize communication to the sensor.
    void Init();

    // Read the current values from the sensor.
    void Collect();

    // Print the values. Requires that Collect has been called.
    void Report();

    float humidity() const { return humidity_; }
    float temperature() const { return temperature_; }

  private:
    DHT dht_;
    float humidity_;
    float temperature_;  // Celcius
};

#endif  // RESOURCES_ARDUINO_FILES_SHARED_DHT_HANDLER_H