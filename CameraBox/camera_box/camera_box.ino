#include <stdlib.h>
#include <Wire.h>
#include <Adafruit_MMA8451.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>

#define DHTPIN 4 // DHT Temp & Humidity Pin
#define DHTTYPE DHT22   // DHT 22  (AM2302)

Adafruit_MMA8451 mma = Adafruit_MMA8451();

DHT dht(DHTPIN, DHTTYPE);

void setup(void) {
  Serial.begin(9600);
  
  pinMode(5, OUTPUT);  
  pinMode(6, OUTPUT);    
  pinMode(13, OUTPUT);

  digitalWrite(5, HIGH);  
  digitalWrite(6, HIGH);    

  Serial.println("PANOPTES Arduino Code for Electronics");

  if (! mma.begin()) {
    Serial.println("Couldn't start Accelerometer");
    while (1);
  }
  Serial.println("MMA8451 Accelerometer found");

  dht.begin();
  Serial.println("DHT22found");

  // Check Accelerometer range
  mma.setRange(MMA8451_RANGE_2_G);
  Serial.print("Accelerometer Range = "); Serial.print(2 << mma.getRange());
  Serial.println("G");

  Serial.println("Data output is:");

}

void loop() {

  digitalWrite(13, HIGH);   // turn the LED on (HIGH is the voltage level)
  delay(1000);              // wait for a second
  digitalWrite(13, LOW);    // turn the LED off by making the voltage LOW
  delay(1000);              // wait for a second
  
  Serial.print("{");
  read_accelerometer();
  Serial.print(',');
  read_temperature();
  Serial.print("}");

  Serial.println();

//  delay(3000); // Three second
}

void read_accelerometer() {
  /* ACCELEROMETER */
  /* Get a new sensor event */
  sensors_event_t event;
  mma.getEvent(&event);
  uint8_t o = mma.getOrientation(); // Orientation

  Serial.print("\"accelerometer\":{");
  Serial.print("\"x\":"); Serial.print(event.acceleration.x); Serial.print(',');
  Serial.print("\"y\":"); Serial.print(event.acceleration.y); Serial.print(',');
  Serial.print("\"z\":"); Serial.print(event.acceleration.z); Serial.print(',');
  Serial.print("\"o\": "); Serial.print(o);
  Serial.print('}');
}
//
//// Reading temperature or humidity takes about 250 milliseconds!
//// Sensor readings may also be up to 2 seconds 'old' (its a very slow sensor)
void read_temperature() {
  float h = dht.readHumidity();
  float c = dht.readTemperature(); // Celsius

  // Check if any reads failed and exit early (to try again).
  // if (isnan(h) || isnan(t)) {
  //   Serial.println("Failed to read from DHT sensor!");
  //   return;
  // }

  Serial.print("\"temperature\":{");
  Serial.print("\"h\":"); Serial.print(h); Serial.print(',');
  Serial.print("\"c\":"); Serial.print(c);
  Serial.print('}');
}
