import time

from pocs.utils import error

min_sleeping_interval = 0.1
waiting_msg_interval = 15

# Why is this not passed in based on the length of the current observation?
timeout = 150.


def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("I'm finding exoplanets!")
    pocs.next_state = 'parking'

    try:
        # Start the observing
        start_time = time.time()
        camera_events = pocs.observatory.observe()

        timeout_time = start_time + timeout
        next_msg_time = start_time + waiting_msg_interval
        while not all([event.is_set() for event in camera_events.values()]):
            pocs.check_messages()
            if pocs.interrupted:
                pocs.say("Observation interrupted!")
                break

            now = time.time()
            if now >= next_msg_time:
                pocs.logger.debug(
                    'Waiting for images: {} seconds elapsed'.format(round(now - start_time)))
                pocs.status()
                next_msg_time += waiting_msg_interval
                now = time.time()

            if now >= timeout_time:
                raise error.Timeout

            # Sleep until almost the time for the next message, or just
            # before the timeout time. We assume that checking the
            # camera events and messages will take a small fraction of
            # a second
            sleep_time = min(next_msg_time - now, timeout_time - now)
            sleep_time = max(min_sleeping_interval, sleep_time - min_sleeping_interval)
            time.sleep(sleep_time)

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
