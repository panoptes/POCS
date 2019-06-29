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
#define VERSION_ID "\"2019-06-26\""

#define DHTTYPE DHT22   // DHT 22  (AM2302)

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

const int relayArray[] = {RELAY_0, RELAY_1, RELAY_2, RELAY_3, RELAY_4};

const int NUM_DS18 = 3; // Number of DS18B20 Sensors

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
  //      first specifying the pin and the second the status
  //      to change to (1/0). Cameras and debug led are
  //      supported.
  //      Example serial input:
  //           4,1   # Turn pin 4 on
  //          13,0   # Turn built-in led (pin 13) off
  while (Serial.available() > 0) {
    int pin_num = Serial.parseInt();
    int pin_status = Serial.parseInt();

    switch (pin_num) {
    case RELAY_1:
    case RELAY_2:
    case RELAY_3:
    case RELAY_4:
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

  delay(250);

  get_readings();

  // Simple heartbeat
  toggle_led();
  delay(250);
}

void get_readings() {
  float voltages[7];
  int power[6];
  float temps[4];
  float humidity[1];

  read_voltages(voltages);
  read_power(power);
  read_dht_temp(temps, humidity);
  read_ds18b20_temp(temps);

  // Is Mains power on? Check the AC sensor for any value above 0.
  if(voltages[6] > 0.0){
    power[5] = 1;
  } else {
    power[5] = 0;
  }

  // Create our JsonDocument
  // https://arduinojson.org/v6/assistant/
  const size_t capacity = JSON_ARRAY_SIZE(4) + 2*JSON_OBJECT_SIZE(1) + 2*JSON_OBJECT_SIZE(4) + JSON_OBJECT_SIZE(6) + JSON_OBJECT_SIZE(8);
  DynamicJsonDocument doc(capacity);

  JsonObject data = doc.createNestedObject("data");

  JsonObject data_control_board = data.createNestedObject("control_board");
  data_control_board["name"] = "control_board";
  data_control_board["ver"] = VERSION_ID;

  JsonObject data_control_board_power = data_control_board.createNestedObject("power");
  data_control_board_power["computer"] = power[0];
  data_control_board_power["fan"] = power[1];
  data_control_board_power["mount"] = power[2];
  data_control_board_power["cameras"] = power[3];
  data_control_board_power["weather"] = power[4];
  data_control_board_power["main"] = 1;

  JsonObject data_control_board_current = data_control_board.createNestedObject("current");
  data_control_board_current["main"] = voltages[0];
  data_control_board_current["fan"] = voltages[1];
  data_control_board_current["mount"] = voltages[2];
  data_control_board_current["cameras"] = voltages[3];

  JsonObject data_control_board_amps = data_control_board.createNestedObject("amps");
  data_control_board_amps["main"] = voltages[0];
  data_control_board_amps["fan"] = voltages[1];
  data_control_board_amps["mount"] = voltages[2];
  data_control_board_amps["cameras"] = voltages[3];

  data_control_board["humidity"] = humidity[0];

  JsonArray data_control_board_temperature = data_control_board.createNestedArray("temperature");
  data_control_board_temperature.add(temps[0]);
  data_control_board_temperature.add(temps[1]);
  data_control_board_temperature.add(temps[2]);
  data_control_board_temperature.add(temps[3]);

  serializeJson(doc, Serial);
}

/* Read Voltages

Gets the AC probe as well as the values of the current on the AC I_ pins

https://www.arduino.cc/en/Reference/AnalogRead

 */
void read_voltages(float voltages[]) {

  // Enable channels 0_0 and 1_0
  digitalWrite(DSEL_0, LOW);
  digitalWrite(DSEL_1, LOW);

  delay(100);

  float Diag0=analogRead(IS_0);
  float Diag1=analogRead(IS_1);


  // Enabled channels 0_1 and 1_1
  digitalWrite(DSEL_0, HIGH);
  digitalWrite(DSEL_1, HIGH);

  delay(100);

  float Diag3=analogRead(IS_0);
  float Diag4=analogRead(IS_1);

  float Diag2=analogRead(IS_2);
  float Diag5=analogRead(ISENSE);

  float Diag6=analogRead(ISENSEAC);

  float Diag7=analogRead(VPS);

  float Iload0 = Diag0*5/1023*2360/1200; //conversion factor to compute Iload from sensed voltage
  float Iload1 = Diag1*5/1023*2360/1200;
  float Iload2 = Diag2*5/1023*3200/1200;
  float Iload3 = Diag3*5/1023*2360/1200;
  float Iload4 = Diag4*5/1023*2360/1200;
  float Iload5 = Diag5*5/1023;
  float Iload6 = Diag6*5/1023*0.18; //shows in AC (A)
  float Iload7 = Diag7*5/1023*3.45; //takes into account the voltage divider bridge

  voltages[0] = Iload5;
  voltages[1] = Iload0;
  voltages[2] = Iload3;
  voltages[3] = Iload1;
  voltages[4] = Iload4;
  voltages[5] = Iload2;
  voltages[6] = Iload6;
  voltages[7] = Iload7;
}

void read_power(int power[]) {
  power[0] = digitalRead(RELAY_0);
  power[1] = digitalRead(RELAY_1);
  power[2] = digitalRead(RELAY_2);
  power[3] = digitalRead(RELAY_3);
  power[4] = digitalRead(RELAY_4);
}

// Reading temperature or humidity takes about 250 milliseconds!
// Sensor readings may also be up to 2 seconds 'old' (its a very slow sensor)
void read_dht_temp(float temps[], float humidity[]) {
  dht_handler.Collect();

  humidity[0] = dht_handler.humidity();
  temps[0] = dht_handler.temperature();
}

void read_ds18b20_temp(float temps[]) {

  sensors.requestTemperatures();

  for (int x = 0; x < NUM_DS18; x++) {
    // Store in x+1 because DHT11 stores in index 0
    temps[x+1] = sensors.getTempCByIndex(x);
  }
}


/************************************
* Utility Methods
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

void toggle_led() {
  toggle_pin(LED_BUILTIN);
}

