def on_enter(event_data):
    """ """
    pan = event_data.model

    pan.say("Analyzing image...")

    try:
        target = pan.observatory.current_target
        pan.logger.debug("For analyzing: Target: {}".format(target))

        image_info = pan.observatory.analyze_recent()
        # TODO: Handle Quantity correctly
        # pan.db.insert_current('images', image_info)

        pan.logger.debug("Image information: {}".format(image_info))

        if target.current_visit.done_exposing and target.done_visiting:
            # We have successfully analyzed this visit, so we go to next
            pan.next_state = 'scheduling'
        else:
            pan.next_state = 'tracking'
    except Exception as e:
        pan.logger.error("Problem in analyzing: {}".format(e))
        pan.park()
