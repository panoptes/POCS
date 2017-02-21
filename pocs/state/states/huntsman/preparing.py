
def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:
        pocs.say("Preparing the observations for our selected target")

        if pocs.observatory.has_hdr_mode:
            pocs.observatory.make_hdr_observation()

        pocs.next_state = 'slewing'

    except Exception as e:
        pocs.logger.warning("Problem with preparing: {}".format())
