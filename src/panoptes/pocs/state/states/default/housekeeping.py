def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.next_state = 'sleeping'

    pocs.say("Resetting the list of observations and doing some cleanup!")

    # Cleanup existing observations
    try:
        pocs.observatory.scheduler.reset_observed_list()
    except Exception as e:  # pragma: no cover
        pocs.logger.warning(f'Problem with cleanup: {e!r}')
