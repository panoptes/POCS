"""State: pointing.

Capture a short exposure, solve it, measure pointing error, optionally correct,
then proceed to 'tracking'.
"""

import numpy as np
from panoptes.utils.time import wait_for_events

from panoptes.pocs.images import Image

MAX_EXTRA_TIME = 60  # second


def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = "parking"

    # Get pointing parameters
    pointing_config = pocs.get_config("pointing")
    max_attempts = int(pointing_config.get("max_attempts", 3))
    if max_attempts == 0:
        pocs.logger.info(f"Skipping pointing state, {max_attempts=}")
        pocs.next_state = "tracking"
        return

    should_correct = pointing_config.get("auto_correct", False)
    pointing_threshold = pointing_config.get("threshold", 0.05)  # degrees
    exptime = pointing_config.get("exptime", 30)  # seconds

    # We want about 3 iterations of waiting loop during pointing image.
    wait_delay = int(exptime / 3) + 1

    try:
        pocs.say("Taking pointing picture.")

        observation = pocs.observatory.current_observation

        fits_headers = pocs.observatory.get_standard_headers(observation=observation)
        fits_headers["POINTING"] = "True"
        pocs.logger.debug(f"Pointing headers: {fits_headers!r}")

        primary_camera = pocs.observatory.primary_camera

        # Loop over maximum number of pointing iterations
        for img_num in range(max_attempts):
            pocs.logger.info(f"Pointing image {img_num + 1}/{max_attempts} on: {primary_camera}")

            # Start the exposure
            camera_event = primary_camera.take_observation(
                observation,
                headers=fits_headers,
                exptime=exptime,
                filename=f"pointing{img_num:02d}",
            )

            # Wait for images to complete
            maximum_duration = exptime + MAX_EXTRA_TIME

            def waiting_cb():
                pocs.logger.info(f"Waiting for pointing image {img_num + 1}/{max_attempts}")
                return pocs.is_safe()

            wait_for_events(
                camera_event, timeout=maximum_duration, callback=waiting_cb, sleep_delay=wait_delay
            )

            # Analyze pointing
            if observation is not None:
                pointing_id, pointing_path = observation.pointing_image
                pointing_image = Image(
                    pointing_path,
                    location=pocs.observatory.earth_location,
                )
                pocs.logger.debug(f"Pointing image: {pointing_image}")

                pocs.say("Ok, I've got the pointing picture, let's see how close we are.")
                pointing_image.solve_field()

                # Store the solved image object
                observation.pointing_images[pointing_id] = pointing_image

                pocs.logger.debug(f"Pointing Coords: {pointing_image.pointing}")
                pocs.logger.debug(f"Pointing Error: {pointing_image.pointing_error}")

                if should_correct is False:
                    pocs.logger.info("Pointing correction turned off, done with pointing.")
                    break

                delta_ra = pointing_image.pointing_error.delta_ra.value
                delta_dec = pointing_image.pointing_error.delta_dec.value

                # Correct the pointing if either axis is off.
                if np.abs(delta_ra) > pointing_threshold or np.abs(delta_dec) > pointing_threshold:
                    pocs.say("I'm still a bit away from the field so I'm going to get closer.")

                    # Tell the mount we are at the field, which is the center
                    pocs.say("Syncing with the latest image...")
                    has_field = pocs.observatory.mount.set_target_coordinates(
                        pointing_image.pointing
                    )
                    pocs.logger.debug("Coords set, calibrating")

                    # Calibrate the mount - Sync the mount's known position
                    # with the current actual position.
                    pocs.observatory.mount.query("calibrate_mount")

                    # Now set back to field
                    if has_field:
                        if observation.field is not None:
                            pocs.logger.debug("Slewing back to target")
                            target_set = pocs.observatory.mount.set_target_coordinates(
                                observation.field
                            )

                            # Check if target was set.
                            if target_set is False:
                                pocs.logger.warning("Field not properly set. Parking.")
                            else:
                                pocs.observatory.mount.slew_to_target(blocking=True)

                    if img_num == (max_attempts - 1):
                        pocs.logger.info(
                            "Separation outside threshold but at max corrections. "
                            + "Will proceed to observations."
                        )
                else:
                    pocs.logger.info("Separation is within pointing threshold, starting tracking.")
                    break

        pocs.next_state = "tracking"

    except Exception as e:
        pocs.logger.warning(f"Error in pointing: {e!r}")
        pocs.say("Hmm, I had a problem checking the pointing error. Going to park.")
