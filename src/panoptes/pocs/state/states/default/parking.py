def on_enter(event_data):
    """ """
    pocs = event_data.model

    # Clear any current observation
    pocs.observatory.current_observation = None
    pocs.observatory.current_offset_info = None

    pocs.next_state = 'parked'

    if pocs.observatory.has_dome:
        pocs.say('Closing dome')
        if not pocs.observatory.close_dome():
            pocs.logger.critical('Unable to close dome!')
            pocs.say('Unable to close dome!')

    pocs.say("Ok, let's park!")
    pocs.observatory.mount.park()
