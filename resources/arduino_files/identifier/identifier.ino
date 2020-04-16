#include "OneWire.h"
#include "DallasTemperature.h"

//Declare suspected ds18 pin
const int DS18_PIN = 11;

//Declare number of ds18 sensors
const int NUM_DS18 = 3;

uint8_t sensors_address[NUM_DS18][8];

OneWire ds(DS18_PIN);
DallasTemperature sensors(&ds);

void setup() {
  Serial.begin(9600);
  Serial.flush();


  sensors.begin();
}

void loop() {
  delay(100);
  sensors.requestTemperatures();

  float temps[3];
  for (int x = 0; x < NUM_DS18; x++) {
  temps[x] = sensors.getTempCByIndex(x);
  }
  Serial.print("\n");
  Serial.print("\"temps\":[");
  Serial.print(temps[0], 2); Serial.print(',');
  Serial.print(temps[1], 2); Serial.print(',');
  Serial.print(temps[2], 2);
  Serial.print("]");
}
