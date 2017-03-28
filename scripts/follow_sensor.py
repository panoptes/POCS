#!/usr/bin/env python

from peas.sensors import ArduinoSerialMonitor


def main(sensor=None, watch_key=None, **kwargs):
    monitor = ArduinoSerialMonitor()

    while True:
        try:
            data = monitor.capture(use_mongo=False)[sensor]
        except KeyError:
            continue
        else:
            if watch_key in data:
                print(data[watch_key])
            else:
                print(data)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Follow some serial keys.")

    parser.add_argument('sensor', help="Sensor to watch")
    parser.add_argument('--watch-key', default=None, help="Key to watch, e.g. amps")

    args = parser.parse_args()

    try:
        main(**vars(args))
    except KeyboardInterrupt:
        print("Stopping...")
