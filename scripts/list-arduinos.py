#!/usr/bin/env python3

import sys

from panoptes.pocs.sensors import arduino_io
from panoptes.utils import rs232


# Support testing by just listing the available devices.
if __name__ == '__main__':
    port_infos = rs232.get_serial_port_info()
    if port_infos:
        fmt = '{:20s} {:30s} {}'
        print(fmt.format('Device', 'Manufacturer', 'Description'))
        for pi in port_infos:
            print(fmt.format(pi.device, pi.manufacturer, pi.description))
        print()
    devices = arduino_io.get_arduino_ports()
    if devices:
        print("Arduino devices: {}".format(", ".join(devices)))
    else:
        print("No Arduino devices found.")
        sys.exit(1)

    print()
    boards_and_ports = arduino_io.auto_detect_arduino_devices()
    for board, port in boards_and_ports:
        print('Found board {!r} on port {!r}'.format(board, port))
    sys.exit(0)
