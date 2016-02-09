import time


def on_enter(event_data):
    """ Once inside the slewing state, set the mount slewing. """
    pan = event_data.model
    try:

        # Start the mount slewing
        pan.observatory.mount.slew_to_target()

        # Wait until mount is_tracking, then transition to track state
        pan.say("I'm slewing over to the coordinates to track the target.")
        while not pan.observatory.mount.is_tracking:
            time.sleep(3)

        pan.say("Done slewing")
        pan.adjust_pointing()

    except Exception as e:
        pan.say("Wait a minute, there was a problem slewing. Sending to parking. {}".format(e))
        pan.goto('park')
