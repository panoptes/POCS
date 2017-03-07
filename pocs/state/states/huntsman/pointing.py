from time import sleep

from pocs.images import Image

wait_interval = 3.


def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    # point_config = pocs.config.get('pointing', {})

    pocs.next_state = 'parking'

    try:
        pocs.say("Taking pointing picture.")

        primary_camera = pocs.observatory.primary_camera
        observation = pocs.observatory.current_observation

        fits_headers = pocs.observatory.get_standard_headers(observation=observation)
        pocs.logger.debug("Pointing headers: {}".format(fits_headers))

        # Take pointing picture and wait for result
        camera_event = primary_camera.take_observation(observation, fits_headers, exp_time=30., filename='pointing')

        wait_time = 0.
        while not camera_event.is_set():
            pocs.logger.debug('Waiting for pointing image: {} seconds'.format(wait_time))
            pocs.status()

            sleep(wait_interval)
            wait_time += wait_interval

        # WARNING!! Need to do better error checking here to make sure
        # the "current" observation is actually the current observation
        pointing_metadata = pocs.db.get_current('observations')
        pointing_image = Image(pointing_metadata['data']['file_path'])
        pointing_image.solve_field()

        pocs.logger.debug("Pointing file: {}".format(pointing_image))

        pocs.say("Ok, I've got the pointing picture, let's see how close we are.")

        pocs.logger.debug("Pointing Coords: {}".format(pointing_image.pointing))
        pocs.logger.debug("Pointing Error: {}".format(pointing_image.pointing_error))

        # separation = pointing_image.pointing_error.magnitude.value

        # if separation > point_config.get('pointing_threshold', 0.05):
        #     pocs.say("I'm still a bit away from the field so I'm going to try and get a bit closer.")

        #     # Tell the mount we are at the field, which is the center
        #     pocs.say("Syncing with the latest image...")
        #     has_field = pocs.observatory.mount.set_target_coordinates(pointing_image.pointing)
        #     pocs.logger.debug("Coords set, calibrating")
        #     pocs.observatory.mount.serial_query('calibrate_mount')

        #     # Now set back to field
        #     if has_field:
        #         if observation.field is not None:
        #             pocs.logger.debug("Slewing back to target")
        #             pocs.observatory.mount.set_target_coordinates(observation.field)
        #             pocs.observatory.mount.slew_to_target()

        pocs.next_state = 'tracking'

    except Exception as e:
        pocs.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))
