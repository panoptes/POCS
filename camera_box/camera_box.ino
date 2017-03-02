
#include <Wire.h>
#include <stdlib.h>
#include <Adafruit_MMA8451.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>

#define DHT_TYPE DHT22 // DHT 22  (AM2302)

/* DECLARE PINS */
const int  DHT_PIN 9;      // DHT Temp & Humidity Pin
const int CAM_01_RELAY = 5;
const int CAM_02_RELAY = 6;
const int RESET_PIN = 12;


/* CONSTANTS */
Adafruit_MMA8451 accelerometer = Adafruit_MMA8451();

// Setup DHT22
DHT dht(DHT_PIN, DHT_TYPE);

int led_value = LOW;

void setup(void) {
  Serial.begin(9600);
  Serial.flush();

  // Turn off LED inside camera box
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  // Setup Camera relays
  pinMode(CAM_01_RELAY, OUTPUT);
  pinMode(CAM_02_RELAY, OUTPUT);

  pinMode(RESET_PIN, OUTPUT);  

  // Turn on Camera relays
  turn_pin_on(CAM_01_RELAY);
  turn_pin_on(CAM_02_RELAY);

  if (! accelerometer.begin()) {
    while (1);
  }

  dht.begin();

  // Check Accelerometer range
  // accelerometer.setRange(MMA8451_RANGE_2_G);
  // Serial.print("Accelerometer Range = "); Serial.print(2 << accelerometer.getRange());
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
  while (Serial.available() > 0) {
    int pin_num = Serial.parseInt();
    int pin_status = Serial.parseInt();

    switch (pin_num) {
    case CAM_01_RELAY:
    case CAM_02_RELAY:
      if (pin_status == 1) {
        turn_pin_on(pin_num);
      } else {
        turn_pin_off(pin_num);
      }
      break;
    case RESET_PIN:
      if (pin_status == 1) {
        turn_pin_off(RESET_PIN);
      }
      break;
    case LED_BUILTIN:
      digitalWrite(pin_num, pin_status);
      break;
    }
  }

  // Begin reading values and outputting as JSON string
  Serial.print("{");

  read_accelerometer(); Serial.print(',');

  read_dht_temp(); Serial.print(",");

  Serial.print("\"count\":"); Serial.print(millis());

  Serial.println("}");

  Serial.flush();
  delay(1000);

  while (1){
    Serial.println("Waiting on reset");  // Lock-up so that watchdog trips reset
  }  
}

/* ACCELEROMETER */
void read_accelerometer() {
  /* Get a new sensor event */
  sensors_event_t event;
  accelerometer.getEvent(&event);
  uint8_t o = accelerometer.getOrientation(); // Orientation

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

void turn_pin_on(int camera_pin) {
  digitalWrite(camera_pin, HIGH);
}

void turn_pin_off(int camera_pin) {
  digitalWrite(camera_pin, LOW);
}
