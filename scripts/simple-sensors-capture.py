import time
from bson import json_util

from peas.sensors import ArduinoSerialMonitor


def main(loop=True, delay=1., filename=None, send_message=True, verbose=False):
    # Weather object
    monitor = ArduinoSerialMonitor(auto_detect=False)

    if filename is not None:
        with open(filename, 'a') as f:

            while True:
                try:
                    data = monitor.capture(send_message=send_message)

                    if len(data.keys()) > 0:
                        f.write(json_util.dumps(data) + '\n')
                        f.flush()

                        if verbose:
                            print(data)

                    if not args.loop:
                        break

                    time.sleep(delay)
                except KeyboardInterrupt:
                    break
                finally:
                    f.flush()


if __name__ == '__main__':
    import argparse

    # Get the command line option
    parser = argparse.ArgumentParser(description="Read sensor data from arduinos")

    parser.add_argument('--loop', action='store_true', default=True,
                        help="If should keep reading, defaults to True")
    parser.add_argument("-d", "--delay", dest="delay", default=1.0, type=float,
                        help="Interval to read sensors")
    parser.add_argument("--send-message", dest="send_message", default=False, action='store_true',
                        help="Send zmq message")
    parser.add_argument("--filename", default="simple_sensor_capture.json",
                        help="Filename to store json output")
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help="Print results to stdout")
    args = parser.parse_args()

    main(**vars(args))
