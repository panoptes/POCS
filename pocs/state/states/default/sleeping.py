def on_enter(event_data):
    """ """
    pocs = event_data.model

    if pocs.run_once:
        pocs.say('Only wanted to run once, shuttting down')
    elif pocs.is_safe() and pocs.should_retry is False:
        pocs.say("Weather is good and it is dark. Something must have gone wrong. " +
                 "Stopping loop.")
        pocs.stop_states()
    else:
        # Note: Unit will "sleep" before transition until it is safe
        # to observe again.
        pocs.next_state = 'ready'
        pocs.reset_observing_run()

        pocs.say("Another successful night!")

        # Sleep until dark.
        if (pocs.observatory.is_dark(horizon='flat') is False):
            pocs.logger.warning("Waiting until flat twilight")

            # We don't check the safety here because we are already parked
            pocs.wait_until_dark(horizon='flat', check_safety=False)
