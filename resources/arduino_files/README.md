# Arduino Files

The arduino files in this folder are meant to support various iterations or
different configurations. Some are here for legacy purposes.

In general, you should only need two different files: one for the electronics
inside the camera box, and one for the electronics inside the control box.


## Current Versions

### Camera Box

The camera box has a few functions which the electronics support:

* Relays for the two cameras.
* Environmental sensors:
    * Accelerometer
    * DHT22 temperature/humidity

#### camera_board

Currently the only version of the camera board electronics. There might have been
various updates to this file so if it is not working check the instructions to make
sure you have the latest files for the latest design of the camera_board.

### Control Box

The electronics in the control box have undergone various iterations. Listed below
are the various iterations and some desription of which version of the hardware
they should be used with. Note that each type of board might also have updates to
to it, but in general the latest board should always be used.

The main functions of the control box are:

* Relays:
    * Camera box
    * Mount
    * Control computer (NUC)
    * Weather Station
    * Fan
* AC main power sensing (depending on attached hardware)
* Current sensing for relay channels (depending on iteration)
* Environmental sensors:
    * DHT22 temperature/humidity
    * 3x DS18B20 temperature

#### control_board

Supports the custom PCB board with either an Arduino Uno or Arduino Micro.

#### infineon_board

Support just the Infineon 24V board with an attached Arduino Uno. This is the version
used by PAN008 and is a simplified verson of the `control_board` above. It does
*not* use the custom PCB that is specified in the instructions as of 2019-07-01.

#### telemetry_board

The first version (V0) of the custom PCB board for use with the Infineon and an
Arduino Uno. In general this version should not be used unless you have specifically
been told it is what you need.

#### power_board

Mostly the same as the `telemetry_board`. Mostly here for legacy purposes and should
not be used unless you know you need it.

## Using the Arduino files

In general you want to follow the steps outlined in the [`arduino-cli` instructions](https://github.com/arduino/arduino-cli).

### Adding 3rd party libraries

The instructions listed above show how to add libraries. Not all of the iterations
listed above use all the libraries but it doesn't hurt to have them on your machine.

```
Name                    Installed       Location
Adafruit_Unified_Sensor 1.0.3           sketchbook
ArduinoJson             6.11.1          sketchbook
DHT_sensor_library      1.3.4           sketchbook
DallasTemperature       3.8.0           sketchbook
OneWire                 2.3.4           sketchbook
```

These can be installed with:

```bash
arduino-cli lib install "Adafruit Unified Sensor"
arduino-cli lib install "ArduinoJson"
arduino-cli lib install "DHT sensor library"
arduino-cli lib install "DallasTemperature"
arduino-cli lib install "OneWire"
```

> Note: if you already have the library installed the above commands will show an
error message, saying that the file alredy exists and cannot be installed. This is
not really an "error" and can be ignored.


### Compiling the sketch

Using the `arduino-cli` command line tool, the sketch can be compiled using the
command:

```bash
arduino-cli compile --fqbn arduino:avr:uno <FOLDER_NAME>
```

Where `<FOLDER_NAME>` corresponds to the folder containing the `.ino` file.  The
`--fqbn` option depends on the specific Arduino you are using. See [Step 4](https://github.com/arduino/arduino-cli#step-4-find-and-install-the-right-core)
of the `arduino-cli` instructions for more information.

Example:

```bash
arduino-cli compile --fqbn arduino:avr:uno control_board
```

### Uploading the sketch

To upload the sketch you can use the following:

```bash
arduino-cli upload -p <PORT> --fqbn arduino:avr:uno control_board && sleep 2 && stty -F <PORT> -hupcl
```

Where `<PORT>` can be identified by `arduino-cli board list`.

The `stty` command at the end will disable disable the auto-reset of the Arduino
so that serial connections don't cause the board to reset itself. The `arduino-cli`
command toggles the DTR setting because it is needed in order to upload the sketch
correctly.

Example:

```bash
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno control_board && sleep 2 && stty -F /dev/ttyACM0 -hupcl
```

## Tools

### arduino-cli

The `arduino-cli` command is easily installed on Ubuntu and might already be present
on your system. You can test if available with:

```bash
arduino-cli --version
```

If not available, follow the instructions at: https://github.com/arduino/arduino-cli.

### Arduino Web IDE

There is an online version of the Arduino IDE that is often easier than installing
the desktop software. See: https://create.arduino.cc/.
