#include "dht_handler.h"

DHTHandler::DHTHandler(uint8_t pin, uint8_t type)
    : dht_(pin, type), humidity_(-1000), temperature_(-1000) {}

void DHTHandler::Init() {
  dht_.begin();
}

void DHTHandler::Collect() {
  // Force readHumidity to actually talk to the device;
  // otherwise will read at most every 2 seconds, which
  // is sometimes just a little too far apart.
  // Note that the underlying read() routine has some big
  // delays (250ms and 40ms, plus some microsecond scale delays).
  humidity_ = dht_.readHumidity(/*force=*/true);
  // readTemperature will use the data collected by
  // readHumidity, which is just fine.
  temperature_ = dht_.readTemperature();
}

void DHTHandler::Report() {
  // This is being added to a JSON dictionary, so print a comma
  // before the quoted name, which is then followed by a colon.
  Serial.print(", \"humidity\":");
  Serial.print(humidity_);
  Serial.print(", \"temp_00\":");
  Serial.print(temperature_);
}
