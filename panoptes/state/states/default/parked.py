
def on_enter(event_data):
    """ """
    pan = event_data.model
    pan.say("I'm parked now. Phew.")

    next_state = 'clean_up'

    # Assume dark (we still check weather)
    if pan.is_dark():
        # Assume bad weather so wait
        if not pan.weather_station.is_safe():
            next_state = 'wait'
        else:
            pan.say("Weather is good and it is dark. Something must have gone wrong. Sleeping")
    else:
        pan.say("Another successful night! Let's do some clean up")

    # Either wait until safe or goto next state (sleeping)
    if next_state == 'wait':
        pan.wait_until_safe()
    else:
        pan.goto(next_state)
