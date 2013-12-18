/*
Canon DSLR Camera Control

To activate cameras send a serial tring to the board.  The string should 
consist of three integers.  The first and second indicate which cameras
should be activated.  Any non-zero, positive integer in the first field
will activate the first camera and any non-zero integer in the second
field will activate the second camera.  The third value is the exposure
time in milliseconds.

Serial Commands to Board:
E,n,n,nnn -- Expose camera.
C,n,n     -- Cancel exposure.
Q         -- Query which cameras are exposing.
*/

// Constants for Camera Relay
const int camera1_pin = 2;
const int camera2_pin = 3;

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
    // if there's any serial available, read it:
    while (Serial.available() > 0) {
        int command = Serial.parseInt();
        // Based on the command, parse the rest of the serial string differently.
        if (command == 69) {
            // Expose (E=69) command
            int camera1 = Serial.parseInt();
            int camera2 = Serial.parseInt();
            int exptime_ms = Serial.parseInt();
            // look for the newline. That's the end of your
            // sentence:
            if (Serial.read() == '\n') {
                // expose camera for exptime_ms milliseconds
                Serial.print("Starting ");
                Serial.print(exptime_ms/1000.0);
                Serial.print(" second exposure");
                if (camera1 >= 1) {
                    Serial.print(" on camera1 ");
                    digitalWrite(camera1_pin, HIGH);
                    if (camera2 >= 1) { Serial.print("and"); }
                }
                if (camera2 >= 1) {
                    Serial.print(" on camera2 ");
                    digitalWrite(camera2_pin, HIGH);
                }
                Serial.print("... ");
                // Now go in to loop waiting for exposure time to finish
                // If a cancel command is received, cancel exposure.
                int total_exptime = 0
                int remainder = total_exptime % 100;
                int n_loops = (total_exptime - remainder) / 100;
                for (int index = 0; index < n_loops; index++) {
                    delay(100);
                    total_exptime = total_exptime + 100;
                    // Look for cancel command
                }
                delay(remainder);
                // Set pins low (stop exposure)
                digitalWrite(camera1_pin, LOW);
                digitalWrite(camera2_pin, LOW);
                Serial.println("done");
            }
        }
        if (command == 67) or (command == 81) {
        // Cancel (C=67) or Query (Q=81) command
        }
    }
    delay(100);
}

