def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("Recording all the data for the night (not really yet! TODO!!!).")

    # Cleanup existing observations
    pocs.observatory.cleanup_observations()

    pocs.say("Ok, looks like I'm done for the day. Time to get some sleep!")
    pocs.next_state = 'sleeping'
