/*
   The PANOPTES Baseline Unit (January 2017) telemetry board controls 5 relays on
   the V0 power board, and reads 4 current sensors, 3 temperature sensors and one
   combined humidity & temperature sensor. Each pass through loop() it checks for
   serial input regarding switching the relays, and every 2 seconds it prints
   out the values of the sensors and the settings of the relays.

   This program has a class for each type of sensor, with a common API:
   1) An Init() method that is called from setup.
   2) A Collect() method that is called during the sensor reading phase.
   3) A Report() method that is called to print out json data.

   The serial input should be in this format:
      A,B<newline>
   Where A and B are two positive integers. The <newline> can be an ASCII
   new line or carriage return.
   The first integer (A) specifies the digital output pin that controls the relay,
   and the second (B) specifies the output value for that pin (0 or 1).
   See "Digital output pins" below for a list of the relay pins.
   If any other characters appear in the serial input, all serial input is ignored
   until a new line or carriage return is received.
*/

#include <ctype.h>
#include <stdlib.h>

#include "OneWire.h"
#include "DallasTemperature.h"
#include "DHT.h"

////////////////////////////////////////////////
// __      __               _                 //
// \ \    / /              (_)                //
//  \ \  / /___  _ __  ___  _   ___   _ __    //
//   \ \/ // _ \| '__|/ __|| | / _ \ | '_ \   //
//    \  /|  __/| |   \__ \| || (_) || | | |  //
//     \/  \___||_|   |___/|_| \___/ |_| |_|  //
//                                            //
////////////////////////////////////////////////

// Please update the version identifier when you
// make changes to this code. The value needs to
// be in JSON format (i.e. quoted and escaped if
// a string).
#define JSON_VERSION_ID "\"2017-09-02\""

// How often, in milliseconds, to emit a report.
#define REPORT_INTERVAL_MS 2000

// Type of Digital Humidity and Temperature (DHT) Sensor
#define DHTTYPE DHT22   // DHT 22  (AM2302)

// Analog input pins to which the current sensors are attached.
const int I_MAIN = A1;     // 12V input to power board.
const int I_FAN = A2;      // Output to fan (at most a few hundred mA)
const int I_MOUNT = A3;    // Output to mount (up to ~1A)
const int I_CAMERAS = A4;  // Output to cameras (up to ~1.2A)

// Scaling factors for the current sensor values. Given the use
// of the Sparkfun current sensor, which has a potentiometer on
// it, these need to be modified for each individual board. Switching
// to a fixed scale sensor, such as on the Infineon board, will
// remove this need. Another choice would be to output the raw analog
// values, and leave it up to a later system to scale or normalize
// the values.
const float main_amps_mult = 2.8;
const float fan_amps_mult = 1.8;
const float mount_amps_mult = 1.8;
const float cameras_amps_mult = 1.0;

// Digital input pins
const int AC_PIN = 11;    // Is there any AC input?
const int DS18_PIN = 10;  // DS18B20 Temperature (OneWire)
const int DHT_PIN = 9;    // DHT Temp & Humidity Pin

// Digital output pins
const int COMP_RELAY = 8;    // Computer Relay: change with caution; it runs the show.
const int CAMERAS_RELAY = 7; // Cameras Relay Off: 70s Both On: 800s One On: 350
const int FAN_RELAY = 6;     // Fan Relay  Off: 0 On: 80s
const int WEATHER_RELAY = 5; // Weather Relay 250mA upon init and 250mA to read
const int MOUNT_RELAY = 4;   // Mount Relay

OneWire ds(DS18_PIN);

// Utitlity Methods

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

//////////////////////////////////////////////////////////////////////////////
// Input Handlers: the support collecting the values of various sensors/pins,
// and then reporting it later.

class DHTHandler {
  public:
    DHTHandler(uint8_t pin, uint8_t type) : dht_(pin, type) {}

    void Init() {
      dht_.begin();
    }

    void Collect() {
      // Force readHumidity to actually talk to the device;
      // otherwise will read at most every 2 seconds, which
      // is sometimes just a little too far apart.
      // Note that the underlying read() routine has some big
      // delays (250ms and 40ms, plus some microsecond scale delays).
      humidity_ = dht_.readHumidity(/*force=*/true);
      // readTemperature will use the data collected by
      // readHumidity, which is just fine.
      temperature_ = dht_.readTemperature();
    }

    void Report() {
      // This is being added to a JSON dictionary, so print a comma
      // before the quoted name, which is then followed by a colon.
      Serial.print(", \"humidity\":");
      Serial.print(humidity_);
      Serial.print(", \"temp_00\":");
      Serial.print(temperature_);
    }

  private:
    DHT dht_;
    float humidity_;
    float temperature_;  // Celcius
} dht_handler(DHT_PIN, DHTTYPE);

// DallasTemperatureHandler collects temp values from Dallas One-Wire temp sensors.
template <size_t kMaxSensors>
class DallasTemperatureHandler {
  public:
    DallasTemperatureHandler(OneWire* one_wire) : dt_(one_wire), device_count_(0) {}

