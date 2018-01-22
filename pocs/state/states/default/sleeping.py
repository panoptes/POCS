def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.next_state = 'ready'

    # If it is dark and safe we shouldn't be in sleeping state
    if pocs.observatory.scheduler.has_valid_observations and \
            pocs.is_dark() and pocs.is_safe():
        if pocs.should_retry is False:
            pocs.say("Weather is good and it is dark. Something must have gone wrong. " +
                     "Stopping loop.")
            pocs.stop_states()
        else:
            pocs.say("Things look okay for now. I'm going to try again.")
    elif pocs.observatory.scheduler.has_valid_observations is False:
        if pocs.run_once is False:
            pocs.say("No more observations for the night. Gonna sleep for an hour.")
            pocs.sleep(delay=3600)  # 1 hour = 3600 seconds
    else:
        pocs.say("Another successful night!")
