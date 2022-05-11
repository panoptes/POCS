from multiprocessing import Process

from panoptes.utils import error


def on_enter(event_data):
    """Take an observation image.

    This state is responsible for taking the actual observation image.
     """
    pocs = event_data.model
    current_obs = pocs.observatory.current_observation
    pocs.say(f"🔭🔭 I'm observing {current_obs.field.field_name}! 🔭🔭")
    pocs.next_state = 'parking'

    try:
        pocs.observe_target()
    except (error.Timeout, error.CameraNotFound):
        pocs.logger.warning("Timeout waiting for images. Something wrong with cameras, parking.")
    except Exception as e:
        pocs.logger.warning(f"Problem with imaging: {e!r}")
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        pocs.logger.debug('Finished with observing, going to scheduling')
        pocs.next_state = 'scheduling'
