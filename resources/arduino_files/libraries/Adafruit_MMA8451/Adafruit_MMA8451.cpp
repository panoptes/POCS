/**************************************************************************/
/*!
    @file     Adafruit_MMA8451.h
    @author   K. Townsend (Adafruit Industries)
    @license  BSD (see license.txt)

    This is a library for the Adafruit MMA8451 Accel breakout board
    ----> https://www.adafruit.com/products/2019

    Adafruit invests time and resources providing this open source code,
    please support Adafruit and open-source hardware by purchasing
    products from Adafruit!

    @section  HISTORY

    v1.0  - First release
*/
/**************************************************************************/

#if ARDUINO >= 100
 #include "Arduino.h"
#else
 #include "WProgram.h"
#endif

#include <Wire.h>
#include "Adafruit_MMA8451.h"

/**************************************************************************/
/*!
    @brief  Abstract away platform differences in Arduino wire library
*/
/**************************************************************************/
static inline uint8_t i2cread(void) {
  #if ARDUINO >= 100
  return Wire.read();
  #else
  return Wire.receive();
  #endif
}

static inline void i2cwrite(uint8_t x) {
  #if ARDUINO >= 100
  Wire.write((uint8_t)x);
  #else
  Wire.send(x);
  #endif
}


/**************************************************************************/
/*!
    @brief  Writes 8-bits to the specified destination register
*/
/**************************************************************************/
void Adafruit_MMA8451::writeRegister8(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(_i2caddr);
  i2cwrite((uint8_t)reg);
  i2cwrite((uint8_t)(value));
  Wire.endTransmission();
}

/**************************************************************************/
/*!
    @brief  Reads 8-bits from the specified register
*/
/**************************************************************************/
uint8_t Adafruit_MMA8451::readRegister8(uint8_t reg) {
    Wire.beginTransmission(_i2caddr);
    i2cwrite(reg);
    Wire.endTransmission(false); // MMA8451 + friends uses repeated start!!

    Wire.requestFrom(_i2caddr, 1);
    if (! Wire.available()) return -1;
    return (i2cread());
}

/**************************************************************************/
/*!
    @brief  Instantiates a new MMA8451 class in I2C mode
*/
/**************************************************************************/
Adafruit_MMA8451::Adafruit_MMA8451(int32_t sensorID) {
  _sensorID = sensorID;
}

/**************************************************************************/
/*!
    @brief  Setups the HW (reads coefficients values, etc.)
*/
/**************************************************************************/
bool Adafruit_MMA8451::begin(uint8_t i2caddr) {
  Wire.begin();
  _i2caddr = i2caddr;

  /* Check connection */
  uint8_t deviceid = readRegister8(MMA8451_REG_WHOAMI);
  if (deviceid != 0x1A)
  {
    /* No MMA8451 detected ... return false */
    //Serial.println(deviceid, HEX);
    return false;
  }

  writeRegister8(MMA8451_REG_CTRL_REG2, 0x40); // reset

  while (readRegister8(MMA8451_REG_CTRL_REG2) & 0x40);

  // enable 4G range
  writeRegister8(MMA8451_REG_XYZ_DATA_CFG, MMA8451_RANGE_4_G);
  // High res
  writeRegister8(MMA8451_REG_CTRL_REG2, 0x02);
  // Low noise!
  writeRegister8(MMA8451_REG_CTRL_REG4, 0x01);
  // DRDY on INT1
  writeRegister8(MMA8451_REG_CTRL_REG4, 0x01);
  writeRegister8(MMA8451_REG_CTRL_REG5, 0x01);

  // Turn on orientation config
  writeRegister8(MMA8451_REG_PL_CFG, 0x40);

  // Activate!
  writeRegister8(MMA8451_REG_CTRL_REG1, 0x01); // active, max rate

  /*
  for (uint8_t i=0; i<0x30; i++) {
    Serial.print("$");
    Serial.print(i, HEX); Serial.print(" = 0x");
    Serial.println(readRegister8(i), HEX);
  }
  */

  return true;
}


