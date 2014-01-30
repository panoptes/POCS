/*
Canon DSLR Camera Control

To activate cameras send a serial tring to the board.  The string should 
consist of three integers.  The first and second indicate which cameras
should be activated.  Any non-zero, positive integer in the first field
will activate the first camera and any non-zero integer in the second
field will activate the second camera.  The third value is the exposure
time in milliseconds.

Serial Commands to Board:
Enn,mmmmmm -- Expose camera for mmmmmm milliseconds.
C          -- Cancel exposure.  Cancels exposure on both cameras.
Q          -- Query which cameras are exposing.
T          -- Query temperature and humidity from DHT22 (only works if camera not exposing)
O          -- Query orientation (only works if camera not exposing)
*/

char Command[3];
char Data[7];
const int bSize = 20; 
char Buffer[bSize];  // Serial buffer
int ByteCount;

int camera1_pin = 2;
int camera2_pin = 4;

//Analog read pins
const int xPin = 0;
const int yPin = 1;
const int zPin = 2;

//The minimum and maximum values that came from
//the accelerometer while standing still
//You very well may need to change these
int minVal = 265;
int maxVal = 402;

//to hold the caculated values
double x;
double y;
double z;

//-----------------------------------------------------------------------------
// SerialParser
//-----------------------------------------------------------------------------
void SerialParser(void) {
    ByteCount = -1;
    ByteCount =  Serial.readBytesUntil('\n',Buffer,bSize);
    if (ByteCount  > 0) {
        strcpy(Command,strtok(Buffer,","));
        strcpy(Data,strtok(NULL,","));
    }
    memset(Buffer, 0, sizeof(Buffer));   // Clear contents of Buffer
    Serial.flush();
}


//-----------------------------------------------------------------------------
// SETUP
//-----------------------------------------------------------------------------
void setup() {
    // Open serial communications and wait for port to open:
    Serial.begin(9600);
    while (!Serial) {
    ; // wait for serial port to connect. Needed for Leonardo only
    }
    Serial.print("Setup Camera Relay Pins ... ");
    pinMode(camera1_pin, OUTPUT);
    pinMode(camera2_pin, OUTPUT);
    digitalWrite(camera1_pin, LOW);
    digitalWrite(camera2_pin, LOW);
    Serial.println("done!");
}


//-----------------------------------------------------------------------------
// MAIN LOOP
//-----------------------------------------------------------------------------
void loop() {
    boolean cam1 = false;
    boolean cam2 = false;
    SerialParser();
    if (Command[0] == 'E') {
        if (Command[1] == '1') {cam1 = true;}
        if (Command[1] == '2') {cam2 = true;}
        if (Command[2] == '1') {cam1 = true;}
        if (Command[2] == '2') {cam2 = true;}
        String exptime_ms_string = String(Data);
        unsigned long exptime_ms = exptime_ms_string.toInt();
        float exptime_sec = exptime_ms/1000.0;
        Serial.print("EXP");
        if (cam1 == true) {Serial.print("1");}
        if (cam2 == true) {Serial.print("2");}
        Serial.print(",");
        Serial.print(exptime_ms);
        Serial.println('#');
        if (cam1 == true) {digitalWrite(camera1_pin, HIGH);}
        if (cam2 == true) {digitalWrite(camera2_pin, HIGH);}
        // Now go in to loop waiting for exposure time to finish
        // If a cancel command is received, cancel exposure.
        unsigned long total_exptime = 0;
        unsigned long remainder = exptime_ms % 100;
        unsigned long startTime = millis();
        while (total_exptime < exptime_ms - remainder) {
            delay(100);
            total_exptime = total_exptime + 100;
            Serial.println(total_exptime);
            // Look for cancel or query status commands
            SerialParser();
            if (ByteCount > 0) {
                if (Command[0] == 'Q') {
                    Serial.print("EXP");
                    if (cam1 == true) {Serial.print("1");}
                    if (cam2 == true) {Serial.print("2");}
                    Serial.println('#');
                } else if (Command[0] == 'X') {
                    cam1 = false;
                    cam2 = false;
                    digitalWrite(camera1_pin, LOW);
                    digitalWrite(camera2_pin, LOW);
                    Serial.print("EXP");
                    if (cam1 == true) {Serial.print("1");}
                    if (cam2 == true) {Serial.print("2");}
                    Serial.println('X#');
                    total_exptime = exptime_ms;
                } else {
                    Serial.println('?#');
                }
            }
        }
        delay(remainder);
        total_exptime = total_exptime + remainder;
        // Set pins low (stop exposure)
        cam1 = false;
        cam2 = false;
        digitalWrite(camera1_pin, LOW);
        digitalWrite(camera2_pin, LOW);
        unsigned long elapsed = millis() - startTime;
        Serial.println(elapsed);
    } else if (Command[0] == 'Q') {
        Serial.print("EXP");
        Serial.println('#');
    } else if (Command[0] == 'X') {
        Serial.print("EXP");
        Serial.println('#');
    } else if (Command[0] == 'T') {
        //
    } else if (Command[0] == 'O') {
        queryOrientation();
    } else if (Command[0] != ' ') {
        Serial.println('#');
    }
    Command[0] = ' ';
    Command[1] = '0';
    Command[2] = '0';
    Data[0] = '0';
    Data[1] = '0';
    Data[2] = '0';
    Data[3] = '0';
    Data[4] = '0';
    Data[5] = '0';
    Data[6] = '0';
    delay(100);
}


//-----------------------------------------------------------------------------
// Query Temperature
//-----------------------------------------------------------------------------
float queryTemperature(void) {

}


//-----------------------------------------------------------------------------
// Query Orientation
//-----------------------------------------------------------------------------
float queryOrientation(void) {
  //read the analog values from the accelerometer
  int xRead = analogRead(xPin);
  int yRead = analogRead(yPin);
  int zRead = analogRead(zPin);

  //convert read values to degrees -90 to 90 - Needed for atan2
  int xAng = map(xRead, minVal, maxVal, -90, 90);
  int yAng = map(yRead, minVal, maxVal, -90, 90);
  int zAng = map(zRead, minVal, maxVal, -90, 90);

  //Caculate 360deg values like so: atan2(-yAng, -zAng)
  //atan2 outputs the value of -π to π (radians)
  //We are then converting the radians to degrees
  x = RAD_TO_DEG * (atan2(-yAng, -zAng) + PI);
  y = RAD_TO_DEG * (atan2(-xAng, -zAng) + PI);
  z = RAD_TO_DEG * (atan2(-yAng, -xAng) + PI);

  //Output the caculations
  Serial.print("x: ");
  Serial.print(x);
  Serial.print(" | y: ");
  Serial.print(y);
  Serial.print(" | z: ");
  Serial.println(z);
}
