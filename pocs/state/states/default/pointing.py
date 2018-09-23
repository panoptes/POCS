from astropy import units as u
from pocs.images import Image

MAX_EXTRA_TIME = 60 * u.second


def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    # Get pointing parameters
    pointing_config = pocs.config['pointing']
    num_pointing_images = pointing_config.get('max_iterations', 3)
    should_correct = pointing_config.get('auto_correct', False)
    pointing_threshold = pointing_config.get('threshold', 0.05)  # degrees
    exptime = pointing_config.get('exptime', 30)  # seconds

    try:
        pocs.say("Taking pointing picture.")

        observation = pocs.observatory.current_observation

        fits_headers = pocs.observatory.get_standard_headers(
            observation=observation
        )
        fits_headers['POINTING'] = 'True'
        pocs.logger.debug("Pointing headers: {}".format(fits_headers))

        primary_camera = pocs.observatory.primary_camera

        # Loop over maximum number of pointing iterations
        for img_num in range(num_pointing_images):
            pocs.logger.debug("Taking pointing image {}/{} on: {}",
                              img_num, num_pointing_images, primary_camera)

            # Start the exposure
            camera_event = primary_camera.take_observation(
                observation,
                fits_headers,
                exp_time=exptime,
                filename='pointing{:02d}'.format(img_num)
            )

            # Wait for images to complete
            maximum_duration = exptime + MAX_EXTRA_TIME
            pocs.wait_for_events(camera_event, maximum_duration, event_type='pointing')

            # Analyze pointing
            if observation is not None:
                pointing_id, pointing_path = observation.last_exposure
                pointing_image = Image(
                    pointing_path,
                    location=pocs.observatory.earth_location
                )
                pointing_image.solve_field()

                observation.pointing_image = pointing_image

                pocs.logger.debug("Pointing file: {}".format(pointing_image))

                pocs.say("Ok, I've got the pointing picture, let's see how close we are.")

                pocs.logger.debug("Pointing Coords: {}", pointing_image.pointing)
                pocs.logger.debug("Pointing Error: {}", pointing_image.pointing_error)

                separation = pointing_image.pointing_error.magnitude.value

                if should_correct is False:
                    pocs.logger.info("Pointing correction turned off, done with pointing.")
                    break

                # Correct the pointing
                if separation > pointing_threshold:
                    pocs.say("I'm still a bit away from the field so I'm going to get closer.")

                    # Tell the mount we are at the field, which is the center
                    pocs.say("Syncing with the latest image...")
                    has_field = pocs.observatory.mount.set_target_coordinates(
                        pointing_image.pointing)
                    pocs.logger.debug("Coords set, calibrating")

                    # Calibrate the mount - Sync the mount's known position
                    # with the current actual position.
                    pocs.observatory.mount.query('calibrate_mount')

                    # Now set back to field
                    if has_field:
                        if observation.field is not None:
                            pocs.logger.debug("Slewing back to target")
                            pocs.observatory.mount.set_target_coordinates(observation.field)
                            pocs.observatory.mount.slew_to_target()
                else:
                    pocs.logger.info("Separation is within pointing threshold.")
                    break

        pocs.next_state = 'tracking'

    except Exception as e:
        pocs.say("Hmm, I had a problem checking the pointing error. Going to park. {}".format(e))
