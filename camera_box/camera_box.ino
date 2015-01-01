#include <Wire.h>
#include <stdlib.h>
#include <Adafruit_MMA8451.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>

#define DHTPIN 4 // DHT Temp & Humidity Pin
#define DHTTYPE DHT22   // DHT 22  (AM2302)


const int CAM_01_PIN = 5;
const int CAM_02_PIN = 6;

int led_value = LOW;

Adafruit_MMA8451 mma = Adafruit_MMA8451();

DHT dht(DHTPIN, DHTTYPE);

void setup(void) {
  Serial.begin(9600);
  Serial.flush();

  // Turn off LED inside camera box
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  // Setup Camera relays
  pinMode(CAM_01_PIN, OUTPUT);
  pinMode(CAM_02_PIN, OUTPUT);

  // Turn on Camera relays
  turn_camera_on(CAM_01_PIN);
  turn_camera_on(CAM_02_PIN);

  if (! mma.begin()) {
    while (1);
  }

  dht.begin();

  // Check Accelerometer range
  // mma.setRange(MMA8451_RANGE_2_G);
  // Serial.print("Accelerometer Range = "); Serial.print(2 << mma.getRange());
  // Serial.println("G");
}

void loop() {

  // Read any serial input
  //    - Input will be two comma separated integers, the
  //      first specifying the pin and the second the status
  //      to change to (1/0). Cameras and debug led are
  //      supported.
  //      Example serial input:
  //           4,1   # Turn fan on
  //          13,0   # Turn led off
  while(Serial.available() > 0){
      int pin_num = Serial.parseInt();
      int pin_status = Serial.parseInt();

      switch(pin_num){
        case CAM_01_PIN:
          if(pin_status == 1){
            turn_camera_on(CAM_01_PIN);
          } else {
            turn_camera_off(CAM_01_PIN);
          }
          break;
        case CAM_02_PIN:
          if(pin_status == 1){
            turn_camera_on(CAM_02_PIN);
          } else {
            turn_camera_off(CAM_02_PIN);
          }
          break;
        case LED_BUILTIN:
          digitalWrite(pin_num, pin_status);
          break;
      }
  }

  Serial.print("{");

  read_accelerometer(); Serial.print(',');

  read_dht_temp(); Serial.print(",");

  Serial.print("\"count\":"); Serial.print(millis());

  Serial.println("}");

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

  Serial.print("\"humidity\":"); Serial.print(h); Serial.print(',');
  Serial.print("\"temp_01\":"); Serial.print(c);
}

/************************************
* Utitlity Methods
*************************************/

void toggle_led() {
  led_value = ! led_value;
  digitalWrite(LED_BUILTIN, led_value);
}

void turn_camera_on(int camera_pin) {
  digitalWrite(camera_pin, HIGH);
}

void turn_camera_off(int camera_pin) {
  digitalWrite(camera_pin, LOW);
}
