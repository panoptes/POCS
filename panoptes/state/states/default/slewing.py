def on_enter(self, event_data):
    """ Once inside the slewing state, set the mount slewing. """
    try:

        # Start the mount slewing
        self.observatory.mount.slew_to_target()

        # Wait until mount is_tracking, then transition to track state
        self.wait_until_mount('is_tracking', 'adjust_pointing')
        self.say("I'm slewing over to the coordinates to track the target.")

    except Exception as e:
        self.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
        self.goto('park')
