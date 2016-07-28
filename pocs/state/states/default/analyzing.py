def on_enter(event_data):
    """ """
    pocs = event_data.model

    pocs.say("Analyzing image...")

    try:
        target = pocs.observatory.current_target
        pocs.logger.debug("For analyzing: Target: {}".format(target))

        image_info = pocs.observatory.analyze_recent()
        # TODO: Handle Quantity correctly
        # pocs.db.insert_current('images', image_info)

        pocs.logger.debug("Image information: {}".format(image_info))

        if target.current_visit.done_exposing and target.done_visiting:
            # We have successfully analyzed this visit, so we go to next
            pocs.next_state = 'scheduling'
        else:
            pocs.next_state = 'tracking'
    except Exception as e:
        pocs.logger.error("Problem in analyzing: {}".format(e))
        pocs.park()
