from pocs.utils import error
from time import sleep

wait_interval = 15.
timeout = 150.


def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("I'm finding exoplanets!")
    pocs.next_state = 'parking'

    try:
        # Start the observing
        camera_events = pocs.observatory.observe()

        wait_time = 0.
        while not all([event.is_set() for event in camera_events.values()]):
            pocs.check_messages()
            if pocs.interrupted:
                pocs.say("Observation interrupted!")
                break

            pocs.logger.debug('Waiting for images: {} seconds'.format(wait_time))
            pocs.status()

            if wait_interval > timeout:
                raise error.Timeout

            sleep(wait_interval)
            wait_time += wait_interval

    except error.Timeout as e:
        pocs.logger.warning(
            "Timeout while waiting for images. Something wrong with camera, going to park.")
    except Exception as e:
        pocs.logger.warning("Problem with imaging: {}".format(e))
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        pocs.observatory.current_observation.current_exp += 1
        pocs.logger.debug('Finished with observing, going to analyze')

        pocs.next_state = 'analyzing'
