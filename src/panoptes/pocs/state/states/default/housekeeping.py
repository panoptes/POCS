def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.next_state = 'sleeping'

    pocs.say("Recording all the data for the night.")

    # Cleanup existing observations
    try:
        pocs.observatory.cleanup_observations()
    except Exception as e:  # pragma: no cover
        pocs.logger.warning('Problem with cleanup: {}'.format(e))

    pocs.say("Ok, I'm done cleaning up all the recorded data.")
