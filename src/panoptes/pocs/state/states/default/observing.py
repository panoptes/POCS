from panoptes.utils import error


def on_enter(event_data):
    """Take an observation image.

    This state is responsible for taking the actual observation image.
     """
    pocs = event_data.model
    pocs.say(f"🔭🔭 I'm observing {pocs.observatory.current_observation.field.field_name}! 🔭🔭")
    pocs.next_state = 'parking'

    try:
        # Do the observing.
        pocs.observatory.observe(blocking=True)
    except (error.Timeout, error.CameraNotFound):
        pocs.logger.warning("Timeout waiting for images. Something wrong with cameras, parking.")
    except Exception as e:
        pocs.logger.warning(f"Problem with imaging: {e!r}")
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        pocs.logger.debug('Finished with observing, going to analyze')
        pocs.next_state = 'analyzing'
