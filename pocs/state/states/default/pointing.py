import time

from astropy import units as u

from pocs.utils import current_time
from pocs.utils import images


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

    # This should all move to the `states.pointing` module or somewhere else
    point_config = pocs.config.get('pointing', {})
    pointing_exptime = point_config.get('exptime', 30) * u.s

    pocs.next_state = 'parking'

    try:
        pocs.say("Taking pointing picture.")

        primary_camera = pocs.observatory.primary_camera
        observation = pocs.observatory.current_observation

        image_dir = pocs.config['directories']['images']

        filename = "{}/fields/{}/{}/{}/pointing.cr2".format(
            image_dir,
            observation.field.field_name,
            primary_camera.uid,
            observation.seq_time)

        start_time = current_time(flatten=True)
        fits_headers = pocs.observatory.get_standard_headers(observation=observation)

        # Add observation metadata
        fits_headers.update(observation.status())

        image_id = '{}_{}_{}'.format(
            pocs.config['name'],
            primary_camera.uid,
            start_time
        )

        sequence_id = '{}_{}_{}'.format(
            pocs.config['name'],
            primary_camera.uid,
            observation.seq_time
        )

        camera_metadata = {
            'camera_uid': primary_camera.uid,
            'camera_name': primary_camera.name,
            'filter': primary_camera.filter_type,
            'img_file': filename,
            'is_primary': primary_camera.is_primary,
            'start_time': start_time,
            'image_id': image_id,
            'sequence_id': sequence_id
        }
        fits_headers.update(camera_metadata)
        pocs.logger.debug("Pointing headers: {}".format(fits_headers))

        # Take pointing picture and wait for result
        primary_camera.take_exposure(
            seconds=pointing_exptime,
            filename=filename,
        )

        time.sleep(pointing_exptime.value)
        time.sleep(6)

        pocs.logger.debug("Processing {}".format(filename))

        pocs.logger.debug("Converting CR2 -> FITS: {}".format(filename))
        fits_path = images.cr2_to_fits(filename, headers=fits_headers, remove_cr2=True)

        observation.exposure_list[image_id] = fits_path

        pocs.logger.debug("Adding image metadata to db: {}".format(image_id))
        pocs.db.observations.insert_one({
            'data': camera_metadata,
            'date': current_time(datetime=True),
            'image_id': image_id,
        })

        pocs.logger.debug("Pointing file: {}".format(fits_path))

        pocs.say("Ok, I've got the pointing picture, let's see how close we are.")

        # Get the image and solve
        pointing_coord, pointing_error = images.get_pointing_error(fits_path, verbose=True)

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
