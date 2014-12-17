#include <stdlib.h>
#include <OneWire.h>

#include <DHT.h>

#define DHTPIN 3 // DHT Temp & Humidity Pin
#define DHTTYPE DHT22   // DHT 22  (AM2302)

int ac_probe = 0;
int dc_probe = 1;

int led_pin = 13;
int led_value = LOW;

int fan_pin = 4;

int ds18_01_pin = 2;
const int num_ds18 = 3; // Number of DS18B20 Sensors
uint8_t sensors_address[num_ds18][8]; //here will store the sensors addresses for later use

// Temperature chip I/O
OneWire sensor_bus(ds18_01_pin); // on digital pin 2
float get_ds18b20_temp (uint8_t *address);

// Setup DHT22
DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);

  pinMode(led_pin, OUTPUT);
  pinMode(ds18_01_pin, OUTPUT);
  pinMode(fan_pin, OUTPUT);

  dht.begin();
  Serial.println("DHT22found");

  // Turn on the fan
  turn_fan_on();

  int x, c = 0;
  Serial.println("Starting to look for sensors...");
  for (x = 0; x < num_ds18; x++) {
    if (sensor_bus.search(sensors_address[x]))
      c++;
  }
}

void loop() {
  Serial.print("{");

  read_voltages();

  Serial.print(",");

  read_dht_temp();
  read_ds18b20_temp();

  Serial.println("}");

  toggle_led();

  delay(1000);
}


/* DC Probe: ~730 = 11.53 */
void read_voltages() {
  int ac_reading = analogRead(ac_probe);
  float ac_voltage = ac_reading / 1023 * 5;

  int dc_reading = analogRead(dc_probe);
  float dc_voltage = dc_reading * 0.0158;

  Serial.print("\"voltages\":{");
  Serial.print("\"ac\":"); Serial.print(ac_voltage); Serial.print(',');
  Serial.print("\"dc\":"); Serial.print(dc_voltage);
  Serial.print('}');
}

//// Reading temperature or humidity takes about 250 milliseconds!
//// Sensor readings may also be up to 2 seconds 'old' (its a very slow sensor)
void read_dht_temp() {
  float h = dht.readHumidity();
  float c = dht.readTemperature(); // Celsius

  // Check if any reads failed and exit early (to try again).
  // if (isnan(h) || isnan(t)) {
  //   Serial.println("Failed to read from DHT sensor!");
  //   return;
  // }

  Serial.print("\"humidity\":"); Serial.print(h); Serial.print(',');
  Serial.print("\"temp_01\":"); Serial.print(c); Serial.print(',');
}

void read_ds18b20_temp() {

  for (int x = 1; x < num_ds18; x++) {
    Serial.print("\"temp_0");
    Serial.print(x + 1);
    Serial.print("\":");
    Serial.print(get_ds18b20_temp(sensors_address[x]));

    // Append a comma to all but last
    if (x < num_ds18 - 1) {
      Serial.print(",");
    }
  }
}

float get_ds18b20_temp(uint8_t *addr) {
  byte data[12];

  sensor_bus.reset();
  sensor_bus.select(addr);
  sensor_bus.write(0x44, 1); // start conversion, with parasite power on at the end

  byte present = sensor_bus.reset();
  sensor_bus.select(addr);
  sensor_bus.write(0xBE); // Read Scratchpad

  for (int i = 0; i < 9; i++) { // we need 9 bytes
    data[i] = sensor_bus.read();
  }

  sensor_bus.reset_search();

  byte MSB = data[1];
  byte LSB = data[0];

  float tempRead = ((MSB << 8) | LSB); //using two's compliment
  float TemperatureSum = tempRead / 16;

  return TemperatureSum;
}

/************************************
* Utitlity Methods
*************************************/

void toggle_led() {
  led_value = ! led_value;
  digitalWrite(led_pin, led_value);
}

void turn_fan_on() {
  digitalWrite(fan_pin, HIGH);
  Serial.println("Fan turned on");
}

void turn_fan_off() {
  digitalWrite(fan_pin, LOW);
  Serial.println("Fan turned off");
}
