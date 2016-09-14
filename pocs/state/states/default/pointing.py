import os

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits

from pocs import images


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

        # Take pointing picture and wait for result
        primary_camera.take_exposure(seconds=pointing_exptime, filename=filename)

        pocs.say("Ok, I've got the pointing picture, let's see how close we are.")

        # Get the image and solve
        pointing_image = images.Image(filename)
        pointing_image.solve_field(radius=15)

        pocs.logger.debug("Pointing Error: {}".format(pointing_image.pointing_error))

        separation = pointing_image.pointing_error.magnitude

        if separation > point_config.get('pointing_threshold', 0.05):
            pocs.say("I'm still a bit away from the field so I'm going to try and get a bit closer.")

            # Tell the mount we are at the field, which is the center
            pocs.say("Syncing with the latest image...")
            has_field = pocs.observatory.mount.set_target_coordinates(pointing_image.pointing)
            pocs.observatory.mount.serial_query('calibrate_mount')

            # Now set back to field
            if has_field:
                if observation.field is not None:
                    pocs.observatory.mount.set_target_coordinates(observation.field)
                    pocs.observatory.mount.slew_to_target()

        pocs.next_state = 'tracking'

    except Exception as e:
        pocs.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))
