#ifndef RESOURCES_ARDUINO_FILES_SHARED_DALLAS_TEMPERATURE_HANLDER_H
#define RESOURCES_ARDUINO_FILES_SHARED_DALLAS_TEMPERATURE_HANLDER_H

#include "OneWire.h"
#include "DallasTemperature.h"

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

#endif  // RESOURCES_ARDUINO_FILES_SHARED_DALLAS_TEMPERATURE_HANLDER_H
