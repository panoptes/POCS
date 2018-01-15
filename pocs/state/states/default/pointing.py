from time import sleep

from pocs.images import Image
from pocs.utils import error

wait_interval = 3.
timeout = 150.

num_pointing_images = 1


def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:
        pocs.say("Taking pointing picture.")

        observation = pocs.observatory.current_observation

        fits_headers = pocs.observatory.get_standard_headers(
            observation=observation
        )
        fits_headers['POINTING'] = 'True'
        pocs.logger.debug("Pointing headers: {}".format(fits_headers))

        for img_num in range(num_pointing_images):
            camera_events = dict()

            for cam_name, camera in pocs.observatory.cameras.items():
                if camera.is_primary:
                    pocs.logger.debug("Exposing for camera: {}".format(cam_name))
                    try:
                        # Start the exposures
                        camera_event = camera.take_observation(
                            observation,
                            fits_headers,
                            exp_time=30.,
                            filename='pointing{:02d}'.format(img_num)
                        )

                        camera_events[cam_name] = camera_event

                    except Exception as e:
                        pocs.logger.error("Problem waiting for images: {}".format(e))

            wait_time = 0.
            while not all([event.is_set() for event in camera_events.values()]):
                pocs.check_messages()
                if pocs.interrupted:
                    pocs.say("Observation interrupted!")
                    break

                pocs.logger.debug('Waiting for images: {} seconds'.format(wait_time))
                pocs.status()

                if wait_time > timeout:
                    raise error.Timeout("Timeout waiting for pointing image")

                sleep(wait_interval)
                wait_time += wait_interval

            if pocs.observatory.current_observation is not None:
                pointing_id, pointing_path = pocs.observatory.current_observation.last_exposure
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

        pocs.next_state = 'tracking'

    except Exception as e:
        pocs.say("Hmm, I had a problem checking the pointing error. Going to park. {}".format(e))