void Adafruit_MMA8451::read(void) {
  // read x y z at once
  Wire.beginTransmission(_i2caddr);
  i2cwrite(MMA8451_REG_OUT_X_MSB);
  Wire.endTransmission(false); // MMA8451 + friends uses repeated start!!

  Wire.requestFrom(_i2caddr, 6);
  x = Wire.read(); x <<= 8; x |= Wire.read(); x >>= 2;
  y = Wire.read(); y <<= 8; y |= Wire.read(); y >>= 2;
  z = Wire.read(); z <<= 8; z |= Wire.read(); z >>= 2;


  uint8_t range = getRange();
  uint16_t divider = 1;
  if (range == MMA8451_RANGE_8_G) divider = 1024;
  if (range == MMA8451_RANGE_4_G) divider = 2048;
  if (range == MMA8451_RANGE_2_G) divider = 4096;

  x_g = (float)x / divider;
  y_g = (float)y / divider;
  z_g = (float)z / divider;

}

/**************************************************************************/
/*!
    @brief  Read the orientation: 
    Portrait/Landscape + Up/Down/Left/Right + Front/Back
*/
/**************************************************************************/
uint8_t Adafruit_MMA8451::getOrientation(void) {
  return readRegister8(MMA8451_REG_PL_STATUS) & 0x07;
}

/**************************************************************************/
/*!
    @brief  Sets the g range for the accelerometer
*/
/**************************************************************************/
void Adafruit_MMA8451::setRange(mma8451_range_t range)
{
  // lower bits are range
  writeRegister8(MMA8451_REG_CTRL_REG1, 0x00); // deactivate
  writeRegister8(MMA8451_REG_XYZ_DATA_CFG, range & 0x3);
  writeRegister8(MMA8451_REG_CTRL_REG1, 0x01); // active, max rate
}

/**************************************************************************/
/*!
    @brief  Sets the g range for the accelerometer
*/
/**************************************************************************/
mma8451_range_t Adafruit_MMA8451::getRange(void)
{
  /* Read the data format register to preserve bits */
  return (mma8451_range_t)(readRegister8(MMA8451_REG_XYZ_DATA_CFG) & 0x03);
}

/**************************************************************************/
/*!
    @brief  Sets the data rate for the MMA8451 (controls power consumption)
*/
/**************************************************************************/
void Adafruit_MMA8451::setDataRate(mma8451_dataRate_t dataRate)
{
  uint8_t ctl1 = readRegister8(MMA8451_REG_CTRL_REG1);
  ctl1 &= ~(0x28); // mask off bits
  ctl1 |= (dataRate << 3);
  writeRegister8(MMA8451_REG_CTRL_REG1, ctl1);
}

/**************************************************************************/
/*!
    @brief  Sets the data rate for the MMA8451 (controls power consumption)
*/
/**************************************************************************/
mma8451_dataRate_t Adafruit_MMA8451::getDataRate(void)
{
  return (mma8451_dataRate_t)((readRegister8(MMA8451_REG_CTRL_REG1) >> 3)& 0x07);
}

/**************************************************************************/
/*! 
    @brief  Gets the most recent sensor event
*/
/**************************************************************************/
void Adafruit_MMA8451::getEvent(sensors_event_t *event) {
  /* Clear the event */
  memset(event, 0, sizeof(sensors_event_t));

  event->version   = sizeof(sensors_event_t);
  event->sensor_id = _sensorID;
  event->type      = SENSOR_TYPE_ACCELEROMETER;
  event->timestamp = 0;

  read();

  event->acceleration.x = x_g;
  event->acceleration.y = y_g;
  event->acceleration.z = z_g;
}

/**************************************************************************/
/*! 
    @brief  Gets the sensor_t data
*/
/**************************************************************************/
void Adafruit_MMA8451::getSensor(sensor_t *sensor) {
  /* Clear the sensor_t object */
  memset(sensor, 0, sizeof(sensor_t));

  /* Insert the sensor name in the fixed length char array */
  strncpy (sensor->name, "MMA8451", sizeof(sensor->name) - 1);
  sensor->name[sizeof(sensor->name)- 1] = 0;
  sensor->version     = 1;
  sensor->sensor_id   = _sensorID;
  sensor->type        = SENSOR_TYPE_ACCELEROMETER;
  sensor->min_delay   = 0;
  sensor->max_value   = 0;             
  sensor->min_value   = 0;
  sensor->resolution  = 0;             
}
