
def on_enter(event_data):
    """ The unit is tracking the target. Proceed to observations. """
    pocs = event_data.model
    pocs.next_state = 'parking'

    # If we came from pointing then don't try to adjust
    if event_data.transition.source != 'pointing':
        pocs.say("Checking our tracking")
        try:
            pocs.observatory.update_tracking()
            pocs.say("Done with tracking adjustment, going to observe")
            pocs.next_state = 'observing'
        except Exception as e:
            pocs.logger.warning("Problem adjusting tracking: {}".format(e))
    else:
        pocs.next_state = 'observing'
