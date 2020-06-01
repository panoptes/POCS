#ifndef RESOURCES_ARDUINO_FILES_SHARED_DALLAS_TEMPERATURE_HANLDER_H
#define RESOURCES_ARDUINO_FILES_SHARED_DALLAS_TEMPERATURE_HANLDER_H

#include "OneWire.h"
#include "DallasTemperature.h"

struct DallasTemperatureDeviceInfo {
  bool Init(DallasTemperature* dt, uint8_t device_num) {
    if (!dt->getAddress(address, device_num)) {
      return false;
    }
    index = device_num;
    resolution = dt->getResolution(address);
    return true;
  }
  void PrintInfo() {
    Serial.print("{\"ndx\":");
    Serial.print(index);
    Serial.print(", \"address\":\"");
    for (int j = 0; j < sizeof address; ++j) {
      if (j != 0) {
        Serial.print(" ");
      }
      Serial.print(static_cast<int>(address[j]), HEX);
    }
    Serial.print("\", \"resolution\":");
    Serial.print(static_cast<int>(resolution));
    Serial.print("}");
  }
  bool operator>(const DallasTemperatureDeviceInfo& rhs) const {
    return memcmp(address, rhs.address, sizeof address) < 0;
  }

  DeviceAddress address;
  float temperature;
  uint8_t index;
  uint8_t resolution;
};

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
        if (devices_[device_count_].Init(&dt_, device_num)) {
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
          auto tmp = devices_[j - 1];
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
        auto& device = devices_[i];
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
          auto& device = devices_[i];
          Serial.print(device.temperature);
        }
        Serial.print("]");
      }
    }
    void PrintDeviceInfo() {
      Serial.print(", \"temp_devices\":[");
      for (uint8_t i = 0; i < device_count_; i++) {
        if (i != 0) {
          Serial.print(", ");
        }
        devices_[i].PrintInfo();
      }
      Serial.print("]");
    }

  private:
    DallasTemperature dt_;
    DallasTemperatureDeviceInfo devices_[kMaxSensors];
    uint8_t device_count_;
};

#endif  // RESOURCES_ARDUINO_FILES_SHARED_DALLAS_TEMPERATURE_HANLDER_H
