def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.next_state = 'ready'

    # If it is dark and safe we shouldn't be in sleeping state
    if pocs.is_dark() and pocs.is_safe():
        pocs.say("Weather is good and it is dark. Something must have gone wrong. Stopping loop")
        pocs.stop_states()
    else:
        pocs.say("Another successful night!")
