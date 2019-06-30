/* UPDATED CONTROL BOARD SCRIPT FOR 2019V ELECTRONICS */

#include <stdlib.h>

#include "OneWire.h"
#include "DallasTemperature.h"
#include "dht_handler.h"
#include "CharBuffer.h"

#include <ArduinoJson.h>

// Please update the version identifier when you
// make changes to this code. The value needs to
// be in JSON format (i.e. quoted and escaped if
// a string).
#define BOARD_NAME "\"control_board\""
#define VERSION_ID "\"2019-06-26\""

#define DHTTYPE DHT22   // DHT 22  (AM2302)

/* Hardware Index

 There are five relays from the Infineon board and the
 numbers below should correspond to the zero-based index
 number of the item plugged into each relay. The numbering
 starts from the bottom of the board, *furthest* from the
 V_in and GND pins. The relay next to the GND pin is therefore
 relay index 4.

*/
#define int COMPUTER_INDEX = 0;
#define int MOUNT_INDEX = 1;
#define int CAMERA_BOX_INDEX = 2;
#define int WEATHER_INDEX = 3;
#define int FAN_INDEX = 4;

#define UNO 1 // 1 if board is Uno, 0 if it is a Micro

/* DECLARE PINS */
#ifdef UNO
  // Digital Pins
  const int DS18_PIN = 13; // DS18B20 Temperature (OneWire)
  const int DHT_PIN = 12;  // DHT Temp & Humidity Pin

  // Relays
  const int RELAY_0 = 11; // 0_0 PROFET-0 Channel 0 (A3 = 17)
  const int RELAY_1 = 3;  // 1_0 PROFET-0 Channel 1
  const int RELAY_2 = 4;  // 0_1 PROFET-1 Channel 0
  const int RELAY_3 = 7;  // 1_1 PROFET-1 Channel 1
  const int RELAY_4 = 8;  // 0_2 PROFET-2 Channel 0

  // Current Sense
  const int IS_0 = A0; // (PROFET-0 A0 = 14)
  const int IS_1 = A1; // (PROFET-1 A1 = 15)
  const int IS_2 = A2; // (PROFET-2 A2 = 16)
  const int ISENSE = A5; // INA169 DC Current Sensor
  const int ISENSEAC = A3; // AC Current Sensor
  const int VPS = A6; // V_DC_SENSE circuit to check power supply / battery voltage

  // Channel select
  const int DSEL_0 = 2; // PROFET-0
  const int DSEL_1 = 6; // PROFET-1

  // Enable Sensing
  const int DEN_0 = A4; // PROFET-0 (A4 = 18)
  const int DEN_1 = 5;  // PROFET-1
  const int DEN_2 = 9;  // PROFET-2
#else // MICRO
  // Digital Pins
  const int DS18_PIN = 13; // DS18B20 Temperature (OneWire)
  const int DHT_PIN = 7;  // DHT Temp & Humidity Pin

  // Relays
  const int RELAY_0 = A3; // 0_0 PROFET-0 Channel 0
  const int RELAY_1 = 5;  // 1_0 PROFET-0 Channel 1
  const int RELAY_2 = 6;  // 0_1 PROFET-1 Channel 0
  const int RELAY_3 = 9;  // 1_1 PROFET-1 Channel 1
  const int RELAY_4 = 11;  // 0_2 PROFET-2 Channel 0

  // Current Sense
  const int IS_0 = A2; // (PROFET-0 A0 = 14)
  const int IS_1 = A1; // (PROFET-1 A1 = 15)
  const int IS_2 = A0; // (PROFET-2 A2 = 16)
  const int ISENSE = A10; // INA169 DC Current Sensor
  const int ISENSEAC = A5; // AC Current Sensor
  const int VPS = A6; // V_DC_SENSE circuit to check power supply / battery voltage

  // Channel select
  const int DSEL_0 = 2; // PROFET-0
  const int DSEL_1 = 16; // PROFET-1

  // Enable Sensing
  const int DEN_0 = 12; // PROFET-0 (A4 = 18)
  const int DEN_1 = 5;  // PROFET-1
  const int DEN_2 = 9;  // PROFET-2
#endif

const int NUM_DS18 = 3; // Number of DS18B20 Sensors

// Relay index. Used to look up appropriate relay for given hardware index.
const int numRelays = 5;
const int relayArray[] = {RELAY_0, RELAY_1, RELAY_2, RELAY_3, RELAY_4};

uint8_t sensors_address[NUM_DS18][8];

// Temperature chip I/O
OneWire ds(DS18_PIN);
DallasTemperature sensors(&ds);

// Setup DHT22
DHTHandler dht_handler(DHT_PIN, DHTTYPE);

int led_value = LOW;

