
def on_enter(event_data):
    """ Adjust pointing.

    * Take 60 second exposure
    * Call `sync_coordinates`
        * Plate-solve
        * Get pointing error
        * If within `_pointing_threshold`
            * goto tracking
        * Else
            * set set mount target coords to center RA/Dec
            * sync mount coords
            * slew to target
    """
    pan = event_data.model

    separation = 0

    target = pan.observatory.mount.get_current_target()
    center = None

    try:
        pan.say("Taking guide picture.")

        guide_camera = pan.observatory.get_guide_camera()

        filename = pan.observatory.construct_filename(guide=True)
        filename = filename.replace('guide.cr2', 'guide_{:03.0f}.cr2'.format(pan._pointing_iteration))
        pan.logger.debug("Path for guide: {}".format(filename))

        guide_image = guide_camera.take_exposure(seconds=pan._pointing_exptime, filename=filename)
        pan.logger.debug("Waiting for guide image: {}".format(guide_image))

        try:
            pan.wait_until_files_exist(guide_image)

            pan.logger.debug("Adding callback for guide image")
            separation, center = pan.observatory.get_separation(guide_image, return_center=True)
        except Exception as e:
            pan.logger.error("Problem waiting for images: {}".format(e))
            pan.goto('park')

    except Exception as e:
        pan.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))
        pan.goto('park')

    pan.logger.debug("Separation: {}".format(separation))
    if separation < pan._pointing_threshold:
        pan.say("I'm pretty close to the target, starting track.")
        pan.goto('track')
    elif pan._pointing_iteration >= pan._max_iterations:
        pan.say("I've tried to get closer to the target but can't. I'll just observe where I am.")
        pan.goto('track')
    else:
        pan.say("I'm still a bit away from the target so I'm going to try and get a bit closer.")

        pan._pointing_iteration = pan._pointing_iteration + 1

        # Set the target to center
        has_center = False
        if center is not None:
            has_center = pan.observatory.mount.set_target_coordinates(center)

        if has_center:
            # Tell the mount we are at the target, which is the center
            pan.observatory.mount.serial_query('calibrate_mount')
            pan.say("Syncing with the latest image...")

            # Now set back to target
            if target is not None:
                pan.observatory.mount.set_target_coordinates(target)

        pan.goto('slew_to_target')
