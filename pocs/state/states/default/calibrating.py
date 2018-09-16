from pocs.utils import current_time


def on_enter(event_data):
    """Calibrating State
    Take flat-field frames for the evening.
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:

        pocs.say("Let's take some flat fields!")

        flat_horizon = pocs.config['location']['flat_horizon'].value
        observe_horizon = pocs.config['location']['observe_horizon'].value

        # Wait for twilight if needed
        sun_pos = pocs.observatory.observer.sun_altaz(current_time()).alt.value

        # Take the flats
        if sun_pos <= flat_horizon and sun_pos > observe_horizon:
            pocs.say("Taking some flat fields to start the night")
            pocs.observatory.take_evening_flats(initial_exptime=5)
        elif sun_pos <= observe_horizon:
            pocs.say("Sun is below {} - end of calibration".format(observe_horizon))

        pocs.next_state = 'scheduling'

    except Exception as e:
        pocs.logger.warning("Problem with flat-fielding: {}".format(e))
