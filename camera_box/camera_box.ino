#include <Wire.h>
#include <stdlib.h>
#include <Adafruit_MMA8451.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>

#define DHTPIN 4 // DHT Temp & Humidity Pin
#define DHTTYPE DHT22   // DHT 22  (AM2302)

int CAM_01_PIN = 5;
int CAM_02_PIN = 6;

int led_pin = 13;
int led_value = LOW;

Adafruit_MMA8451 mma = Adafruit_MMA8451();

DHT dht(DHTPIN, DHTTYPE);

void setup(void) {
  Serial.begin(9600);

  // Setup Camera relays
  pinMode(CAM_01_PIN, OUTPUT);
  pinMode(CAM_02_PIN, OUTPUT);

  // Turn on Camera relays
  turn_camera_on(CAM_01_PIN);
  turn_camera_on(CAM_02_PIN);

  Serial.println("PANOPTES Arduino Code for Electronics");

  if (! mma.begin()) {
    Serial.println("Couldn't start Accelerometer");
    while (1);
  } else {
    Serial.println("MMA8451 Accelerometer found");
  }

  dht.begin();
  Serial.println("DHT22found");

  // Check Accelerometer range
  mma.setRange(MMA8451_RANGE_2_G);
  Serial.print("Accelerometer Range = "); Serial.print(2 << mma.getRange());
  Serial.println("G");

}

void loop() {

  Serial.print("{");
  read_accelerometer();
  Serial.print(',');
  read_dht_temp();
  Serial.println("}");

  toggle_led();

  delay(1000);
}

/* ACCELEROMETER */
void read_accelerometer() {
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

//// Reading temperature or humidity takes about 250 milliseconds!
//// Sensor readings may also be up to 2 seconds 'old' (its a very slow sensor)
void read_dht_temp() {
  float h = dht.readHumidity();
  float c = dht.readTemperature(); // Celsius

  // Check if any reads failed and exit early (to try again).
  // if (isnan(h) || isnan(t)) {
  //   Serial.println("Failed to read from DHT sensor!");
  //   return;
  // }

  Serial.print("\"humidity\":"); Serial.print(h); Serial.print(',');
  Serial.print("\"temp_01\":"); Serial.print(c); 
}

/************************************
* Utitlity Methods
*************************************/

void toggle_led() {
  led_value = ! led_value;
  digitalWrite(led_pin, led_value);
}

void turn_camera_on(int camera_pin) {
  digitalWrite(camera_pin, HIGH);
}

void turn_camera_off(int camera_pin) {
  digitalWrite(camera_pin, LOW);
}
