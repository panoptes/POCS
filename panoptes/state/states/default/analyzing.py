def on_enter(event_data):
    """ """
    pan = event_data.model

    pan.say("Analyzing image...")
    next_state = 'park'

    try:
        target = pan.observatory.current_target
        pan.logger.debug("For analyzing: Target: {}".format(target))

        image_info = pan.observatory.analyze_recent()
        pan.messaging.send_message('STATUS', {'observatory': image_info})

        pan.logger.debug("Image information: {}".format(image_info))
        pan.logger.debug("Δ RA/Dec [pixel]: {} {}".format(image_info['delta_ra_px'], image_info['delta_dec_px']))

        # Set next state
        next_state = 'adjust_tracking'
    except Exception as e:
        pan.logger.error("Problem in analyzing: {}".format(e))

    if target.current_visit.done_exposing and target.done_visiting:
        # We have successfully analyzed this visit, so we go to next
        next_state = 'schedule'

    pan.goto(next_state)
