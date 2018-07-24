from astropy.coordinates import get_sun

from pocs.utils import current_time


def on_enter(event_data):
    """Pointing State
    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'


    twilight_horizon = pocs.config['location']['twilight_horizon']
    try:
        twilight_horizon = twilight_horizon.value
    except AttributeError:
        pass

    try:

        if pocs.observatory.take_flat_fields:

            # Wait for twilight if needed
            while True:
                sun_pos = pocs.observatory.observer.altaz(
                    current_time(),
                    target=get_sun(current_time())
                ).alt

                if sun_pos.value <= 10 and sun_pos.value >= 0:
                    pocs.say("Sun is still not down yet, will wait to take some flats")
                    pocs.sleep(delay=60)
                # Take the flats
                elif sun_pos.value <= 0 and sun_pos.value > twilight_horizon:
                    pocs.say("Taking some flat fields to start the night")
                    pocs.observatory.take_evening_flats(
                        camera_list=list(pocs.observatory.cameras.keys()),
                        take_darks=False
                    )
                elif sun_pos.value <= twilight_horizon:
                    pocs.say("Done with calibration frames")
                    break

        pocs.next_state = 'scheduling'

    except Exception as e:
        pocs.logger.warning("Problem with flat-fielding: {}".format(e))
