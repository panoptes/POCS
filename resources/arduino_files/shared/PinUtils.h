#ifndef RESOURCES_ARDUINO_FILES_SHARED_PIN_UTILS_H
#define RESOURCES_ARDUINO_FILES_SHARED_PIN_UTILS_H

// Utility Methods

void turn_pin_on(int pin_num);
void turn_pin_off(int pin_num);
bool is_pin_on(int pin_num);
void toggle_pin(int pin_num);
void toggle_led();

// Returns the mode (INPUT, OUTPUT, or INPUT_PULLUP) for a pin.
int pinMode(int pin);

#endif  // RESOURCES_ARDUINO_FILES_SHARED_PIN_UTILS_H