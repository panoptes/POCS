from astropy import units as u
import time

from pocs import utils as pocs_utils

SLEEP_SECONDS = 1.0
STATUS_INTERVAL = 10. * u.second
WAITING_MSG_INTERVAL = 30. * u.second
MAX_EXTRA_TIME = 60 * u.second


def on_enter(event_data):
    """Wait for camera exposures to complete.

    Frequently check for the exposures to complete, the observation to be
    interrupted, messages to be received. Periodically post to the STATUS
    channel and to the debug log.
     """
    pocs = event_data.model
    pocs.say("I'm finding exoplanets!")
    pocs.next_state = 'parking'

    try:
        maximum_duration = pocs.observatory.current_observation.exp_time + MAX_EXTRA_TIME

        # Start the observing.
        start_time = pocs_utils.current_time()
        camera_events = pocs.observatory.observe()

        timeout = pocs_utils.Timeout(maximum_duration)
        next_status_time = start_time + STATUS_INTERVAL
        next_msg_time = start_time + WAITING_MSG_INTERVAL
        while not all([event.is_set() for event in camera_events.values()]):
            pocs.check_messages()
            if pocs.interrupted:
                pocs.say("Observation interrupted!")
                break

            now = pocs_utils.current_time()
            if now >= next_msg_time:
                elapsed_secs = (now - start_time).to(u.second).value
                pocs.logger.debug(
                    'Waiting for images: {} seconds elapsed'.format(round(elapsed_secs)))
                next_msg_time += WAITING_MSG_INTERVAL
                now = pocs_utils.current_time()

            if now >= next_status_time:
                pocs.status()
                next_status_time += STATUS_INTERVAL
                now = pocs_utils.current_time()

            if timeout.expired():
                raise pocs_utils.error.Timeout

            # Sleep for a little bit.
            time.sleep(SLEEP_SECONDS)

    except pocs_utils.error.Timeout:
        pocs.logger.warning(
            "Timeout while waiting for images. Something wrong with camera, going to park.")
    except Exception as e:
        pocs.logger.warning("Problem with imaging: {}".format(e))
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        pocs.observatory.current_observation.current_exp += 1
        pocs.logger.debug('Finished with observing, going to analyze')

        pocs.next_state = 'analyzing'
