from time import sleep

wait_interval = 15.


def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:
        pocs.say("Let's focus the cameras!")
        camera_events = pocs.observatory.autofocus_cameras()

        wait_time = 0.
        while not all([event.is_set() for event in camera_events.values()]):
            pocs.check_messages()
            if pocs.interrupted:
                pocs.say("Observation interrupted!")
                break

            pocs.logger.debug('Waiting for images: {} seconds'.format(wait_time))
            pocs.status()

            sleep(wait_interval)
            wait_time += wait_interval

        pocs.next_state = 'observing'

    except Exception as e:
        pocs.logger.warning("Problem with focusing: {}".format(e))
