#include <stdlib.h>
#include <OneWire.h>
#include <DallasTemperature.h>


#include <DHT.h>

#define DHTTYPE DHT22   // DHT 22  (AM2302)

/* DECLARE PINS */

// Analog Pins
const int I_MAIN = A1;
const int I_FAN = A2;
const int I_MOUNT = A3;
const int I_CAMERAS = A4;

// Digital Pins
const int AC_PIN = 11;
const int DS18_PIN = 10; // DS18B20 Temperature (OneWire)
const int DHT_PIN = 9; // DHT Temp & Humidity Pin

const int COMP_RELAY = 8; // Computer Relay
const int CAMERAS_RELAY = 7; // Cameras Relay Off: 70s Both On: 800s One On: 350
const int FAN_RELAY = 6; // Fan Relay  Off: 0 On: 80s
const int WEATHER_RELAY = 5; // Weather Relay 250mA upon init and 250mA to read
const int MOUNT_RELAY = 4; // Mount Relay

const int NUM_DS18 = 3; // Number of DS18B20 Sensors


/* CONSTANTS */
/*
For info on the current sensing, see:
  http://henrysbench.capnfatz.com/henrys-bench/arduino-current-measurements/the-acs712-current-sensor-with-an-arduino/
  http://henrysbench.capnfatz.com/henrys-bench/arduino-current-measurements/acs712-current-sensor-user-manual/
*/
const float mV_per_amp = 0.185; 
const float ACS_offset = 0.; 


uint8_t sensors_address[NUM_DS18][8];

// Temperature chip I/O
OneWire ds(DS18_PIN);
DallasTemperature sensors(&ds);

// Setup DHT22
DHT dht(DHT_PIN, DHTTYPE);

int led_value = LOW;


void setup() {
  Serial.begin(9600);
  Serial.flush();

  pinMode(LED_BUILTIN, OUTPUT);

  sensors.begin();

  pinMode(AC_PIN, INPUT);

  pinMode(COMP_RELAY, OUTPUT);
  pinMode(CAMERAS_RELAY, OUTPUT);
  pinMode(FAN_RELAY, OUTPUT);
  pinMode(WEATHER_RELAY, OUTPUT);
  pinMode(MOUNT_RELAY, OUTPUT);

  // Turn relays on to start
  digitalWrite(COMP_RELAY, HIGH);
  digitalWrite(CAMERAS_RELAY, HIGH);
  digitalWrite(FAN_RELAY, HIGH);
  digitalWrite(WEATHER_RELAY, HIGH);  
  digitalWrite(MOUNT_RELAY, HIGH);

  dht.begin();

}

void loop() {

  // Read any serial input
  //    - Input will be two comma separated integers, the
  //      first specifying the pin and the second the status
  //      to change to (1/0). Only the fan and the debug led
  //      are currently supported.
  //      Example serial input:
  //           4,1   # Turn fan on
  //          13,0   # Turn led off
  while (Serial.available() > 0) {
    int pin_num = Serial.parseInt();
    int pin_status = Serial.parseInt();

    switch (pin_num) {
      case 0: // All off
        turn_pin_off(COMP_RELAY);
        turn_pin_off(CAMERAS_RELAY);
        turn_pin_off(FAN_RELAY);
        turn_pin_off(WEATHER_RELAY);
        turn_pin_off(MOUNT_RELAY);
        break;
      case 1: // All on
        turn_pin_on(COMP_RELAY);
        turn_pin_on(CAMERAS_RELAY);
        turn_pin_on(FAN_RELAY);
        turn_pin_on(WEATHER_RELAY);
        turn_pin_on(MOUNT_RELAY);
        break;        
      case COMP_RELAY:
        /* The computer shutting itself off:
         *  - Power down
         *  - Wait 30 seconds
         *  - Power up
         */
        if (pin_status == 0){
          turn_pin_off(COMP_RELAY);
          delay(1000 * 30);
          turn_pin_on(COMP_RELAY);
        }
        break;
      case CAMERAS_RELAY:
      case FAN_RELAY:
      case WEATHER_RELAY:
      case MOUNT_RELAY:
        if (pin_status == 1) {
          turn_pin_on(pin_num);
        } else if (pin_status == 0) {
          turn_pin_off(pin_num);
        } else if (pin_status == 9) {
          toggle_pin(pin_num);
        }
        break;      
      case LED_BUILTIN:
        digitalWrite(pin_num, pin_status);
        break;
      }
  }

  Serial.print("{");

  read_voltages();

  read_dht_temp();

  read_ds18b20_temp();

  Serial.print("\"count\":"); Serial.print(millis());

  Serial.println("}");

  // Simple heartbeat
  //  toggle_led();
  delay(1000);
}

