from pocs.utils import current_time


def on_enter(event_data):
    """Calibrating State
    Take flat-field frames for the evening.
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:
        pocs.say("Let's take some flat fields!")
        pocs.next_state = 'scheduling'

        # Take the flats
        if pocs.observatory.should_take_flats(which='evening'):
            if pocs.observatory.is_dark(horizon='flat') is False:
                pocs.say("Not dark enough for flats yet, goingn to wait a little while.")
                pocs.wait_until_dark(horizon='flat')

            pocs.say("Taking some flat fields to start the night")
            pocs.observatory.take_evening_flats(initial_exptime=5)
        else:
            pocs.say("Checking if it's dark enough to observe")
            pocs.wait_until_dark(horizon='observe')

    except Exception as e:
        pocs.logger.warning("Problem with flat-fielding: {}".format(e))
