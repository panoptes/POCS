#!/usr/bin/env python3
import os
import sys
from subprocess import Popen, PIPE
import fcntl
import serial
import time

from pocs.mount import create_mount_from_config
from panoptes.utils.error import MountNotFound

from panoptes.utils.config.client import set_config

from peas.sensors import detect_board_on_port

BASEDIR = 'cd /sys/devices/pci0000:00'
DataStorageMatrix = []
TemporaryDataStorageList = []

# Utility function for Arduino automatic uploading


def ArduinoAutoUpload(board_type, usb_port):
    if (board_type == "camera board"):
        sketch_name = "camera_board"
    if (board_type == "control board"):
        sketch_name = "power_board"
    while True:
        response = input(
            f'Automatically upload the Arduino sketch for the {board_type} Arduino ({sketch_name}.ino) [y/n]?')
        if response.lower().startswith('y'):
            print("Uploading sketch...")
            os.chdir('/var/panoptes/POCS/resources/arduino_files')
            os.system(f'arduino-cli upload -p {usb_port} --fqbn {fqbn} {sketch_name}')
            print('\033[1;32;40mSketch uploaded.\033[1;37;40m')
            break
        elif response.lower().startswith('n'):
            print("Exiting, continuing with next upload if necessary.")
            break
        else:
            print("A 'yes' or 'no' response is required")


# Finding dev path and relating it to bus number and dev number
StartLocationProbe = BASEDIR + ' ; find -maxdepth 2 -name "usb*"'
StartLocation = Popen(
    StartLocationProbe,
    shell=True,
    bufsize=64,
    stdin=PIPE,
    stdout=PIPE,
    close_fds=True).stdout.read().strip().decode('utf-8').split('\n')
NumStartLocation = len(StartLocation)
x = NumStartLocation
while x > 0:
    StartLocationIndex = NumStartLocation - x
    NEWBASEDIR = BASEDIR + ' ; cd ' + StartLocation[StartLocationIndex]
    SearchLocationProbe = NEWBASEDIR + ' ; find . -name "*-*:*"'
    SearchLocations = Popen(
        SearchLocationProbe,
        shell=True,
        bufsize=64,
        stdin=PIPE,
        stdout=PIPE,
        close_fds=True).stdout.read().strip().decode('utf-8').split('\n')
    Num_Searches = len(SearchLocations)
    i = Num_Searches
    while i > 0:
        CurrentIndex = Num_Searches - i
        SearchLocation = NEWBASEDIR + ' ; cd ' + SearchLocations[CurrentIndex]
        DevPathProbe = SearchLocation + ' ; find -maxdepth 2 ! -name "tty"  -name "tty*"'
        DEVPATH = Popen(
            DevPathProbe,
            shell=True,
            bufsize=64,
            stdin=PIPE,
            stdout=PIPE,
            close_fds=True).stdout.read().strip().decode('utf-8')
        if (DEVPATH == ""):
            i -= 1
            continue
        if (DEVPATH.startswith("./tty/")):
            PARSEDDEVPATH = DEVPATH.split("./tty/")
            PARSEDDEVPATH.remove("")
        if (DEVPATH != ""):
            if (DEVPATH.startswith("./tty/")):
                PARSEDDEVPATH = DEVPATH.split("./tty/")
            elif (DEVPATH.startswith("./tty")):
                PARSEDDEVPATH = DEVPATH.split("./")
        PARSEDDEVPATH.remove("")
        BUSNUMDEVNUMPROBE = SearchLocation + ' ; cd .. ; echo -n "Bus: " ; cat busnum ; echo -n " Device: " ; cat devnum ; echo -n " ID " ; cat idVendor ; echo -n ":" ; cat idProduct ; echo -n " " ; cat manufacturer ; echo -n ", " ; cat product'
        BUSNUMDEVNUM = Popen(
            BUSNUMDEVNUMPROBE,
            shell=True,
            bufsize=64,
            stdin=PIPE,
            stdout=PIPE,
            close_fds=True).stdout.read().strip().decode('utf-8')
        TemporaryDataStorageList = BUSNUMDEVNUM.split("\n")
        TemporaryDataStorageList.insert(0, PARSEDDEVPATH[0])
        TemporaryDataStorageList.insert(1, " ")
        TemporaryDataStorageList.insert(0, "Dev path: \033[1;32;40m/dev/")
        TemporaryDataStorageList.insert(2, "\033[1;37;40m")
        DataStorageMatrix.append(TemporaryDataStorageList)
        i -= 1
    x -= 1
