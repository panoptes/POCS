def on_enter(event_data):
    """ """
    pocs = event_data.model

    if pocs.is_safe() and pocs.should_retry is False:
        pocs.say("Weather is good and it is dark. Something must have gone wrong. " +
                 "Stopping loop.")
        pocs.stop_states()
    else:
        # Note: Unit will "sleep" before transition until it is safe
        # to observe again.
        pocs.next_state = 'ready'
        pocs.reset_observing_run()

        pocs.say("Another successful night!")

        # Wait until dark
        if (pocs.observatory.should_take_flats(which='evening') and
                pocs.observatory.is_dark(horizon='flat') is False):
            pocs.logger.warning("Waiting until flat twilight")
            pocs.wait_until_dark(horizon='flat')
