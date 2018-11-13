
def on_enter(event_data):
    """Calibrating State
    Take flat-field frames for the evening.
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:

        # Take the flats
        if pocs.observatory.should_take_flats(which='evening'):
            pocs.say("Taking some flat fields to start the night")
            pocs.observatory.take_flat_fields(which='evening', initial_exptime=5)
            pocs.say("Done taking flat fields.")
    except Exception as e:
        pocs.logger.warning("Problem with flat-fielding: {}".format(e))

    try:
        # Wait until dark enough to observe (will send to Home)
        pocs.say("Checking if it's dark enough to observe")
        pocs.wait_until_dark(horizon='observe', wait_position='home')
        pocs.next_state = 'scheduling'
    except Exception as e:
        pocs.logger.warning("Problem waiting until darks: {}".format(e))
