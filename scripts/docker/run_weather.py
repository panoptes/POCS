#!/usr/bin/env python3

from peas.weather import AAGCloudSensor

from pocs.utils.config import load_config
from pocs.utils import CountdownTimer
from pocs.utils import error


def main(config, loop_delay=60):
    try:
        try:
            port = config['weather']['aag_cloud']['serial_port']
        except KeyError:
            port = '/dev/ttyUSB0'
        print("Loading AAG Cloud Sensor on {}".format(port))
        weather = AAGCloudSensor(serial_address=port, store_result=True)
        if weather.AAG is None:
            print(f'AAG not set up properly, check port')
            return
        print("Weather station set up")
    except error.PanError as e:
        print('Problem setting up PEAS: {}'.format(e))

    timer = CountdownTimer(loop_delay)

    # Loop forever.
    print(f'Starting weather station loop with {loop_delay}s delay')
    while True:
        timer.restart()
        weather.capture(store_result=True, send_message=True)

        timer.sleep()

        # TODO: listen for messages and react to them


if __name__ == '__main__':
    config = load_config('peas')
    main(config)
