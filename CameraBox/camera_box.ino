#include <stdlib.h>
#include <Wire.h>
#include <Adafruit_MMA8451.h>
#include <Adafruit_Sensor.h>

Adafruit_MMA8451 mma = Adafruit_MMA8451();

void setup(void) {
  Serial.begin(9600);

  Serial.println("PANOPTES Arduino Code for Electronics");

  if (! mma.begin()) {
    Serial.println("Couldnt start Accelerometer");
    while (1);
  }
  Serial.println("MMA8451 Accelerometer found");

  mma.setRange(MMA8451_RANGE_2_G);

  Serial.print("Range = "); Serial.print(2 << mma.getRange());
  Serial.println("G");

}

void loop() {

 read_accelerometer();

 Serial.println();

  delay(1000); // One second
}


void read_accelerometer() {
  /* ACCELEROMETER */
  /* Get a new sensor event */
  sensors_event_t event;
  mma.getEvent(&event);
  uint8_t o = mma.getOrientation(); // Orientation

  Serial.print(event.acceleration.x); Serial.print(':');
  Serial.print(event.acceleration.y); Serial.print(':');
  Serial.print(event.acceleration.z); Serial.print(':');
  Serial.print(o);
}