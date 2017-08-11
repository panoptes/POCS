def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:
        pocs.say("It's dither time!")

        current_observation = pocs.observatory.current_observation

        pocs.logger.debug("Setting dithering coords: {}".format(current_observation.field))

        if pocs.observatory.mount.set_target_coordinates(current_observation.field):

            pocs.observatory.slew_to_target()
            pocs.status()

            # Wait until mount is_tracking, then transition to track state
            pocs.say("I'm moving to new dither position")

            pocs.next_state = 'observing'

    except Exception as e:
        pocs.logger.warning("Problem with preparing: {}".format())
