# Arduino Files

The arduino files in this folder are meant to support various iterations or
different configurations. Some are here for legacy purposes.

In general, you should only need two different files: one for the electronics
inside the camera box, and one for the electronics inside the control box.

### Compiling the sketch

Using the `arduino-cli` command line tool, the sketch can be compiled using the
command:

```bash
arduino-cli compile --fqbn arduino:avr:uno <FOLDER_NAME>
```

Where `<FOLDER_NAME>` corresponds to the folder containing the `.ino` file.  The
`--fqbn` option depends on the specific Arduino you are using. See [Step 4](https://github.com/arduino/arduino-cli#step-4-find-and-install-the-right-core)
of the `arduino-cli` instructions for more information.

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

A fulle example would be:

```bash
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno control_board && sleep 2 && stty -F /dev/ttyACM0 -hupcl
```

### Tools

#### arduino-cli

The `arduino-cli` command is easily installed on Ubuntu and might already be present
on your system. You can test if available with:

```bash
arduino-cli --version
```

If not available, follow the instructions at: https://github.com/arduino/arduino-cli.

#### Arduino Web IDE

There is an online version of the Arduino IDE that is often easier than installing
the desktop software. See: https://create.arduino.cc/.
