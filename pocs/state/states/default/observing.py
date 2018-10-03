from pocs import utils as pocs_utils

MAX_EXTRA_TIME = 60  # seconds


def on_enter(event_data):
    """Take an observation image.

    This state is responsible for taking the actual observation image.
     """
    pocs = event_data.model
    pocs.say("I'm finding exoplanets!")
    pocs.next_state = 'parking'

    try:
        maximum_duration = pocs.observatory.current_observation.exp_time.value + MAX_EXTRA_TIME

        # Start the observing.
        camera_events_info = pocs.observatory.observe()
        camera_events = list(camera_events_info.values())
        pocs.wait_for_events(camera_events, maximum_duration, event_type='observing')

    except pocs_utils.error.Timeout:
        pocs.logger.warning(
            "Timeout while waiting for images. Something wrong with camera, going to park.")
    except Exception as e:
        pocs.logger.warning("Problem with imaging: {}".format(e))
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        pocs.logger.debug('Finished with observing, going to analyze')

        pocs.next_state = 'analyzing'
