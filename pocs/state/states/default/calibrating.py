def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:
        pocs.say("Taking some flat fields to start the night")

        if pocs.take_evening_flats:
            pocs.observatory.take_evening_flats()

        pocs.next_state = 'scheduling'

    except Exception as e:
        pocs.logger.warning("Problem with flat-fielding: {}".format(e))
