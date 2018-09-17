def on_enter(event_data):
    """
    Once in the `ready` state our unit has been initialized successfully. The next step is to
    schedule something for the night.
    """
    pocs = event_data.model

    pocs.say("Ok, I'm all set up and ready to go!")

    if pocs.observatory.has_dome and not pocs.observatory.open_dome():
        pocs.say("Failed to open the dome while entering state 'ready'")
        pocs.logger.error("Failed to open the dome while entering state 'ready'")
        pocs.next_state = 'parking'
    else:
        pocs.observatory.mount.unpark()

        # This will check the config settings and current time to
        # determine if we should take flats.
        if pocs.observatory.should_take_flats(which='evening'):
            pocs.next_state = 'calibrating'
        else:
            pocs.next_state = 'scheduling'