    void Init() {
      dt_.begin();
      dt_.setWaitForConversion(true);

      uint8_t devices = dt_.getDeviceCount();
      for (uint8_t device_num = 0; device_num < devices; ++device_num) {
        if (dt_.getAddress(devices_[device_count_].address, device_num)) {
          devices_[device_count_].index = device_num;
          ++device_count_;
          if (device_count_ >= kMaxSensors) {
            break;
          }
        }
      }
      // Sort the devices so we get a consistent order from run to run...
      // ... assuming the devices haven't been swapped, in which case we
      // need to redetermine their addresses.
      // Arduino libraries don't include sort(), so adapted insertion sort
      // code in the ArduinoSort library on github for just this purpose.
      for (uint8_t i = 1; i < device_count_; i++) {
        for (uint8_t j = i; j > 0 && devices_[j - 1] > devices_[j]; j--) {
          DeviceInfo tmp = devices_[j - 1];
          devices_[j - 1] = devices_[j];
          devices_[j] = tmp;
        }
      }
    }
    void Collect() {
      // Ask all of the sensors to start a temperature "conversion"; I think
      // this means the analog-to-digital conversion, which stores the result
      // in a register in the sensor. requestTemperatures() will return when
      // the conversion is complete.
      dt_.requestTemperatures();
      for (uint8_t i = 0; i < device_count_; i++) {
        DeviceInfo& device = devices_[i];
        device.temperature = dt_.getTempC(device.address);
      }
    }
    void Report() {
      if (device_count_ > 0) {
        // This is being added to a JSON dictionary, so print a comma
        // before the quoted name, which is then followed by a colon.
        Serial.print(", \"temperature\":[");
        for (uint8_t i = 0; i < device_count_; i++) {
          if (i != 0) {
            Serial.print(",");
          }
          DeviceInfo& device = devices_[i];
          Serial.print(device.temperature);
        }
        Serial.print("]");
      }
    }

    void PrintDeviceInfo() {
      for (uint8_t i = 0; i < device_count_; i++) {
        const DeviceInfo& device = devices_[i];
        const DeviceAddress& addr = device.address;
        Serial.print("Device #");
        Serial.print(device.index);
        Serial.print("   address: ");
        for (int j = 0; j < sizeof device.address; ++j) {
          Serial.print(static_cast<int>(device.address[j]), HEX);
          Serial.print(" ");
        }
        uint8_t resolution = dt_.getResolution(device.address);
        Serial.print("   resolution (bits): ");
        Serial.println(resolution);
      }
    }

  private:
    struct DeviceInfo {
      bool operator>(const DeviceInfo& rhs) const {
        return memcmp(address, rhs.address, sizeof address) < 0;
      }
      DeviceAddress address;
      float temperature;
      uint8_t index;
    };

    DallasTemperature dt_;
    DeviceInfo devices_[kMaxSensors];
    uint8_t device_count_;
};

// There are 3 DS18B20 sensors in the Jan 2017 Telemetry Board design.
DallasTemperatureHandler<3> dt_handler(&ds);

// Base class of handlers below which emit a different name for each
// instance of a sub-class.
class BaseNameHandler {
  protected:
    BaseNameHandler(char* name) : name_(name) {}
    void PrintName() {
      // Print quoted name for JSON dictionary key. The decision of
      // whether to add a comma before this is made by the caller.
      Serial.print('"');
      Serial.print(name_);
      Serial.print("\":");
    }

  private:
    const char* const name_;
};

class CurrentHandler : public BaseNameHandler {
  public:
    CurrentHandler(char* name, int pin, float scale)
      : BaseNameHandler(name), pin_(pin), scale_(scale) {}
    void Collect() {
      reading_ = analogRead(pin_);
      amps_ = reading_ * scale_;
    }
    void ReportReading() {
      PrintName();
      Serial.print(reading_);
    }
    void ReportAmps() {
      PrintName();
      Serial.print(amps_);
    }

  private:
    const int pin_;
    const float scale_;

    int reading_;
    float amps_;
};

// One CurrentHandler instance for each of the current sensors.
CurrentHandler current_handlers[] = {
  {"main", I_MAIN, main_amps_mult},
  {"fan", I_FAN, fan_amps_mult},
  {"mount", I_MOUNT, mount_amps_mult},
  {"cameras", I_CAMERAS, cameras_amps_mult},
};

class DigitalInputHandler : public BaseNameHandler {
  public:
    DigitalInputHandler(char* name, int pin)
      : BaseNameHandler(name), pin_(pin) {}
    void Collect() {
      reading_ = digitalRead(pin_);
    }
    void Report() {
      PrintName();
      Serial.print(reading_);
    }
  private:
    const int pin_;
    int reading_;
};

// One DigitalInputHandler for each of the GPIO pins for which we report the value.
// Most are actually output pins, but the Arduino API allows us to read the value
// that is being output.
DigitalInputHandler di_handlers[] = {
  {"computer", COMP_RELAY},
  {"fan", FAN_RELAY},
  {"mount", MOUNT_RELAY},
  {"cameras", CAMERAS_RELAY},
  {"weather", WEATHER_RELAY},
  {"main", AC_PIN},
};

