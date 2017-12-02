int analogValue = A2; 
//IS-2 Current sense of PROFET 2
void setup() {
pinMode(9, OUTPUT);
//DEN_1 DIAGNOSIS enable
pinMode(A2, INPUT);

pinMode(8, OUTPUT);
//OUT2_0
Serial.begin(9600);
}

void loop() {
  // put your main code here, to run repeatedly:
digitalWrite(9, HIGH);
digitalWrite(8, HIGH);

analogValue = analogRead(A2);
float voltage = analogValue * (21/ 1023.0);
//for 8 volts use 35
Serial.println(voltage);
delay(750);
}
