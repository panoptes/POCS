// This script is for a Weather Station that contains two RG-11 Rain Gauges, 
// a DHT22 Humidity and Temperature Sensor, two TMP36 Temperature Sensors, 
// a TSL235R Light to Frequency Sensor, and an MLX90614 Infrared Thermometer.
//
// Program will read sensors and periodically print out a line of text via
// serial with the readings.


#include <i2cmaster.h>
#include <DHT.h>


// Pin Constants
const int WarningLEDpin = 13; // This LED turns on when the weather conditions are not good for observing.
const int RainSensor1 = 7; // The Rain Gauges can be connected to any of the digital pins.
const int RainSensor2 = 8;
const int TMP36pin1 = 2; // The TMP36 sensors must be connected to analogue pins.
const int TMP36pin2 = 3;
#define DHTPIN 5 // The DHT22 is connected to a digital pin.
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);


// Thresholds for Warnings
// --> These need to be modified after experience in the field
const float Threshold_VeryCloudy = -20.0;
const float Threshold_Cloudy     = -40.0;
const float Threshold_Humidity   = 80.0;


// Constants for TSL235R
volatile unsigned long cnt = 0;
unsigned long oldcnt = 0;
unsigned long t = 0;
unsigned long last;

void irq1()
{
  cnt++;
}


void setup() {
    Serial.begin(9600);

    Serial.print("Setup LED Pin...");
    pinMode(WarningLEDpin, OUTPUT);
    Serial.println("done!");

    Serial.print("Setup DHT22...");
    dht.begin();
    Serial.println("done!");

    Serial.print("Setup I2C...");
    i2c_init(); // Initialise the i2c bus
    PORTC = (1 << PORTC4) | (1 << PORTC5); // Enable pullups
    Serial.println("done!");

    Serial.print("Setup TSL235R...");
    pinMode(2, INPUT); // TSL235R must use digital pin 2.
    digitalWrite(2, HIGH);
    attachInterrupt(0, irq1, RISING);
    Serial.println("done!");

    Serial.print("Setup first RG-11...");
    pinMode(RainSensor1, INPUT);
    Serial.println("done!");

    Serial.print("Setup second RG-11...");
    pinMode(RainSensor2, INPUT);
    Serial.println("done!");


  // print header to Serial
    Serial.print("Light       ");
    Serial.print("SkyTemp   ");
    Serial.print("AmbTemp   ");
    Serial.print("Humidity  ");
    Serial.print("HW    ");
    Serial.print("TempDiff  ");
    Serial.print("CW    ");
    Serial.print("CaseTemp 1 ");
    Serial.print("CaseTemp 2 ");
    Serial.print("Rain1?  ");
    Serial.print("Rain2?  ");
    Serial.print("Safe?  ");
    Serial.println("");
}

void loop() {

    // Read light level TSL235R in mW/m2
    last = millis();
    t = cnt;
    unsigned long hz = t - oldcnt;
    oldcnt = t;
    float Light = (hz+50)/100; // +50 == rounding last digit
    // print output to Serial
    Serial.print(Light);  
    Serial.print(" mW/m2 ");
    
    // Read sky temperature MLX90614 in Celsius
    float SkyTemp_C = readMLX90614() - 273.15; // Converting from Kelvin to Celsius
    // print output to Serial
    Serial.print(SkyTemp_C);
    Serial.print(" C   ");

    // Read ambient temperature and humidity DHT22
    float Humidity = dht.readHumidity();
    float AmbTemp_C = dht.readTemperature();
    // check if returns are valid, if they are NaN (not a number) then something went wrong!
    if (isnan(AmbTemp_C) || isnan(Humidity)) {
        Serial.println("Failed to read from DHT");
    }
    int HumidityWarning = 0;
    if (Humidity > Threshold_Humidity) { HumidityWarning = 1; }
    // print output to Serial
    Serial.print(AmbTemp_C);
    Serial.print(" C   ");
    Serial.print(Humidity);
    Serial.print(" %   ");
    Serial.print(HumidityWarning);
    Serial.print("     ");

    // Determine Sky / Ambient Temperature Difference
    float TempDiff = SkyTemp_C - AmbTemp_C;
    int Cloudiness;
    // print output to Serial
    Serial.print(TempDiff);
    Serial.print(" C    ");
    if (TempDiff >= Threshold_VeryCloudy) { Cloudiness = 2; }
    if (TempDiff >= Threshold_Cloudy && TempDiff < Threshold_VeryCloudy) { Cloudiness = 1; }
    if (TempDiff < Threshold_Cloudy) { Cloudiness = 0; }
    // print output to Serial
    Serial.print(Cloudiness);
    Serial.print("     ");
    
    // Read case temperature from TMP36 primary
    int TMP36reading1 = analogRead(TMP36pin1);
    float TMP36voltage1 = (TMP36reading1 / 1024.0) * 5000;
    float CaseTemp_C1 = (TMP36voltage1 -500) / 10.0;
    // print output to Serial
    Serial.print(CaseTemp_C1);
    Serial.print(" C    ");

    // Read case temperature from TMP36 secondary
    int TMP36reading2 = analogRead(TMP36pin2);
    float TMP36voltage2 = (TMP36reading2 / 1024.0) * 5000;
    float CaseTemp_C2 = (TMP36voltage2 -500) / 10.0;
    // print output to Serial
    Serial.print(CaseTemp_C2);
    Serial.print(" C    ");

    // Are the RG-11 Rain Gauges on?
    int rain1;
    rain1 = digitalRead(RainSensor1);   // read the input pin
    // print output to Serial
    Serial.print(rain1);
    Serial.print("      ");

    int rain2;
    rain2 = digitalRead(RainSensor2);   // read the input pin
    // print output to Serial
    Serial.print(rain2);
    Serial.print("      ");

    // Are conditions safe?
    bool Safe = false;
    if (HumidityWarning == 0 && Cloudiness <= 1) { Safe = true; }
    if (Safe) { digitalWrite(WarningLEDpin, LOW); }
    else { digitalWrite(WarningLEDpin, HIGH); }
    // print output to Serial
    Serial.print(Safe);
    Serial.print("      ");

    Serial.println("");
}

// Read MLX90614 IR thermometer and return temperature in Kelvin
float readMLX90614(void){
    int dev = 0x5A<<1;
    int data_low = 0;
    int data_high = 0;
    int pec = 0;
    
    i2c_start_wait(dev+I2C_WRITE);
    i2c_write(0x07);
    
    i2c_rep_start(dev+I2C_READ);
    data_low = i2c_readAck(); // Read 1 byte and then send ack
    data_high = i2c_readAck(); // Read 1 byte and then send ack
    pec = i2c_readNak();
    i2c_stop();
    
    // This converts high and low bytes together and processes temperature, MSB is an error bit and is ignored for temps
    double tempFactor = 0.02; // 0.02 degrees per LSB (measurement resolution of the MLX90614)
    double tempData = 0x0000; // Zero out the data
    int frac; // Data past the decimal point
    
    // This masks off the error bit of the high byte, then moves it left 8 bits and adds the low byte.
    tempData = (double)(((data_high & 0x007F) << 8) + data_low);
    tempData = (tempData * tempFactor) - 0.01;

    float kelvin = tempData;

    return kelvin;
}
