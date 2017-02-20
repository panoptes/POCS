from astropy.coordinates import get_sun

from pocs.utils import current_time


def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:

        if pocs.take_evening_flats:

            sun_pos = pocs.observatory.observer.altaz(current_time(), target=get_sun(current_time())).alt

            if sun_pos <= 0 and sun_pos >= -18:
                pocs.say("Taking some flat fields to start the night")
                pocs.observatory.take_evening_flats()

        pocs.next_state = 'scheduling'

    except Exception as e:
        pocs.logger.warning("Problem with flat-fielding: {}".format(e))
