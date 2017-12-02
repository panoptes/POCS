def on_enter(event_data):
    """ The unit is tracking the target. Proceed to observations. """
    pocs = event_data.model
    pocs.say("Checking our tracking")

    try:
        ra_info, dec_info = pocs.observatory.update_tracking()
        pocs.say("Correcting drift: RA {} {:.02f}".format(ra_info[0], ra_info[1]))
        pocs.say("Correcting drift: Dec {} {:.02f}".format(dec_info[0], dec_info[1]))
    except Exception as e:
        pocs.logger.warning("Problem adjusting tracking: {}".format(e))

    pocs.say("Done with tracking adjustment, going to observe")
    pocs.next_state = 'observing'
