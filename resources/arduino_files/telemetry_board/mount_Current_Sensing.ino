const int numReadings = 30;              // sample size of readings
int readings[numReadings];               // the readings from the analog input
int readIndex = 0;                       // the index of the current reading
int total = 0;                           // the running total
int average = 0;                         // the average
int analogValue = A2;                    //IS-2 Current sense of PROFET 2

void setup() {
pinMode(9, OUTPUT);                      //DEN_1 DIAGNOSIS enable
pinMode(A2, INPUT);                      //IS-2 Current sense of PROFET 2
pinMode(8, OUTPUT);                      //OUT2_0
Serial.begin(9600);
  for (int thisReading = 0; thisReading < numReadings; thisReading++) {
    readings[thisReading] = 0;            // initialize all the readings to 0:
  }
}

void loop() {
digitalWrite(9, HIGH);                    //DEN_1 DIAGNOSIS enable
digitalWrite(8, HIGH);                    //OUT2_0
float voltage = analogRead(analogValue);  //IS-2 Current sense of PROFET 2
total = total - readings[readIndex];      // subtract the last reading:
readings[readIndex] = voltage;            // read from the sensor:
total = total + readings[readIndex];      // add the reading to the total:
readIndex = readIndex + 1;                // advance to the next position in the array:
  if (readIndex >= numReadings) {         // if we're at the end of the array...
    readIndex = 0;                        // ...wrap around to the beginning:
  }
  float average = total / numReadings;    // calculate the average:  
  Serial.println(average * (17/ 1023.0)); // send it to the computer as ASCII digits
                                          //(17/ 1023.0) converts the readings from 12 volts to current
  delay(100);                             // delay in between reads for stability
}
