/* UPDATED CONTROL BOARD SCRIPT FOR 2019V ELECTRONICS */

#include <stdlib.h>

#ifdef ESP32
  #include <WiFi.h>
  #include <ESPAsyncWebServer.h>
#else
  #include <Arduino.h>
  #include <ESP8266WiFi.h>
  #include <Hash.h>
  #include <ESPAsyncTCP.h>
  #include <ESPAsyncWebServer.h>
#endif

#include <OneWire.h>;
#include <DallasTemperature.h>;
#include <DHT.h>;
#include <ArduinoJson.h>;

// Please update the version identifier when you
// make changes to this code. The value needs to
// be in JSON format (i.e. quoted and escaped if
// a string).
const String BOARD_NAME = "env_board";
const String BOARD_LOCATION = "control_box";
const String VERSION_ID = "2019-07-22";

// Replace with your network credentials
const char* ssid = "panoptes-net";
const char* password = "p@nn-p@ass";

/* Pin setup

  The pin mappings below will depend on the particular microncontroller
  that you have attached, most likely an Ardunio Uno or Arduino Micro.

  The pin structure below is for associating an Ardunio Uno with the Infineon
  relay board. For more information on the Infineon, see the technical documents at:

  https://www.infineon.com/cms/en/product/evaluation-boards/24v_shield_btt6030/#!documents

  Arduino Uno Pins
*/
// Digital Pins
const int DS18_PIN = D2;
const int DHT_PIN = D4;  // DHT Temp & Humidity Pin

/* Sensors

  Set up some information related to the attached sensors.
*/

const int NUM_DS18 = 3; // Number of DS18B20 Sensors

// Temperature chip I/O
OneWire oneWire(DS18_PIN);
DallasTemperature tempSensors(&oneWire);

// Setup DHT22
#define DHTTYPE DHT22   // DHT 22  (AM2302)
DHT dht(DHT_PIN, DHTTYPE);

// Create AsyncWebServer object on port 80
AsyncWebServer server(80);

/* Setup Function

  Put the pins and sensors into their initial state.
*/

String outDoc;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB
  }

  pinMode(LED_BUILTIN, OUTPUT);

  // Start the environmental sensors.
  dht.begin();
  tempSensors.begin();

  // Startup delay - in case of rapid power toggling, we don't
  // want the relays to be turning on and off.
  delay(3000);

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
   
  Serial.println();
  // Print ESP Local IP Address
  Serial.println(WiFi.localIP());

  // Route for root / web page
  server.on("/temp", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send_P(200, "text/plain", outDoc.c_str());
  });
  
  // Start server
  server.begin();

}

/************************************
* Utility Functions
*************************************/

void toggle_pin_delay(int pin_num) {
  turn_pin_off(pin_num);
  delay(1000 * 30);
  turn_pin_on(pin_num);
}

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

void loop() {
  get_readings();
  delay(1000);
}

/************************************
* Sensor Functions
*************************************/


void get_readings() {
  float temps[NUM_DS18+1];
  float humidity[1];

  read_dht_temp(temps, humidity);
  read_ds18b20_temp(temps);

  // Create our JsonDocument
  // https://arduinojson.org/v6/assistant/
  const size_t capacity = JSON_ARRAY_SIZE(0) + 2*JSON_ARRAY_SIZE(1) +
                        JSON_ARRAY_SIZE(2) + JSON_ARRAY_SIZE(3) +
                        2*JSON_OBJECT_SIZE(3) + 5*JSON_OBJECT_SIZE(5);

  DynamicJsonDocument doc(capacity);

  doc["name"] = BOARD_NAME;
  doc["version"] = VERSION_ID;
  doc["time"] = millis();
  doc["location"] = BOARD_LOCATION;

  // Add the environment sensors to the document.
  JsonArray sensors = doc.createNestedArray("sensors");
  JsonObject sensors_0 = sensors.createNestedObject();
  sensors_0["name"] = "DHT";
  JsonArray sensors_0_humidity = sensors_0.createNestedArray("humidity");
  sensors_0_humidity.add(humidity[0]);
  JsonArray sensors_0_temperature = sensors_0.createNestedArray("temperature");
  sensors_0_temperature.add(temps[0]);

  JsonObject sensors_1 = sensors.createNestedObject();
  sensors_1["name"] = "DS18B20";
  JsonArray sensors_1_humidity = sensors_1.createNestedArray("humidity");

  JsonArray sensors_1_temperature = sensors_1.createNestedArray("temperature");
  sensors_1_temperature.add(temps[1]);
  sensors_1_temperature.add(temps[2]);
  sensors_1_temperature.add(temps[3]);

  // Write out the JSON document and a newline.
  // serializeJson(doc, Serial);
  // Serial.println(); // Add a newline

  outDoc = String();
  serializeJson(doc, outDoc);
}


// Reading temperature or humidity takes about 250 milliseconds!
// Sensor readings may also be up to 2 seconds 'old' (it's a very slow sensor)
void read_dht_temp(float temps[], float humidity[]) {
  humidity[0] = dht.readHumidity();
  temps[0] = dht.readTemperature();
}

/* Read DS18B20 Sensors

Loop through the number of connected sensors and gather temperature.

*/
void read_ds18b20_temp(float temps[]) {

  tempSensors.requestTemperatures();

  temps[1] = tempSensors.getTempCByIndex(0);
  temps[2] = tempSensors.getTempCByIndex(1);
  temps[3] = tempSensors.getTempCByIndex(2);
}