# Print out that parsed info!
for x in DataStorageMatrix:
    print("")
    for y in x:
        print(y, end='')
print("")

DevPaths = []
DataStorageMatrixLength = len(DataStorageMatrix)
k = DataStorageMatrixLength
while k > 0:
    DataSet = DataStorageMatrixLength - k
    if (DataStorageMatrix[DataSet][1].startswith("ttyUSB")):
        DevPaths.append(DataStorageMatrix[DataSet][1])
    k -= 1

# Identify Mount
for port in DevPaths:
    usb_port = f'/dev/{port}'
    set_config('mount.serial.port', usb_port)
    mount_info = {
        'driver': 'ioptron',
        'serial': {
            'port': usb_port
        }
    }

    mount = create_mount_from_config(mount_info=mount_info)

    try:
        mount.initialize()
    except MountNotFound:
        continue

    print(f'\033[1;32;40mFound mount on {usb_port}, saving to config\033[1;37;40m')
    set_config('mount.serial.port', usb_port)
    break

# Identify Weather Sensor
print("Looking for AAG weather sensor. Process could take up to 8 minutes")
for port in DevPaths:
    usb_port = f'/dev/{port}'
    print(f'Testing port {usb_port}.')
    Input = ""
    ser = serial.Serial(usb_port, 9600, timeout=3)
    i = 0
    PreviousInput = False
    end_time = time.time() + 60
    while i < 10:
        bytesToRead = ser.inWaiting()
        info = ser.read(bytesToRead)
        info = info.decode('utf-8')
        Input = Input + info
        if (len(Input) > 1000):
            if ("CloudWatcher!" in Input):
                print(f'\033[1;32;40mFound weather sensor on {usb_port}, saving to config\033[1;37;40m')
                print(usb_port)
                set_config('weather.aag_cloud.serial_port', usb_port)
                ser.close()
                i += 1
                break
            Input = ""
        info = ''
        if (time.time() >= end_time and PreviousInput is False):
            print("Testing if there is any input information.")
            if (Input == ""):
                print(f'Weather sensor not found on {usb_port}.')
                print(f'Input: {Input}')
                ser.close()
                break
            print("Input found. Verifying weather sensor.")
            PreviousInput = True
    else:
        continue
    break

# Identify Arduinos
# Isolate Arduino device paths
k = DataStorageMatrixLength
DevPaths.clear()
while k > 0:
    DataSet = DataStorageMatrixLength - k
    if (DataStorageMatrix[DataSet][1].startswith("ttyACM")):
        DevPaths.append(DataStorageMatrix[DataSet][1])
    k -= 1

# Setup arduino-cli commands for this docker image
os.system("arduino-cli core update-index")
fqbn_raw = os.popen("arduino-cli board list | awk '{ print $7 }'").read()
fqbn = fqbn_raw.split('\n')[1]
fqbnCoreElements = fqbn.split(":")
fqbnCore = fqbnCoreElements[0] + ":" + fqbnCoreElements[1]
os.system(f'arduino-cli core install {fqbnCore}')
# Switch to the arduino_files directory to have the sketch compile and
# upload properly
os.chdir('/var/panoptes/POCS/resources/arduino_files')

print("Compiling sketches...")
# Setup required .hex and .elf arduino-cli files for all sketches
SketchPaths = ["identifier", "camera_board", "power_board"]
for path in SketchPaths:
    os.system(f'arduino-cli compile --fqbn {fqbn} {path}')
print("Done. Testing for Micro setup and then moving on to upload to identify Arduinos if necessary.")

