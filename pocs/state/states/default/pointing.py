from time import sleep

from pocs.utils import images

wait_interval = 3.


def on_enter(event_data):
    """ Adjust pointing.

    * Take 60 second exposure
    * Call `sync_coordinates`
        * Plate-solve
        * Get pointing error
        * If within `_pointing_threshold`
            * goto tracking
        * Else
            * set set mount field coords to center RA/Dec
            * sync mount coords
            * slew to field
    """
    pocs = event_data.model

    point_config = pocs.config.get('pointing', {})

    pocs.next_state = 'parking'

    try:
        pocs.say("Taking pointing picture.")

        primary_camera = pocs.observatory.primary_camera
        observation = pocs.observatory.current_observation

        fits_headers = pocs.observatory.get_standard_headers(observation=observation)
        pocs.logger.debug("Pointing headers: {}".format(fits_headers))

        # Take pointing picture and wait for result
        camera_event = primary_camera.take_observation(observation, fits_headers, exp_time=30.)

        wait_time = 0.
        while not camera_event.is_set():
            pocs.logger.debug('Waiting for pointing image: {} seconds'.format(wait_time))
            pocs.status()

            sleep(wait_interval)
            wait_time += wait_interval

        pointing_metadata = pocs.db.get_current('observations')
        file_path = pointing_metadata['data']['file_path']

        pocs.logger.debug("Pointing file: {}".format(file_path))

        pocs.say("Ok, I've got the pointing picture, let's see how close we are.")

        # Get the image and solve
        pointing_coord, pointing_error = images.get_pointing_error(file_path)

        pocs.logger.debug("Pointing coords: {}".format(pointing_coord))
        pocs.logger.debug("Pointing Error: {}".format(pointing_error))

        separation = pointing_error.separation.value

        if separation > point_config.get('pointing_threshold', 0.05):
            pocs.say("I'm still a bit away from the field so I'm going to try and get a bit closer.")

            # Tell the mount we are at the field, which is the center
            pocs.say("Syncing with the latest image...")
            has_field = pocs.observatory.mount.set_target_coordinates(pointing_coord)
            pocs.logger.debug("Coords set, calibrating")
            pocs.observatory.mount.serial_query('calibrate_mount')

            # Now set back to field
            if has_field:
                if observation.field is not None:
                    pocs.logger.debug("Slewing back to target")
                    pocs.observatory.mount.set_target_coordinates(observation.field)
                    pocs.observatory.mount.slew_to_target()

        pocs.next_state = 'tracking'

    except Exception as e:
        pocs.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))
