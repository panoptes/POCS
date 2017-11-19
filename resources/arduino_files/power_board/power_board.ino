#include <stdlib.h>

#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>

#define DHTTYPE DHT22   // DHT 22  (AM2302)

/* DECLARE PINS */

// Current Sense
const int IS_0 = A0; // PROFET-0
const int IS_1 = A1; // PROFET-1
const int IS_2 = A2; // PROFET-2

// Channel select
const int DSEL_0 = 2; // PROFET-0
const int DSEL_1 = 6; // PROFET-1

const inst DEN_0 = A4; // PROFET-0
const inst DEN_1 = 5;  // PROFET-1
const inst DEN_2 = 9;  // PROFET-2

// Digital Pins
const int DS18_PIN = 10; // DS18B20 Temperature (OneWire)
const int DHT_PIN = 11;  // DHT Temp & Humidity Pin

// Relays
const int RELAY_1 = A3; // 0_0 PROFET-0 Channel 0
const int RELAY_2 = 3;  // 1_0 PROFET-0 Channel 1
const int RELAY_3 = 4;  // 0_1 PROFET-1 Channel 0
const int RELAY_4 = 7;  // 1_1 PROFET-1 Channel 1
const int RELAY_5 = 8;  // 0_2 PROFET-2 Channel 0

const int relayArray[] = {RELAY_1, RELAY_2, RELAY_3, RELAY_4, RELAY_5};
const int numRelay = 5;

const int NUM_DS18 = 3; // Number of DS18B20 Sensors

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

  // Turn relays on to start
  for (int i = 0; i < numRelay; i++) {
    pinMode(relayArray[i], OUTPUT);
    digitalWrite(relayArray[i], HIGH);
    delay(250);
  }

  dht.begin();
}

void loop() {

  // Read any serial input
  //    - Input will be two comma separated integers, the
  //      first specifying the pin and the second the status
  //      to change to (1/0). Only the fan and the debug led
  //      are currently supported.
  //      Example serial input:
  //           4,1   # Turn relay 4 on
  //           4,2   # Toggle relay 4
  //           4,3   # Toggle relay 4 w/ 30 sec delay
  //           4,9   # Turn relay 4 off
  while (Serial.available() > 0) {
    int pin_num = Serial.parseInt();
    int pin_status = Serial.parseInt();

    switch (pin_status) {
      case 1:
        turn_pin_on(pin_num);
        break;
      case 2:
        toggle_pin(pin_num);
        break;    
      case 3:
        toggle_pin_delay(pin_num);    
      case 9:
        turn_pin_off(pin_num);
        break;
    }
  }

  get_readings();

  // Simple heartbeat
  toggle_led();
  delay(500);
}

void get_readings() {
  Serial.print("{");

  read_voltages();

  read_dht_temp();

  read_ds18b20_temp();

  Serial.print("\"name\":\"telemetry_board\""); Serial.print(",");

  Serial.print("\"count\":"); Serial.print(millis());

  Serial.println("}");
}

/* Read Voltages

Gets the AC probe as well as the values of the current on the AC I_ pins

https://www.arduino.cc/en/Reference/AnalogRead

 */
void read_voltages() {
  int ac_reading = digitalRead(AC_PIN);

  int main_reading = analogRead(I_MAIN);
  float main_amps = (main_reading / 1023.) * main_amps_mult;  
//  float main_amps = ((main_voltage - ACS_offset) / mV_per_amp);

  int fan_reading = analogRead(I_FAN);
  float fan_amps = (fan_reading / 1023.) * fan_amps_mult;
//  float fan_amps = ((fan_voltage - ACS_offset) / mV_per_amp);
  
  int mount_reading = analogRead(I_MOUNT);
  float mount_amps = (mount_reading / 1023.) * mount_amps_mult;
//  float mount_amps = ((mount_voltage - ACS_offset) / mV_per_amp);
  
  int camera_reading = analogRead(I_CAMERAS);
  float camera_amps = (camera_reading / 1023.) * 1;
//  float camera_amps = ((camera_voltage - ACS_offset) / mV_per_amp);

  Serial.print("\"power\":{");
  Serial.print("\"computer\":"); Serial.print(is_pin_on(COMP_RELAY)); Serial.print(',');
  Serial.print("\"fan\":"); Serial.print(is_pin_on(FAN_RELAY)); Serial.print(',');
  Serial.print("\"mount\":"); Serial.print(is_pin_on(MOUNT_RELAY)); Serial.print(',');
  Serial.print("\"cameras\":"); Serial.print(is_pin_on(CAMERAS_RELAY)); Serial.print(',');
  Serial.print("\"weather\":"); Serial.print(is_pin_on(WEATHER_RELAY)); Serial.print(',');  
  Serial.print("\"main\":"); Serial.print(ac_reading); Serial.print(',');  
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

  Serial.print("\"amps\":{");
  Serial.print("\"main\":"); Serial.print(main_amps); Serial.print(',');
  Serial.print("\"fan\":"); Serial.print(fan_amps); Serial.print(',');
  Serial.print("\"mount\":"); Serial.print(mount_amps); Serial.print(',');
  Serial.print("\"cameras\":"); Serial.print(camera_amps);
  Serial.print("},");
}

// Reading temperature or humidity takes about 250 milliseconds!
// Sensor readings may also be up to 2 seconds 'old' (its a very slow sensor)
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

int is_pin_on(int pin_num) {
  return digitalRead(pin_num);
}

void turn_pin_on(int pin_num) {
  digitalWrite(pin_num, HIGH);
}

void turn_pin_off(int pin_num) {
  digitalWrite(pin_num, LOW);
}

void toggle_pin(int pin_num) {
  digitalWrite(pin_num, !digitalRead(pin_num));
}

void toggle_pin_delay(int pin_num, int delay = 30) {
  turn_pin_off(pin_num);
  delay(1000 * delay);
  turn_pin_on(pin_num);
}

void toggle_led() {
  toggle_pin(LED_BUILTIN);
}
