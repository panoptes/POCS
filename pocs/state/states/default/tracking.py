from pocs.utils import current_time


def on_enter(event_data):
    """ The unit is tracking the target. Proceed to observations. """
    pocs = event_data.model
    pocs.next_state = 'parking'

    # If we came from pointing then don't try to adjust
    if event_data.transition.source != 'pointing':
        pocs.say("Checking our tracking")
        try:
            ra_info, dec_info = pocs.observatory.update_tracking()
            pocs.say("Correcting drift: RA {} {:.02f}".format(ra_info[0], ra_info[1]))
            pocs.say("Correcting drift: Dec {} {:.02f}".format(dec_info[0], dec_info[1]))

            # Adjust tracking for up to 30 seconds then fail if not done.
            start_tracking_time = current_time()
            while pocs.observatory.mount.is_tracking is False:
                if (current_time() - start_tracking_time).sec > 30:
                    raise Exception("Trying to adjust tracking for more than 30 seconds")

                pocs.logger.debug("Waiting for tracking adjustment")
                pocs.sleep(delay=0.5)

            pocs.say("Done with tracking adjustment, going to observe")
            pocs.next_state = 'observing'
        except Exception as e:
            pocs.logger.warning("Problem adjusting tracking: {}".format(e))
