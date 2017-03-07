
def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("I'm parked now. Phew.")

    pocs.say("Cleaning up for the night!")
    pocs.next_state = 'housekeeping'
