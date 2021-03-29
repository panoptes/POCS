#include <stdlib.h>
#include <ArduinoJson.h>

//conversion factor to compute Iload from sensed voltage. From Luc.
const float MULTIPLIER = 5 / 1023 * 2360 / 1200;

// Relays
const int RELAY_0 = A3; // 0_0 PROFET-0 Channel 0 (A3 = 17)
const int RELAY_1 = 3;  // 1_0 PROFET-0 Channel 1
const int RELAY_2 = 4;  // 0_1 PROFET-1 Channel 0
const int RELAY_3 = 7;  // 1_1 PROFET-1 Channel 1
const int RELAY_4 = 8;  // 0_2 PROFET-2 Channel 0

// Current Sense
const int IS_0 = A0; // (PROFET-0 A0 = 14)
const int IS_1 = A1; // (PROFET-1 A1 = 15)
const int IS_2 = A2; // (PROFET-2 A2 = 16)

// Channel select
const int DSEL_0 = 2; // PROFET-0
const int DSEL_1 = 6; // PROFET-1

// Enable Sensing
const int DEN_0 = A4; // PROFET-0 (A4 = 18)
const int DEN_1 = 5;  // PROFET-1
const int DEN_2 = 9;  // PROFET-2

const int relayArray[] = {RELAY_0, RELAY_1, RELAY_2, RELAY_3, RELAY_4};

int led_value = LOW;

void setup() {
  Serial.begin(9600);
  Serial.flush();

  pinMode(LED_BUILTIN, OUTPUT);

  // Setup sense pins
  pinMode(IS_0, INPUT);
  pinMode(IS_1, INPUT);
  pinMode(IS_2, INPUT);

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

  //ENABLE DIAGNOSIS AND SELECT CHANNEL
  digitalWrite(DEN_0, HIGH);  // DEN_0 goes HIGH so Diagnosis enabled for PROFET0
  digitalWrite(DEN_1, HIGH);  // DEN_1 goes HIGH so Diagnosis enabled for PROFET1
  digitalWrite(DEN_2, HIGH);  // DEN_2 goes HIGH so Diagnosis enabled for PROFET2

  digitalWrite(DSEL_0, LOW); // DSEL_0 LOW reads PROFET 0_0. DSEL_0 HIGH reads PROFET 0_1
  digitalWrite(DSEL_1, LOW); // DSEL_1 LOW reads PROFET 1_0. DSEL_1 HIGH reads PROFET 1_1

  // Turn on all relays to start
  turn_pin_on(RELAY_0);
  turn_pin_on(RELAY_1);
  turn_pin_on(RELAY_2);
  turn_pin_on(RELAY_3);
  turn_pin_on(RELAY_4);
}

void loop() {
  if (Serial.available() > 0) {
    handle_input();
  }
  delay(250);
  get_readings();

  // Simple heartbeat
  toggle_led();
  delay(250);
}

void handle_input() {
  StaticJsonDocument<28> doc;
  DeserializationError error = deserializeJson(doc, Serial);

  if (error) {
    //    Serial.print(F("deserializeJson() failed: "));
    //    Serial.println(error.f_str());
    return;
  }

  int relay_index = doc["relay"].as<int>();
  int pin_num = relayArray[relay_index];
  int power_on = doc["power"].as<int>();

  if (power_on == true) {
    turn_pin_on(pin_num);
  } else {
    turn_pin_off(pin_num);
  }
}

void get_readings() {
  int current_readings[5];
  read_currents(current_readings);

  StaticJsonDocument<128> doc;

  JsonArray relays = doc.createNestedArray("relays");
  relays.add(is_relay_on(RELAY_0));
  relays.add(is_relay_on(RELAY_1));
  relays.add(is_relay_on(RELAY_2));
  relays.add(is_relay_on(RELAY_3));
  relays.add(is_relay_on(RELAY_4));

  JsonArray currents = doc.createNestedArray("currents");
  currents.add(current_readings[0]);
  currents.add(current_readings[1]);
  currents.add(current_readings[2]);
  currents.add(current_readings[3]);
  currents.add(current_readings[4]);
  doc["name"] = "power_board";

  serializeJson(doc, Serial);
  Serial.println();
}

/* Read Current from the PROFETs */
void read_currents(int current_readings[]) {

  // Enable channels 0_0 and 1_0.
  digitalWrite(DSEL_0, LOW);
  digitalWrite(DSEL_1, LOW);
  delay(500);

  // Read from PROFETs.
  int Diag0_0 = analogRead(IS_0);
  int Diag1_0 = analogRead(IS_1);
  int Diag2_0 = analogRead(IS_2);

  // Enabled channels 0_1 and 1_1.
  digitalWrite(DSEL_0, HIGH);
  digitalWrite(DSEL_1, HIGH);
  delay(500);

  int Diag0_1 = analogRead(IS_0);
  int Diag1_1 = analogRead(IS_1);
  int Diag2_1 = analogRead(IS_2);

  current_readings[0] = Diag0_0;
  current_readings[1] = Diag0_1;
  current_readings[2] = Diag1_0;
  current_readings[3] = Diag1_1;
  // Average the PROFET that was read twice.
  current_readings[4] = int((Diag2_0 + Diag2_1) / 2);
}


/************************************
  Utility Methods
*************************************/

bool is_relay_on(int pin_num) {
  return digitalRead(pin_num) != LOW;
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

void toggle_pin_delay(int pin_num) {
  turn_pin_off(pin_num);
  delay(1000 * 30);
  turn_pin_on(pin_num);
}

void toggle_led() {
  toggle_pin(LED_BUILTIN);
}
