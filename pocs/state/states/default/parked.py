
def on_enter(event_data):
    """ """
    pan = event_data.model
    pan.say("I'm parked now. Phew.")

    pan.say("Cleaning up for the night!")
    pan.clean_up()
