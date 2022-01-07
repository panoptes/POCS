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
        # Do the observing, once per exptime (usually only one unless a compound observation).
        for _ in current_obs.exptimes:
            pocs.observatory.observe(blocking=True)
            pocs.say(f"Finished observing! I'll start processing that in the background.")

            # Do processing in background.
            process_proc = Process(target=pocs.observatory.process_observation)
            process_proc.start()
            pocs.logger.debug(f'Processing for {current_obs} started on {process_proc.pid=}')
    except (error.Timeout, error.CameraNotFound):
        pocs.logger.warning("Timeout waiting for images. Something wrong with cameras, parking.")
    except Exception as e:
        pocs.logger.warning(f"Problem with imaging: {e!r}")
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        pocs.logger.debug('Finished with observing, going to analyze')
        pocs.next_state = 'analyzing'
