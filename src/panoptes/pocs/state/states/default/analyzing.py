def on_enter(event_data):
    """ """
    pocs = event_data.model

    observation = pocs.observatory.current_observation

    pocs.say(f"Analyzing image {observation.current_exp_num} / {observation.min_nexp}")

    pocs.next_state = 'tracking'
    try:

        if pocs.get_config('mount.settings.update_tracking', False):
            pocs.logger.debug('Analyzing recent image from analyzing state')
            pocs.observatory.analyze_recent()

        if pocs.get_config('observations.upload_image_immediately', False):
            pocs.say('Uploading the image!')
            try:
                pocs.observatory.upload_recent()
            except FileNotFoundError:
                pocs.observatory.warning(f'Most recent upload failed')

        if pocs.get_config('actions.FORCE_RESCHEDULE', False):
            pocs.say("Forcing a move to the scheduler")
            pocs.next_state = 'scheduling'

        # Check if observation set is finished
        if observation.set_is_finished:
            pocs.next_state = 'scheduling'

    except Exception as e:
        pocs.logger.error(f"Problem in analyzing: {e!r}")
        pocs.next_state = 'parking'
