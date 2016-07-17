def on_enter(event_data):
    """ """
    pan = event_data.model
    pan.say("Recording all the data for the night (not really yet! TODO!!!).")

    # Assume dark (we still check weather)
    if pan.is_dark():
        # Assume bad weather so wait in ready state
        if not pan.is_safe():
            pan.next_state = 'ready'
        else:
            pan.say("Weather is good and it is dark. Something must have gone wrong. Stopping loop")
            pan.stop_states()
    else:
        pan.say("Ok, looks like I'm done for the day. Time to get some sleep!")
        pan.next_state = 'sleeping'
