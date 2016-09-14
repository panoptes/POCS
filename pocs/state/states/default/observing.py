from ....utils import error


def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("I'm finding exoplanets!")

    observation_success = False

    # Temp for bad cameras
    max_tries = 10
    num_tries = 0

    try:
        # Block on observing
        observation_success = pocs.observatory.observe()
    except error.Timeout as e:
        pocs.logger.warning("Timeout while waiting for images. Something wrong with camera, going to park.")
    except Exception as e:
        pocs.logger.warning("Problem with imaging: {}".format(e))
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        if observation_success:
            pocs.next_state = 'analyzing'
        else:
            if num_tries < max_tries:
                pocs.next_state = 'observing'
                num_tries += 1
                pocs.logger.debug("Trying to observe again: {} of {}".format(num_tries, max_tries))
            else:
                pocs.logger.warning("Can't seem to observe, parking")
                pocs.next_state = 'parking'