/* Toggle Pin */
void turn_pin_on(int camera_pin) {
  digitalWrite(camera_pin, HIGH);
}

void turn_pin_off(int camera_pin) {
  digitalWrite(camera_pin, LOW);
}

void toggle_pin(int pin_num) {
  digitalWrite(pin_num, !digitalRead(pin_num));
}

int is_pin_on(int camera_pin) {
  return digitalRead(camera_pin);
}

/* Read Voltages

Gets the AC probe as well as the values of the current on the AC I_ pins

https://www.arduino.cc/en/Reference/AnalogRead

 */
void read_voltages() {
  int ac_reading = digitalRead(AC_PIN);

  int main_reading = analogRead(I_MAIN);
  float main_voltage = (main_reading / 1023.) * 5.;
  float main_amps = ((main_voltage - ACS_offset) / mV_per_amp);

  int fan_reading = analogRead(I_FAN);
  float fan_voltage = (fan_reading / 1023.) * 5.;
  float fan_amps = ((fan_voltage - ACS_offset) / mV_per_amp);
  
  int mount_reading = analogRead(I_MOUNT);
  float mount_voltage = (mount_reading / 1023.) * 5.;
  float mount_amps = ((mount_voltage - ACS_offset) / mV_per_amp);
  
  int camera_reading = analogRead(I_CAMERAS);
  float camera_voltage = (camera_reading / 1023.) * 5.;
  float camera_amps = ((camera_voltage - ACS_offset) / mV_per_amp);

  Serial.print("\"power\":{");
  Serial.print("\"computer\":"); Serial.print(is_pin_on(COMP_RELAY)); Serial.print(',');
  Serial.print("\"fan\":"); Serial.print(is_pin_on(FAN_RELAY)); Serial.print(',');
  Serial.print("\"mount\":"); Serial.print(is_pin_on(MOUNT_RELAY)); Serial.print(',');
  Serial.print("\"cameras\":"); Serial.print(is_pin_on(CAMERAS_RELAY)); Serial.print(',');
  Serial.print("\"weather\":"); Serial.print(is_pin_on(WEATHER_RELAY)); Serial.print(',');  
  Serial.print("},");

  Serial.print("\"current\":{");
  Serial.print("\"main\":"); Serial.print(main_reading); Serial.print(',');
  Serial.print("\"fan\":"); Serial.print(fan_reading); Serial.print(',');
  Serial.print("\"mount\":"); Serial.print(mount_reading); Serial.print(',');
  Serial.print("\"cameras\":"); Serial.print(camera_reading);
  Serial.print("},");
  
//  Serial.print("\"volts\":{");
//  Serial.print("\"main\":"); Serial.print(main_voltage); Serial.print(',');
//  Serial.print("\"fan\":"); Serial.print(fan_voltage); Serial.print(',');
//  Serial.print("\"mount\":"); Serial.print(mount_voltage); Serial.print(',');
//  Serial.print("\"cameras\":"); Serial.print(camera_voltage);
//  Serial.print("},");
//
//  Serial.print("\"amps\":{");
//  Serial.print("\"main\":"); Serial.print(main_amps); Serial.print(',');
//  Serial.print("\"fan\":"); Serial.print(fan_amps); Serial.print(',');
//  Serial.print("\"mount\":"); Serial.print(mount_amps); Serial.print(',');
//  Serial.print("\"cameras\":"); Serial.print(camera_amps);
//  Serial.print("},");
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
  Serial.print("\"temp_00\":"); Serial.print(c); Serial.print(',');
}

void read_ds18b20_temp() {

  sensors.requestTemperatures();  

  Serial.print("\"temperature\":[");

  for (int x = 0; x < NUM_DS18; x++) {
    Serial.print(sensors.getTempCByIndex(x)); Serial.print(",");
  }
  Serial.print("],");
}


/************************************
* Utitlity Methods
*************************************/

void toggle_led() {
  led_value = ! led_value;
  digitalWrite(LED_BUILTIN, led_value);
}