/////////////////////////////////////////////////////////////////////////////////////////
// General reporting code.

// Due to limitations of the Arduino preprocessor, we must place the following all on one line:
template<class T, int size> void ReportCollection(const char* name, T(&handlers)[size]) {
  // This is being added to a JSON dictionary, so print a comma
  // before the quoted name, which is then followed by a colon.
  Serial.print(", \"");
  Serial.print(name);
  Serial.print("\": {");
  bool first = true;
  for (auto& handler : handlers) {
    if (first) {
      first = false;
    } else {
      Serial.print(", ");
    }
    handler.Report();
  }
  Serial.print('}');
}

// Due to limitations of the Arduino preprocessor, we must place the following all on one line:
template<class T, int size> void PrintCollection(const char* name, T(&handlers)[size], void (T::*mf)()) {
  // This is being added to a JSON dictionary, so print a comma
  // before the quoted name, which is then followed by a colon.
  Serial.print(", \"");
  Serial.print(name);
  Serial.print("\": {");
  bool first = true;
  for (auto& handler : handlers) {
    if (first) {
      first = false;
    } else {
      Serial.print(",");
    }
    (handler.*mf)();
  }
  Serial.print('}');
}

// Produce a single JSON line with the current values reported by
// the sensors and the settings of the relays.
void Report(unsigned long now) {
  static unsigned long report_num = 0;

  // Collect values from all of the sensors & replays.
  dht_handler.Collect();
  dt_handler.Collect();
  for (auto& di_handler : di_handlers) {
    di_handler.Collect();
  }
  for (auto& handler : current_handlers) {
    handler.Collect();
  }

  // Print the collected values as JSON.
  Serial.print("{\"name\":\"telemetry_board\", \"count\":");
  Serial.print(millis());
  Serial.print(", \"num\":");
  Serial.print(++report_num);
  Serial.print(", \"ver\":");
  Serial.print(JSON_VERSION_ID);

  ReportCollection("power", di_handlers);
  PrintCollection("current", current_handlers, &CurrentHandler::ReportReading);
  PrintCollection("amps", current_handlers, &CurrentHandler::ReportAmps);
  dht_handler.Report();
  dt_handler.Report();

  Serial.println("}");
}

//////////////////////////////////////////////////////////////////////////////////
// Serial input support

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
      int pin_num, pin_status;
      if (input_buffer_.ParseInt(&pin_num) &&
          input_buffer_.MatchAndConsume(',') &&
          input_buffer_.ParseInt(&pin_status) &&
          input_buffer_.Empty()) {
        switch (pin_num) {
          case COMP_RELAY:
            /* The computer shutting itself off:
                - Power down
                - Wait 30 seconds
                - Power up
            */
            if (pin_status == 0) {
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
    }

    CharBuffer<8> input_buffer_;
    bool wait_for_new_line_{false};
} serial_input_handler;

// A simple count-down timer.
class IntervalTimer {
  public:
    IntervalTimer(unsigned int interval_ms)
      : interval_(interval_ms), remaining_(interval_ms) {}
    bool HasExpired() {
      unsigned long now = millis();
      unsigned long elapsed = now - last_time_;
      last_time_ = now;
      // Note: not checking for elapsed being so large that it
      // exceeds the ability to be represented in remaining_.
      remaining_ -= elapsed;
      if (remaining_ <= 0) {
        remaining_ += interval_;
        if (remaining_ < 0) {
          remaining_ = interval_;
        }
        return true;
      }
      return false;
    }

  private:
    unsigned long last_time_{0};
    long remaining_;
    const unsigned int interval_;
};

//////////////////////////////////////////////////////////////////////////////////
// Primary Arduino defined methods: setup(), called once at start, and loop(),
// called repeatedly (roughly as soon as it returns).

void setup() {
  Serial.begin(9600);
  Serial.flush();

  pinMode(LED_BUILTIN, OUTPUT);

  // Setup relay pins.
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

  // Setup communications with the sensors.
  dht_handler.Init();
  dt_handler.Init();
  // dt_handler.PrintDeviceInfo();

  pinMode(AC_PIN, INPUT);
}

void loop() {
  serial_input_handler.Handle();

  // Every REPORT_INTERVAL_MS we want to produce a report on sensor values,
  // and relay settings.
  static IntervalTimer report_timer(REPORT_INTERVAL_MS);
  if (report_timer.HasExpired()) {
    digitalWrite(LED_BUILTIN, HIGH);
    Report(millis());
    digitalWrite(LED_BUILTIN, LOW);
  } else if (!Serial) {
    // Do a rapid blink of the LED if there is apparently no serial
    // line connection. Note that we still call the serial input
    // handler and print reports, just in case !Serial is wrong.
    static IntervalTimer fast_blink_timer(100);
    if (fast_blink_timer.HasExpired()) {
      toggle_led();
    }
  }
}
