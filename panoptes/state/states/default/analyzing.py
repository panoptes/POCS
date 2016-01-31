from ....utils import images


def on_enter(event_data):
    """ """
    pan = event_data.model

    pan.say("Analyzing image...")
    next_state = 'park'

    try:
        target = pan.observatory.current_target
        pan.logger.debug("For analyzing: Target: {}".format(target))

        observation = target.current_visit
        pan.logger.debug("For analyzing: Observation: {}".format(observation))

        exposure = observation.current_exposure
        pan.logger.debug("For analyzing: Exposure: {}".format(exposure))

        # Get the standard FITS headers. Includes information about target
        fits_headers = pan._get_standard_headers(target=target)
        fits_headers['title'] = target.name

        try:
            kwargs = {}
            if 'ra_center' in target._guide_wcsinfo:
                kwargs['ra'] = target._guide_wcsinfo['ra_center'].value
            if 'dec_center' in target._guide_wcsinfo:
                kwargs['dec'] = target._guide_wcsinfo['dec_center'].value
            if 'fieldw' in target._guide_wcsinfo:
                kwargs['radius'] = target._guide_wcsinfo['fieldw'].value

            # Process the raw images (just makes a pretty right now - we solved above and offset below)
            pan.logger.debug("Starting image processing")
            exposure.process_images(fits_headers=fits_headers, solve=False, **kwargs)
        except Exception as e:
            pan.logger.warning("Problem analyzing: {}".format(e))

        # Should be one Guide image per exposure set corresponding to the `primary` camera
        # current_img = exposure.get_guide_image_info()

        # Analyze image for tracking error
        if target._previous_center is not None:
            pan.logger.debug("Getting offset from guide")

            offset_info = target.get_image_offset(exposure, with_plot=True)

            pan.logger.debug("Offset information: {}".format(offset_info))
            pan.logger.debug("Δ RA/Dec [pixel]: {} {}".format(offset_info['delta_ra'], offset_info['delta_dec']))
        else:
            # If no guide data, this is first image of set
            # target._previous_center =
            # images.crop_data(images.read_image_data(current_img['img_file']),
            # box_width=500)
            target._previous_center = images.crop_data(
                images.read_image_data(exposure.get_guide_image_info()['img_file']), box_width=500)

    except Exception as e:
        pan.logger.error("Problem in analyzing: {}".format(e))

    # If target has visits left, go back to observe
    if not observation.complete:
        # We have successfully analyzed this visit, so we go to next
        next_state = 'adjust_tracking'
    else:
        next_state = 'schedule'

    pan.goto(next_state)
