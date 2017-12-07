import time

from peas.sensors import ArduinoSerialMonitor


def main(loop=True, delay=1., verbose=False):
    # Weather object
    monitor = ArduinoSerialMonitor(auto_detect=False)

    while True:
        data = monitor.capture()

        if verbose and len(data.keys()) > 0:
            print(data)

        if not args.loop:
            break

        time.sleep(args.delay)


if __name__ == '__main__':
    import argparse

    # Get the command line option
    parser = argparse.ArgumentParser(description="Read sensor data from arduinos")

    parser.add_argument('--loop', action='store_true', default=True,
                        help="If should keep reading, defaults to True")
    parser.add_argument("-d", "--delay", dest="delay", default=1.0, type=float,
                        help="Interval to read sensors")
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help="Print results to stdout")
    args = parser.parse_args()

    main(**vars(args))
