from panoptes.utils import error
from panoptes.utils.time import wait_for_events

MAX_EXTRA_TIME = 60  # seconds


def on_enter(event_data):
    """Take an observation image.

    This state is responsible for taking the actual observation image.
     """
    pocs = event_data.model
    pocs.say(f"🔭🔭🔭 I'm observing {pocs.observatory.current_observation.field.field_name}! 🔭🔭🔭")
    pocs.next_state = 'parking'

    try:
        maximum_duration = pocs.observatory.current_observation.exptime.value + MAX_EXTRA_TIME

        # Start the observing.
        camera_events_info = pocs.observatory.observe()
        camera_events = list(camera_events_info.values())

        def waiting_cb():
            pocs.logger.info(f'Waiting on an observation.')

        wait_for_events(camera_events, timeout=maximum_duration, callback=waiting_cb, sleep_delay=11)

    except error.Timeout:
        pocs.logger.warning("Timeout waiting for images. Something wrong with camera, parking.")
    except Exception as e:
        pocs.logger.warning(f"Problem with imaging: {e!r}")
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        pocs.logger.debug('Finished with observing, going to analyze')
        pocs.next_state = 'analyzing'
