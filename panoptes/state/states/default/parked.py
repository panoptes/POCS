
def on_enter(event_data):
    """ """
    pan = event_data.model
    pan.say("I'm parked now. Phew.")

    # Assume dark (we still check weather)
    if pan.is_dark():
        # Assume bad weather so wait
        if not pan.is_safe():
            pan.wait_until_safe()
        else:
            pan.say("Weather is good and it is dark. Something must have gone wrong.")
    else:
        pan.say("Another successful night!")

    pan.say("Cleaning up for the night!")
    pan.clean_up()
