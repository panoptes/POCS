def on_enter(event_data):
    """ The unit is tracking the target. Proceed to observations. """
    pocs = event_data.model
    pocs.say("Checking our tracking")

    try:
        pocs.observatory.update_tracking()
        pocs.say("Done with tracking adjustment, going to observe")
        pocs.next_state = 'observing'

    except Exception as e:
        pocs.logger.warning("Tracking problem: {}".format(e))
        pocs.say("Yikes! A problem while updating our tracking.")
        pocs.next_state = 'parking'