void setup() {
  Serial.begin(9600);
  Serial.flush();

  pinMode(LED_BUILTIN, OUTPUT);

  sensors.begin();

  // Setup sense pins
  pinMode(IS_0, INPUT);
  pinMode(IS_1, INPUT);
  pinMode(IS_2, INPUT);
  pinMode(ISENSE, INPUT);
  pinMode(ISENSEAC, INPUT);
  pinMode(VPS, INPUT);

  analogReference(EXTERNAL);

  // Setup diagnosis enable pins
  pinMode(DEN_0, OUTPUT);
  pinMode(DEN_1, OUTPUT);
  pinMode(DEN_2, OUTPUT);

  // Setup relay pins
  pinMode(RELAY_0, OUTPUT);
  pinMode(RELAY_1, OUTPUT);
  pinMode(RELAY_2, OUTPUT);
  pinMode(RELAY_3, OUTPUT);
  pinMode(RELAY_4, OUTPUT);

  // Turn on everything to start
  // Setup relay pins
  digitalWrite(RELAY_0, HIGH);
  digitalWrite(RELAY_1, HIGH);
  digitalWrite(RELAY_2, HIGH);
  digitalWrite(RELAY_3, HIGH);
  digitalWrite(RELAY_4, HIGH);

  dht_handler.Init();

  //ENABLE DIAGNOSIS AND SELECT CHANNEL
  digitalWrite(DEN_0, HIGH);  // DEN_0 goes HIGH so Diagnosis enabled for PROFET0
  digitalWrite(DEN_1, HIGH);  // DEN_1 goes HIGH so Diagnosis enabled for PROFET1
  digitalWrite(DEN_2, HIGH);  // DEN_2 goes HIGH so Diagnosis enabled for PROFET2

  digitalWrite(DSEL_0, LOW); // DSEL_0 LOW reads PROFET 0_0. DSEL_0 HIGH reades PROFET 0_1
  digitalWrite(DSEL_1, LOW); // DSEL_1 LOW reads PROFET 1_0. DSEL_1 HIGH reades PROFET 1_1
}

void loop() {

  // Read any serial input
  //    - Input will be two comma separated integers, the
  //      first specifying the relay index and the second the status
  //      to change to (1/0). Cameras and debug LED are supported.
  //      Example serial input:
  //           4,1   # Turn relay 4 on
  //          13,0   # Turn built-in led (pin 13) off
  while (Serial.available() > 0) {
    int relay_number = Serial.parseInt();
    int relay_action = Serial.parseInt();

    // Don't allow toggle of computer
    if(relay_number != COMPUTER_INDEX){
      // Lookup the actual pin number to use.
      int pin_num = relayArray[relay_number]

      if (pin_status == 1) {
        turn_pin_on(pin_num);
      } else if (pin_status == 0) {
        turn_pin_off(pin_num);
      } else if (pin_status == 9) {
        toggle_pin(pin_num);
      }
    } elif(relay_number == LED_BUILTIN){
      toggle_pin(LED_BUILTIN)
    }
  }

  delay(250);

  // Do the actual work of reading all the sensors.
  get_readings();

  // Simple LED heartbeat.
  toggle_led();
  delay(250);
}

/************************************
* Sensor Functions
*************************************/


void get_readings() {
  float voltages[7];
  int power_readings[6];
  float temps[4];
  float humidity[1];

  read_voltages(voltages);
  read_power(power_readings);
  read_dht_temp(temps, humidity);
  read_ds18b20_temp(temps);

  // Is Mains power on? Check the AC sensor for any value above 0.
  if(voltages[6] > 0.0){
    power_readings[5] = 1;
  } else {
    power_readings[5] = 0;
  }

  // Create our JsonDocument
  // https://arduinojson.org/v6/assistant/
  const size_t capacity = JSON_ARRAY_SIZE(0) + 2*JSON_ARRAY_SIZE(1) +
                          JSON_ARRAY_SIZE(2) + JSON_ARRAY_SIZE(3) +
                          2*JSON_OBJECT_SIZE(3) + 3*JSON_OBJECT_SIZE(6);
  DynamicJsonDocument doc(capacity);

  doc["name"] = BOARD_NAME;
  doc["version"] = VERSION_ID;
  doc["time"] = millis();

  // Add the currents to the document.
  JsonObject current = doc.createNestedObject("current");
  current["computer"] = voltages[COMPUTER_INDEX];
  current["mount"] = voltages[MOUNT_INDEX];
  current["camera_box"] = voltages[CAMERA_BOX_INDEX];
  current["weater"] = voltages[WEATHER_INDEX];
  current["fan"] = voltages[FAN_INDEX];
  current["ac"] = voltages[7];
  current["dc"] = voltages[5];

  // Add the power readings (on/off) to the document.
  onObject power = doc.createNestedObject("power");
  power["computer"] = power_readings[COMPUTER_INDEX];
  power["mount"] = power_readings[MOUNT_INDEX];
  power["camera_box"] = power_readings[CAMERA_BOX_INDEX];
  power["weather"] = power_readings[WEATHER_INDEX];
  power["fan"] = power_readings[FAN_INDEX];
  power["main"] = power_readings[5];

  // Add the environment sensors to the document.
  JsonArray sensors = doc.createNestedArray("sensors");
  JsonObject sensors_0 = sensors.createNestedObject();
  sensors_0["name"] = "DHT";
  JsonArray sensors_0_humidity = sensors_0.createNestedArray("humidity");
  sensors_0_humidity.add(humidity[0]);
  JsonArray sensors_0_temperature = sensors_0.createNestedArray("temperature");
  sensors_0_temperature.add(temps[0]);

  JsonObject sensors_1 = sensors.createNestedObject();
  sensors_1["name"] = "DS18B20";
  JsonArray sensors_1_humidity = sensors_1.createNestedArray("humidity");

  JsonArray sensors_1_temperature = sensors_1.createNestedArray("temperature");
  for (int x = 0; x < NUM_DS18; x++) {
    // Store in x+1 because DHT11 stores in index 0
    sensors_1_temperature.add(temps[x+1]);
  }

  serializeJson(doc, Serial);
}


