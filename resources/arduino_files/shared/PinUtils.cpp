#include "PinUtils.h"

#include <stdlib.h>

#include "Arduino.h"

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

// pinMode copied from https://github.com/arduino/Arduino/issues/4606.
int pinMode(int pin) {
  if (pin >= NUM_DIGITAL_PINS) return (-1);

  uint8_t bit = digitalPinToBitMask(pin);
  uint8_t port = digitalPinToPort(pin);
  volatile uint8_t *reg = portModeRegister(port);
  if (*reg & bit) return (OUTPUT);

  volatile uint8_t *out = portOutputRegister(port);
  return ((*out & bit) ? INPUT_PULLUP : INPUT);
}
