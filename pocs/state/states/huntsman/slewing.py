def on_enter(event_data):
    """ Once inside the slewing state, set the mount slewing. """
    pocs = event_data.model
    try:
        pocs.logger.debug("Inside slew state")

        # Wait until mount is_tracking, then transition to track state
        pocs.say("I'm slewing over to the coordinates to track the target.")

        # Start the mount slewing
        pocs.observatory.slew_to_target()
        pocs.status()  # Send status update

        pocs.say("I'm at the target")
        pocs.next_state = 'focusing'

    except Exception as e:
        pocs.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
