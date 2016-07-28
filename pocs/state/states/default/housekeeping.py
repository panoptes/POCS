def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("Recording all the data for the night (not really yet! TODO!!!).")

    # Assume dark (we still check weather)
    if pocs.is_dark():
        # Assume bad weather so wait in ready state
        if not pocs.is_safe():
            pocs.next_state = 'ready'
        else:
            pocs.say("Weather is good and it is dark. Something must have gone wrong. Stopping loop")
            pocs.stop_states()
    else:
        pocs.say("Ok, looks like I'm done for the day. Time to get some sleep!")
        pocs.next_state = 'sleeping'
