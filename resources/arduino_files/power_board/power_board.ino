#include <stdlib.h>

#include "OneWire.h"
#include "DallasTemperature.h"
#include "dht_handler.h"
#include "CharBuffer.h"
#include "PinUtils.h"

#define DHTTYPE DHT22   // DHT 22  (AM2302)

/* DECLARE PINS */

// Digital Pins
const int DS18_PIN = 11; // DS18B20 Temperature (OneWire)
const int DHT_PIN = 10;  // DHT Temp & Humidity Pin

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

// Accumulates a line, parses it and takes the requested action if it is valid.
class SerialInputHandler {
  public:
    void Handle() {
      while (Serial && Serial.available() > 0) {
        int c = Serial.read();
        if (wait_for_new_line_) {
          if (IsNewLine(c)) {
            wait_for_new_line_ = false;
            input_buffer_.Reset();
          }
        } else if (IsNewLine(c)) {
          ProcessInputBuffer();
          wait_for_new_line_ = false;
          input_buffer_.Reset();
        } else if (isprint(c)) {
          if (!input_buffer_.Append(static_cast<char>(c))) {
            wait_for_new_line_ = true;
          }
        } else {
          // Input is not an acceptable character.
          wait_for_new_line_ = true;
        }
      }
    }

  private:
    // Allow the input line to end with NL, CR NL or CR.
    bool IsNewLine(int c) {
      return c == '\n' || c == '\r';
    }

    void ProcessInputBuffer() {
      uint8_t relay_index, new_state;
      if (input_buffer_.ParseUInt8(&relay_index) &&
          input_buffer_.MatchAndConsume(',') &&
          input_buffer_.ParseUInt8(&new_state) &&
          input_buffer_.Empty()) {
            
        int pin_num = relayArray[relay_index];
        switch (new_state) {
          case 0:
            turn_pin_off(pin_num);
            break;    
          case 1:
            turn_pin_on(pin_num);
            break;
          case 9:
            toggle_pin(pin_num);
            break;
        }    
      }
    }

    CharBuffer<8> input_buffer_;
    bool wait_for_new_line_{false};
} serial_input_handler;

void loop() {

  // Read any serial input
  //    - Input will be two comma separated integers, the
  //      first specifying the relayArray index and the second 
  //      the new desired state.
  //      Example serial input:
  //           0,1   # Turn relay index 0 on (pin RELAY_0)
  //           0,2   # Turn relay index 0 off
  //           0,3   # Toggle relay index 0 
  //           0,4   # Toggle relay index 0 w/ 30 sec delay
  
  serial_input_handler.Handle();
  
  delay(250);

  get_readings();

  // Simple heartbeat
  toggle_led();
  delay(250);
}

void get_readings() {
  float voltages[5];
  float temps[4];
  float humidity[1];

  read_voltages(voltages);
  read_dht_temp(temps, humidity);
  read_ds18b20_temp(temps);

  Serial.print("{");

  Serial.print("\"currents\":[");
  Serial.print(voltages[0], 3); Serial.print(',');
  Serial.print(voltages[1], 3); Serial.print(',');
  Serial.print(voltages[2], 3); Serial.print(',');
  Serial.print(voltages[3], 3); Serial.print(',');
  Serial.print(voltages[4], 3);
  Serial.print("],");

  Serial.print("\"temps\":[");
  Serial.print(temps[0], 2); Serial.print(',');
  Serial.print(temps[1], 2); Serial.print(',');
  Serial.print(temps[2], 2); Serial.print(',');
  Serial.print(temps[3], 2);
  Serial.print("],");

  Serial.print(" \"humidity\":"); Serial.print(humidity[0]); Serial.print(',');

  Serial.print("\"name\":\"power_board\"");

  Serial.println("}");
}

/* Read Voltages

Gets the AC probe as well as the values of the current on the AC I_ pins

https://www.arduino.cc/en/Reference/AnalogRead

 */
void read_voltages(float voltages[]) {

  // Enable channels 0_0 and 1_0
  digitalWrite(DSEL_0, LOW);
  digitalWrite(DSEL_1, LOW);

  delay(500);  

  float Diag0=analogRead(IS_0);
  float Diag1=analogRead(IS_1);
  

  // Enabled channels 0_1 and 1_1
  digitalWrite(DSEL_0, HIGH);
  digitalWrite(DSEL_1, HIGH);

  delay(500);  
  
  float Diag3=analogRead(IS_0);
  float Diag4=analogRead(IS_1);
  
  float Diag2=analogRead(IS_2);
  
  float Iload0 = Diag0*5/1023*2360/1200; //conversion factor to compute Iload from sensed voltage
  float Iload1 = Diag1*5/1023*2360/1200;
  float Iload2 = Diag2*5/1023*2360/1200; 
  float Iload3 = Diag3*5/1023*2360/1200; 
  float Iload4 = Diag4*5/1023*2360/1200; 
  
  voltages[0] = Iload0;
  voltages[1] = Iload3;
  voltages[2] = Iload1;
  voltages[3] = Iload4;
  voltages[4] = Iload2;
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
