#include <Wire.h>
#include <stdlib.h>

#include "Adafruit_MMA8451.h"
#include "Adafruit_Sensor.h"
#include "dht_handler.h"
#include "PinUtils.h"

const int DHT_PIN = 9;      // DHT Temp & Humidity Pin
const int CAM_0_RELAY = 5;
const int CAM_1_RELAY = 6;
const int RESET_PIN = 12;

// Type of Digital Humidity and Temperature (DHT) Sensor
#define DHTTYPE DHT22   // DHT 22  (AM2302)

// IO Handlers.

class AccelerometerHandler {
  public:
    void init() {
      ready_ = false;
      has_reading_ = false;
      ready();
    }
    void collect() {
      if (ready()) {
        accelerometer_.getEvent(&event_);
        orientation_ = accelerometer_.getOrientation(); // Orientation
        has_reading_ = true;
      }
    }
    void report() {
      if (has_reading_) {
        Serial.print(", \"accelerometer\":{\"x\":");
        Serial.print(event_.acceleration.x);
        Serial.print(", \"y\":");
        Serial.print(event_.acceleration.y);
        Serial.print(", \"z\":");
        Serial.print(event_.acceleration.z);
        Serial.print(", \"o\": "); Serial.print(orientation_);
        Serial.print("}");
      }
    }
    bool ready() {
      if (!ready_) {
        ready_ = accelerometer_.begin();
        if (!ready_) {
          Serial.println("Accelerometer not ready, or not present.");
        } else {
          // Check Accelerometer range
          // accelerometer.setRange(MMA8451_RANGE_2_G);
          // Serial.print("Accelerometer Range = "); Serial.print(2 << accelerometer.getRange());
          // Serial.println("G");
        }
      }
      return ready_;
    }

  private:
    Adafruit_MMA8451 accelerometer_;
    sensors_event_t event_;
    uint8_t orientation_;
    bool ready_;
    bool has_reading_;
} acc_handler;

// DHT22: Relative Humidity & Temperature Sensor.
DHTHandler dht_handler(DHT_PIN, DHTTYPE);

unsigned long end_setup_millis;
unsigned long next_report_millis;
int report_num = 0;

class LedHandler {
  public:
    void init() {
      pinMode(LED_BUILTIN, OUTPUT);
      digitalWrite(LED_BUILTIN, false);

      // Provide a visible signal that setup has been entered.
      if (Serial) {
        // 2 seconds of fast blinks.
        for (int i = 0; i < 40; ++i) {
          delay(50);
          toggle_led();
        }
        Serial.println("LED blink complete");
      } else {
        // 2 seconds of slow blinks.
        for (int i = 0; i < 10; ++i) {
          delay(200);
          toggle_led();
        }
      }
    }

    void update() {
      unsigned long now = millis();
      if (next_change_ms_ <= now) {
        toggle_led();
        next_change_ms_ += (Serial ? 1000 : 100);
        if (next_change_ms_ <= now) {
          next_change_ms_ = now;
        }
      }
    }

  private:
    unsigned long next_change_ms_ = 0;
} led_handler;

void setup(void) {
  Serial.begin(9600);
  Serial.flush();

  led_handler.init();

  // Setup Camera relays
  pinMode(CAM_0_RELAY, OUTPUT);
  pinMode(CAM_1_RELAY, OUTPUT);

  // Turn on Camera relays
  turn_pin_on(CAM_0_RELAY);
  turn_pin_on(CAM_1_RELAY);

  acc_handler.init();
  dht_handler.Init();

  Serial.println("EXIT setup()");
  next_report_millis = end_setup_millis = millis();
}

void loop() {
  led_handler.update();
  if (Serial) {
    main_loop();
  }
}

static int inputs = 0;

void main_loop() {
  unsigned long now = millis();
  if (next_report_millis <= now) {
    // Schedule the next report for `interval' milliseconds from the last report,
    // unless we've fallen behind.
    constexpr int interval = 1000;
    next_report_millis += interval;
    if (next_report_millis <= now) {
      next_report_millis = now + interval;
    }

    // Collect the data. Since some of these operations take a while, keep updating the
    // LED as appropriate. Could probably be done with an interrupt handler instead.
    report_num++;
    acc_handler.collect();
    led_handler.update();
    dht_handler.Collect();
    led_handler.update();
    bool cam0 = digitalRead(CAM_0_RELAY);
    bool cam1 = digitalRead(CAM_1_RELAY);

    // Format/output the results.
    Serial.print("{\"name\":\"camera_board\", \"count\":");
    led_handler.update();
    // TODO(jamessynge): Deal with wrap around here.
    Serial.print(millis() - end_setup_millis);
    led_handler.update();
    Serial.print(", \"num\":");
    led_handler.update();
    Serial.print(report_num);
    led_handler.update();
    Serial.print(", \"inputs_received\":");
    led_handler.update();
    Serial.print(inputs);
    led_handler.update();
    Serial.print(", \"camera_00\":");
    led_handler.update();
    Serial.print(cam0);
    led_handler.update();
    Serial.print(", \"camera_01\":");
    led_handler.update();
    Serial.print(cam1);
    led_handler.update();
    acc_handler.report();
    led_handler.update();
    dht_handler.Report();
    led_handler.update();
    Serial.println("}");
    led_handler.update();
    Serial.flush();
    led_handler.update();
  }

  // Read any serial input
  //    - Input will be two integers (with anything in between them), the
  //      first specifying the pin and the second the status
  //      to change to (1/0). Cameras and debug led are
  //      supported.
  //      Example serial input:
  //           5,1   # Turn camera 0 on
  //           6,0   # Turn camera 1 off
  //          13,0   # Turn led off
  while (Serial.available() > 0) {
    inputs++;
    int pin_num = Serial.parseInt();
    int pin_status = Serial.parseInt();

    switch (pin_num) {
      case CAM_0_RELAY:
      case CAM_1_RELAY:
        if (pin_status == 1) {
          turn_pin_on(pin_num);
        } else if (pin_status == 0) {
          turn_pin_off(pin_num);
        }
        break;
    }
  }
}