// Reading temperature or humidity takes about 250 milliseconds!
// Sensor readings may also be up to 2 seconds 'old' (it's a very slow sensor)
void read_dht_temp(float temps[], float humidity[]) {
  dht_handler.Collect();

  humidity[0] = dht_handler.humidity();
  temps[0] = dht_handler.temperature();
}

/* Read DS18B20 Sensors

Loop through the number of connected sensors and gather temperature.

*/
void read_ds18b20_temp(float temps[]) {

  sensors.requestTemperatures();

  for (int x = 0; x < NUM_DS18; x++) {
    // Store in x+1 because DHT11 stores in index 0
    temps[x+1] = sensors.getTempCByIndex(x);
  }
}

/* Read Voltages

Gets the AC probe as well as the values of the current on the AC I_ pins

https://www.arduino.cc/en/Reference/AnalogRead

 */
void read_voltages(float voltages[]) {

  float analogToFiveVolts = 5/1023;

  // conversion factor to compute Iload from sensed voltage.
  // The two types of mosfets on the Infineion have different values.
  // (wtgee) Empirical?
  float convertLoad0 = analogToFiveVolts*2360/1200;
  float convertLoad1 = analogToFiveVolts*3200/1200;

  // Enable channels 0_0 and 1_0 and get readings. Index 0 and 1.
  digitalWrite(DSEL_0, LOW);
  digitalWrite(DSEL_1, LOW);
  delay(100);
  float Diag0=analogRead(IS_0);
  float Diag1=analogRead(IS_1);
  float Iload0 = Diag0*convertLoad0;
  float Iload1 = Diag1*convertLoad0;

  // Enabled channels 0_1 and 1_1 and get readings. Index 2 and 3.
  digitalWrite(DSEL_0, HIGH);
  digitalWrite(DSEL_1, HIGH);
  delay(100);
  float Diag2=analogRead(IS_0);
  float Diag3=analogRead(IS_1);
  float Iload2 = Diag2*convertLoad0;
  float Iload3 = Diag3*convertLoad0;

  // Get readings for top channel. Index 4.
  float Diag4=analogRead(IS_2);
  float Iload4 = Diag4*convertLoad1;

  // DC sensor.
  float Diag5=analogRead(ISENSE);
  float Iload5 = Diag5*analogToFiveVolts;

  // AC sensor.
  float Diag6=analogRead(ISENSEAC);
  float Diag7=analogRead(VPS);
  float Iload6 = Diag6*analogToFiveVolts*0.18; //shows in AC (A)
  float Iload7 = Diag7*analogToFiveVolts*3.45; //takes into account the voltage divider bridge

  // Channel sensing.
  voltages[0] = Iload0;
  voltages[1] = Iload1;
  voltages[2] = Iload2;
  voltages[3] = Iload3;
  voltages[4] = Iload4;

  // AC and DC sensing.
  voltages[5] = Iload5; // DC
  voltages[6] = Iload6; // AC
  voltages[7] = Iload7; // AC w/ voltage divider
}

/* Hardware Index

 Read Power (i.e. is it on or off?)
ply read the current state of the pin .
/o read_power(int power_readings[]) {
  */
  power_readings[COMPUTER_INDEX] = digitalRead(relayArray[COMPUTER_INDEX]);
  power_readings[MOUNT_INDEX = digitalRead(relayArray[MOUNT_INDEX])

  power_readings[CAMERA_BOX_INDEX = digitalRead(relayArray[CAMERA_BOX_INDEX])
  power_readings[WEATHER_INDEX = digitalRead(relayArray[WEATHER_INDEX])
  power_readings[FAN_INDEX = digitalRead(relayArray[FAN_INDEX])
}

/************************************
* Utility Functions
*************************************/

void toggle_pin_delay(int pin_num) {
  turn_pin_off(pin_num);
  delay(1000 * 30);
  turn_pin_on(pin_num);
}

void turn_pin_on(int pin_num) {
  digitalWrite(pin_num, HIGH);
}

void turn_pin_off(int pin_num) {
  digitalWrite(pin_num, LOW);
}

bool is_pin_on(int pin_num) {
  return digitalRead(pin_num) != LOW;
}

void toggle_pin(int pin_num) {
  digitalWrite(pin_num, !digitalRead(pin_num));
}
