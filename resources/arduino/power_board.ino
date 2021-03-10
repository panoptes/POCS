#include <stdlib.h>
#include <ArduinoJson.h>

//conversion factor to compute Iload from sensed voltage. From Luc.
const float MULTIPLIER = 5/1023*2360/1200;

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

  digitalWrite(DSEL_0, LOW); // DSEL_0 LOW reads PROFET 0_0. DSEL_0 HIGH reades PROFET 0_1
  digitalWrite(DSEL_1, LOW); // DSEL_1 LOW reads PROFET 1_0. DSEL_1 HIGH reades PROFET 1_1

 // Turn on all relays to start
 turn_pin_on(RELAY_0);
 turn_pin_on(RELAY_1);
 turn_pin_on(RELAY_2);
 turn_pin_on(RELAY_3);
 turn_pin_on(RELAY_4);
}

// CharBuffer stores characters and supports (minimal) parsing of
// the buffered characters.
template <uint8_t kBufferSize>
class CharBuffer {
  public:
    CharBuffer() {
      Reset();
    }
    void Reset() {
      write_cursor_ = read_cursor_ = 0;
    }
    bool Append(char c) {
      if (write_cursor_ < buf_ + kBufferSize) {
        buf_[write_cursor_++] = c;
        return true;
      }
      return false;
    }
    bool Empty() {
      return read_cursor_ >= write_cursor_;
    }
    char Next() {
      return buf_[read_cursor_++];
    }
    char Peek() {
      return buf_[read_cursor_];
    }
    bool ParseInt(int* output) {
      int& v = *output;
      v = 0;
      size_t len = 0;
      while (!Empty() && isdigit(Peek())) {
        char c = Next();
        v = v * 10 + c - '0';
        ++len;
        if (len > 5) {
          return false;
        }
      }
      return len > 0;
    }
    bool MatchAndConsume(char c) {
      if (Empty() || Peek() != c) {
        return false;
      }
      Next();
      return true;
    }

  private:
    char buf_[kBufferSize];
    uint8_t write_cursor_;
    uint8_t read_cursor_;
};

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
      int relay_index, new_state;
      if (input_buffer_.ParseInt(&relay_index) &&
          input_buffer_.MatchAndConsume(',') &&
          input_buffer_.ParseInt(&new_state) &&
          input_buffer_.Empty()) {

        int pin_num = relayArray[relay_index];
        switch (new_state) {
          case 1:
            turn_pin_on(pin_num);
            break;
          case 2:
            turn_pin_off(pin_num);
            break;
          case 3:
            toggle_pin(pin_num);
            break;
          case 4:
            toggle_pin_delay(pin_num);
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

/* Read Current
Gets the AC probe as well as the values of the current on the AC I_ pins
https://www.arduino.cc/en/Reference/AnalogRead
*/
void read_currents(int current_readings[]) {

  // Enable channels 0_0 and 1_0
  digitalWrite(DSEL_0, LOW);
  digitalWrite(DSEL_1, LOW);

  delay(500);

  int Diag0=analogRead(IS_0);
  int Diag1=analogRead(IS_1);

  // Enabled channels 0_1 and 1_1
  digitalWrite(DSEL_0, HIGH);
  digitalWrite(DSEL_1, HIGH);

  delay(500);

  int Diag3=analogRead(IS_0);
  int Diag4=analogRead(IS_1);

  int Diag2=analogRead(IS_2);

  float Iload0 = Diag0 * MULTIPLIER;
  float Iload1 = Diag1 * MULTIPLIER;
  float Iload2 = Diag2 * MULTIPLIER;
  float Iload3 = Diag3 * MULTIPLIER;
  float Iload4 = Diag4 * MULTIPLIER;

  current_readings[0] = Diag0; //Iload0;
  current_readings[1] = Diag3; //Iload3;
  current_readings[2] = Diag1; //Iload1;
  current_readings[3] = Diag4; //Iload4;
  current_readings[4] = Diag2; //Iload2;
}


/************************************
* Utility Methods
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
