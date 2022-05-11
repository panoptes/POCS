def on_enter(event_data):
    """ Once inside the slewing state, set the mount slewing. """
    pocs = event_data.model
    try:
        if pocs.observatory.mount.is_parked:
            pocs.observatory.mount.unpark()

        # Wait until mount is_tracking, then transition to track state
        pocs.say("I'm slewing over to the coordinates to track the target.")

        # Start the mount slewing
        pocs.observatory.mount.slew_to_target(blocking=True)

        pocs.say("I'm at the target, starting observation!")
        pocs.next_state = 'observing'

    except Exception as e:
        pocs.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
