from astropy.coordinates import get_sun

from pocs.utils import current_time


def on_enter(event_data):
    """Pointing State
    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:

        if pocs.observatory.take_flat_fields:
            flat_horizon = pocs.config['location']['flat_horizon'].value
            observe_horizon = pocs.config['location']['observe_horizon'].value

            # Wait for twilight if needed
            sun_pos = pocs.observatory.observer.altaz(
                current_time(),
                target=get_sun(current_time())
            ).alt

            # Take the flats
            if sun_pos.value <= flat_horizon and sun_pos.value > observe_horizon:
                pocs.say("Taking some flat fields to start the night")
                pocs.observatory.take_evening_flats(initial_exptime=5, max_exptime=150)
            elif sun_pos.value <= observe_horizon:
                pocs.say("Sun is below {} - end of calibration".format(observe_horizon))

        pocs.next_state = 'scheduling'

    except Exception as e:
        pocs.logger.warning("Problem with flat-fielding: {}".format(e))
