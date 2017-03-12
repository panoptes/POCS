#include <stdlib.h>
#include <OneWire.h>

#include <DHT.h>

#define DHTTYPE DHT22   // DHT 22  (AM2302)

/* DECLARE PINS */

// Analog Pins
const int I_MAIN = A1;
const int I_FAN = A2;
const int I_MOUNT = A3;
const int I_CAMERAS = A4;

// Digital Pins
const int AC_IN = 11;
const int DS18_IN = 10; // DS18B20 Temperature (OneWire)
const int DHT_IN = 9; // DHT Temp & Humidity Pin

const int COMP_RELAY = 8; // Computer Relay
const int CAMERAS_RELAY = 7; // Cameras Relay
const int FAN_RELAY = 6; // Fan Relay
const int WEATHER_RELAY = 5; // Weather Relay
const int MOUNT_RELAY = 4; // Mount Relay

const int NUM_DS18 = 3; // Number of DS18B20 Sensors


/* CONSTANTS */
/*
For info on the current sensing, see:
  http://henrysbench.capnfatz.com/henrys-bench/arduino-current-measurements/the-acs712-current-sensor-with-an-arduino/
  http://henrysbench.capnfatz.com/henrys-bench/arduino-current-measurements/acs712-current-sensor-user-manual/
*/
const int mV_per_amp = 185; 
const int ACS_offset = 2500; 


uint8_t sensors_address[NUM_DS18][8];

// Temperature chip I/O
OneWire sensor_bus(DS18_PIN);
float get_ds18b20_temp (uint8_t *address);

// Setup DHT22
DHT dht(DHT_PIN, DHTTYPE);

int led_value = LOW;


void setup() {
  Serial.begin(9600);
  Serial.flush();

  pinMode(LED_BUILTIN, OUTPUT);

  pinMode(DS18_PIN, OUTPUT);

  pinMode(COMP_RELAY, OUTPUT);
  pinMode(CAMERAS_RELAY, OUTPUT);
  pinMode(FAN_RELAY, OUTPUT);
  pinMode(WEATHER_RELAY, OUTPUT);
  pinMode(MOUNT_RELAY, OUTPUT);

  dht.begin();

  // Search for attached DS18B20 sensors
  int x, c = 0;
  for (x = 0; x < NUM_DS18; x++) {
    if (sensor_bus.search(sensors_address[x]))
      c++;
  }
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
      case COMP_RELAY:
      case CAMERAS_RELAY:
      case FAN_RELAY:
      case WEATHER_RELAY:
      case MOUNT_RELAY:
        if (pin_status == 1) {
          turn_pin_on(pin_num);
        } else {
          turn_pin_off(pin_num);
        }
        break;      
      case FAN_PIN:
      case LED_BUILTIN:
        digitalWrite(pin_num, pin_status);
        break;
      }
  }

  Serial.print("{");

  read_voltages(); Serial.print(",");

  read_dht_temp(); Serial.print(",");

  read_ds18b20_temp(); Serial.print(",");

  Serial.print("\"count\":"); Serial.print(millis());

  Serial.println("}");

  // Simple heartbeat
  toggle_led();
  delay(1000);
}

/* Toggle Pin */
void turn_pin_on(int camera_pin) {
  digitalWrite(camera_pin, HIGH);
}

void turn_pin_off(int camera_pin) {
  digitalWrite(camera_pin, LOW);
}


/* Read Voltages

Gets the AC probe as well as the values of the current on the AC I_ pins

https://www.arduino.cc/en/Reference/AnalogRead

 */
void read_voltages() {
  int ac_reading = analogRead(AC_IN);
  float ac_voltage = (ac_reading / 1023.) * 5000;
  ac_amps = ((ac_voltage - ACS_offset) / mV_per_amp);

  int main_reading = analogRead(I_MAIN);
  float main_voltage = (main_reading / 1023.) * 5000;
  main_amps = ((main_voltage - ACS_offset) / mV_per_amp);

  int fan_reading = analogRead(I_FAN);
  float fan_voltage = (fan_reading / 1023.) * 5000;
  fan_amps = ((fan_voltage - ACS_offset) / mV_per_amp);
  
  int mount_reading = analogRead(I_MOUNT);
  float mount_voltage = (mount_reading / 1023.) * 5000;
  mount_amps = ((mount_voltage - ACS_offset) / mV_per_amp);
  
  int camera_reading = analogRead(I_CAMERAS);
  float camera_voltage = (camera_reading / 1023.) * 5000;
  camera_amps = ((camera_voltage - ACS_offset) / mV_per_amp);

  Serial.print("\"voltages\":{");
  Serial.print("\"ac\":"); Serial.print(ac_voltage); Serial.print(',');
  Serial.print("\"main\":"); Serial.print(main_amps); Serial.print(',');
  Serial.print("\"fan\":"); Serial.print(fan_amps); Serial.print(',');
  Serial.print("\"mount\":"); Serial.print(mount_amps); Serial.print(',');
  Serial.print("\"cameras\":"); Serial.print(cameras_amps);
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
  Serial.print("\"temp_00\":"); Serial.print(c);
}

void read_ds18b20_temp() {

  for (int x = 0; x < NUM_DS18; x++) {
    Serial.print("\"temp_0");
    Serial.print(x + 1);
    Serial.print("\":");
    Serial.print(get_ds18b20_temp(sensors_address[x]));

    // Append a comma to all but last
    if (x < NUM_DS18 - 1) {
      Serial.print(",");
    }
  }
}

float get_ds18b20_temp(uint8_t *addr) {
  byte data[12];

  sensor_bus.reset();
  sensor_bus.select(addr);
  sensor_bus.write(0x44, 1); // start conversion, with parasite power on at the end

  byte present = sensor_bus.reset();
  sensor_bus.select(addr);
  sensor_bus.write(0xBE); // Read Scratchpad

  for (int i = 0; i < 9; i++) { // we need 9 bytes
    data[i] = sensor_bus.read();
  }

  sensor_bus.reset_search();

  byte MSB = data[1];
  byte LSB = data[0];

  float tempRead = ((MSB << 8) | LSB); //using two's compliment
  float TemperatureSum = tempRead / 16;

  return TemperatureSum;
}

/************************************
* Utitlity Methods
*************************************/

void toggle_led() {
  led_value = ! led_value;
  digitalWrite(LED_BUILTIN, led_value);
}