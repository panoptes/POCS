#!/usr/bin/env python3

from peas.sensors import ArduinoSerialMonitor

from pocs.utils.config import load_config
from pocs.utils import CountdownTimer
from pocs.utils import error


def main(config, loop_delay=5):
    try:
        print("Loading Arduino Serial Monitor")
        environment = ArduinoSerialMonitor(auto_detect=True)
        if environment is None:
            print(f'Arduino Serial Monitor not set up properly, check ports')
            return
        print("Environmental sensors set up")
    except error.PanError as e:
        print('Problem setting up Arduino serial montiors: {}'.format(e))

    timer = CountdownTimer(loop_delay)

    # Loop forever.
    print(f'Starting environmental sensors loop with {loop_delay}s delay')
    while True:
        timer.restart()
        environment.capture(store_result=True, send_message=True)

        timer.sleep()

        # TODO: listen for messages and react to them


if __name__ == '__main__':
    config = load_config('peas')
    main(config)
