def on_enter(event_data):
    """ """
    pan = event_data.model

    pan.say("Analyzing image...")
    next_state = 'park'

    try:
        target = pan.observatory.current_target
        pan.logger.debug("For analyzing: Target: {}".format(target))

        image_info = target.analyze_recent()
        pan.messaging.send_message('STATUS', {'observatory': image_info})

        pan.logger.debug("Image information: {}".format(image_info))
        pan.logger.debug("Δ RA/Dec [pixel]: {} {}".format(image_info['delta_ra_px'], image_info['delta_dec_px']))

    except Exception as e:
        pan.logger.error("Problem in analyzing: {}".format(e))

    # If target has visits left, go back to observe
    if not target.done_visiting:
        # We have successfully analyzed this visit, so we go to next
        next_state = 'adjust_tracking'
    else:
        next_state = 'schedule'

    pan.goto(next_state)
