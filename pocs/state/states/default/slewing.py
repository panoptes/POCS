def on_enter(event_data):
    """ Once inside the slewing state, set the mount slewing. """
    pan = event_data.model
    try:
        pan.logger.debug("Inside slew state")

        # Start the mount slewing
        pan.observatory.mount.slew_to_target()

        # Wait until mount is_tracking, then transition to track state
        pan.say("I'm slewing over to the coordinates to track the target.")

        while not pan.observatory.mount.is_tracking:
            pan.logger.debug("Slewing to target")
            pan.sleep()

        pan.say("I'm at the target, checking pointing.")
        pan.next_state = 'pointing'

    except Exception as e:
        pan.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
