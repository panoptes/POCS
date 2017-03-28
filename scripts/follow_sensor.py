#!/usr/bin/env python

from peas.sensors import ArduinoSerialMonitor


def main(watch_key=None, **kwargs):
    monitor = ArduinoSerialMonitor()

    keys = watch_key.split('.')

    while True:
        data = monitor.capture(use_mongo=False)
        for key in keys:
            try:
                data = data[key]
            except KeyError:
                break

        print(data)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Follow some serial keys.")

    parser.add_argument('watch_key', help="Key to watch with dot separation, e.g. telemetry_board.amps")

    args = parser.parse_args()

    try:
        main(**vars(args))
    except KeyboardInterrupt:
        print("Stopping...")
