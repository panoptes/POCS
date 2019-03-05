def on_enter(event_data):
    """ """
    pocs = event_data.model

    observation = pocs.observatory.current_observation

    pocs.say("Analyzing image {} / {}".format(observation.current_exp_num, observation.min_nexp))

    pocs.next_state = 'tracking'
    try:

        pocs.observatory.analyze_recent()

        if pocs.force_reschedule:
            pocs.say("Forcing a move to the scheduler")
            pocs.next_state = 'scheduling'

        # Check for minimum number of exptimes
        if observation.current_exp_num >= observation.min_nexp:
            # Check if we have completed an exptime block
            if observation.current_exp_num % observation.exp_set_size == 0:
                pocs.next_state = 'scheduling'
    except Exception as e:
        pocs.logger.error("Problem in analyzing: {}".format(e))
        pocs.next_state = 'parking'
