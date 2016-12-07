def on_enter(event_data):
    """ """
    pocs = event_data.model

    pocs.say("Analyzing image...")

    try:
        observation = pocs.observatory.current_observation

        offset_info = pocs.observatory.analyze_recent()

        pocs.logger.debug("Observation exposure: {} / {}".format(observation.current_exp, observation.min_nexp))

        pocs.next_state = 'tracking'

        # Check for minimum number of exposures
        if observation.current_exp >= observation.min_nexp:
            # Check if we have completed an exposure block
            if observation.current_exp % observation.exp_set_size == 0:
                pocs.next_state = 'scheduling'
    except Exception as e:
        pocs.logger.error("Problem in analyzing: {}".format(e))
        pocs.next_state = 'parking'
