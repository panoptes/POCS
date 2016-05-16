def on_enter(event_data):
    """ The unit is tracking the target. Proceed to observations. """
    pan = event_data.model
    pan.say("Checking our tracking")

    try:
        pan.say("I'm adjusting the tracking rate")
        pan.observatory.update_tracking()
        pan.say("Done with tracking adjustment, going to observe")
        pan.observe()

    except Exception as e:
        pan.logger.warning("Tracking problem: {}".format(e))
        pan.say("Yikes! A problem while updating our tracking.")
        pan.park()
