def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.next_state = 'sleeping'

    pocs.say("Recording all the data for the night (not really yet! TODO!!!).")

    # Cleanup existing observations
    try:
        pocs.observatory.cleanup_observations()
    except Exception as e:
        pocs.logger.warning('Problem with cleanup: {}'.format(e))

    pocs.say("Ok, looks like I'm done for the day. Time to get some sleep!")
