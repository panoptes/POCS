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
#include "Adafruit_Sensor.h"

/*=========================================================================
    I2C ADDRESS/BITS
    -----------------------------------------------------------------------*/
    #define MMA8451_DEFAULT_ADDRESS                 (0x1D)    // if A is GND, its 0x1C
/*=========================================================================*/

#define MMA8451_REG_OUT_X_MSB     0x01
#define MMA8451_REG_SYSMOD        0x0B
#define MMA8451_REG_WHOAMI        0x0D
#define MMA8451_REG_XYZ_DATA_CFG  0x0E
#define MMA8451_REG_PL_STATUS     0x10
#define MMA8451_REG_PL_CFG        0x11
#define MMA8451_REG_CTRL_REG1     0x2A
#define MMA8451_REG_CTRL_REG2     0x2B
#define MMA8451_REG_CTRL_REG4     0x2D
#define MMA8451_REG_CTRL_REG5     0x2E



#define MMA8451_PL_PUF            0
#define MMA8451_PL_PUB            1
#define MMA8451_PL_PDF            2
#define MMA8451_PL_PDB            3
#define MMA8451_PL_LRF            4  
#define MMA8451_PL_LRB            5  
#define MMA8451_PL_LLF            6  
#define MMA8451_PL_LLB            7  

typedef enum
{
  MMA8451_RANGE_8_G           = 0b10,   // +/- 8g
  MMA8451_RANGE_4_G           = 0b01,   // +/- 4g
  MMA8451_RANGE_2_G           = 0b00    // +/- 2g (default value)
} mma8451_range_t;


/* Used with register 0x2A (MMA8451_REG_CTRL_REG1) to set bandwidth */
typedef enum
{
  MMA8451_DATARATE_800_HZ     = 0b000, //  400Hz 
  MMA8451_DATARATE_400_HZ     = 0b001, //  200Hz
  MMA8451_DATARATE_200_HZ     = 0b010, //  100Hz
  MMA8451_DATARATE_100_HZ     = 0b011, //   50Hz
  MMA8451_DATARATE_50_HZ      = 0b100, //   25Hz
  MMA8451_DATARATE_12_5_HZ    = 0b101, // 6.25Hz
  MMA8451_DATARATE_6_25HZ     = 0b110, // 3.13Hz
  MMA8451_DATARATE_1_56_HZ    = 0b111, // 1.56Hz
} mma8451_dataRate_t;

class Adafruit_MMA8451 : public Adafruit_Sensor {
 public:
  Adafruit_MMA8451(int32_t id = -1);

  
  bool       begin(uint8_t addr = MMA8451_DEFAULT_ADDRESS);

  void read();

  void setRange(mma8451_range_t range);
  mma8451_range_t getRange(void);

  void setDataRate(mma8451_dataRate_t dataRate);
  mma8451_dataRate_t getDataRate(void);

  void getEvent(sensors_event_t *event);
  void getSensor(sensor_t *sensor);

  uint8_t getOrientation(void);

  int16_t x, y, z;
  float x_g, y_g, z_g;

  void writeRegister8(uint8_t reg, uint8_t value);
 private:
  uint8_t readRegister8(uint8_t reg);
  int32_t _sensorID;
  int8_t  _i2caddr;
};