Board_Types = os.popen("arduino-cli board list").read().split('\n')
Board_Types.pop(0)
Board_Types.pop(-1)
Board_Types.pop(-1)
Num_Types = len(Board_Types)

# Check to make sure that the build is using only two Arduinos
# to avoid damaging custom hardware or future builds
if (Num_Types > 2):
    print("\033[31mMore than two Arduinos attached to NUC. Script can damage custom hardware and only supports builds using a two Arduino setup with one as the camera board and one as the control board. Exiting.\033[0m")
    sys.exit()

# Test for Mirco - Uno setup and prompt user to upload sketches

ArduinoInfoStorage = []
i = Num_Types
while i > 0:
    Index = Num_Types - i
    ArduinoInfoStorage.append(Board_Types[Index].split(' '))
    i -= 1
for i in ArduinoInfoStorage:
    for x in i:
        if ("Micro" in x):
            print(f'\033[1;32;40mMicro detected on {i[0]}. Assuming this is camera board. Saving to config.\033[1;37;40m')
            set_config("environment.control_board.serial_port", i[0])
            ArduinoAutoUpload("camera board", i[0])
            print("Searching for Arduino Uno. Assuming it is the control board.\033[1;37;40m")
            for y in ArduinoInfoStorage:
                for z in y:
                    if ("Uno" in z):
                        print(f'\033[1;32;40mUno found at {y[0]}. Saving to config.\033[1;37;40m')
                        set_config("environment.camera_board.serial_port", y[0])
                        ArduinoAutoUpload("control board", y[0])
            sys.exit()

# Test for Uno - Uno setup. If found, identify boards, upadte config, prompt sketch upload
Number_Arduino_Uno = 0
Number_Arduino_Micro = 0
for i in Board_Types:
    if ("Uno" in i):
        Number_Arduino_Uno +=1
    elif ("Micro" in i):
	    Number_Arduino_Micro +=1

if (Number_Arduino_Uno is 2):
    print("Double Arduino Uno setup detected. Using identifier sketch to differentiate identical devices.")
elif (Number_Arduino_Micro is 2):
    print("Double Arduino Micro setup detected. Build is currently not supported with this script. Skipping the Arduino identification process.")
    print("Exiting.")
    sys.exit()
else:
    print("\033[31Setup of unit is incomplete or unsupported. If only one Arduino board is connected, continue to auto-identify and configure it.\033[0m")
    while True:
        response = input("Continue?[y/n]")
        if response.lower().startswith('y'):
            break
        elif response.lower().startswith('n'):
            sys.exit()

# Upload identifier sketch and test output
for port in DevPaths:
    usb_port = f'/dev/{port}'
    print(f'Uploading identifier Arduino sketch to {usb_port}.')
    os.system(f'arduino-cli upload -p {usb_port} --fqbn {fqbn} identifier')
    print(f'Sketch uploaded to Arduino on {usb_port}')

    # Get and parse serial output
    with serial.Serial(usb_port, 9600, timeout=3) as ser:
        time.sleep(10)
        # 53 chars since one full temp data is 27, 53 ensures full capture of
        # at least one full temp report
        identifier_output = ser.read(53)
        identifier_output = identifier_output.decode("utf-8")
    serial_lines = identifier_output.split('\n')
    for line in serial_lines:
        if(len(line) > 26):
            full_reading = line
            break
    if (full_reading == '"temps":[-127.00,-127.00,-127.00]'):
        print(f'\033[1;32;40mFound camera_board Arduino on {usb_port}, saving to config.\033[1;37;40m')
        set_config('environment.camera_board.serial_port', usb_port)
        ArduinoAutoUpload("camera board", usb_port)
    elif (full_reading != '"temps":[-127.00,-127.00,-127.00]'):
        print(f'\033[1;32;40mFound power_board Arduino on {usb_port}, saving to config.\033[1;37;40m')
        set_config('environment.control_board.serial_port', usb_port)
        ArduinoAutoUpload("control board", usb_port)
