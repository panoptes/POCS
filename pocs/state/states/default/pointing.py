import os

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits


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

        filename = "{}/{}/{}/{}/pointing.cr2".format(
            image_dir,
            observation.field.field_name,
            primary_camera.uid,
            observation.seq_time)

        # Take pointing picture and wait for result
        primary_camera.take_exposure(seconds=pointing_exptime, filename=filename)
        sync_coordinates(pocs, filename, point_config)

        pocs.next_state = 'tracking'

    except Exception as e:
        pocs.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))


def sync_coordinates(pocs, fname, point_config):
    """ Adjusts pointing error from the most recent image.

    Uses utility function to return pointing error. If the error is off by some
    threshold, sync the coordinates to the center and reacquire the field.
    Iterate on process until threshold is met then start tracking.

    Parameters
    ----------
    pocs   : {pocsoptes}
        A `pocsoptes` instance
    fname : {str}
        Filename of the image to sync with. Should be the pointing image.

    Returns
    -------
    u.Quantity
        The separation between the center of the solved image and the field.
    """
    pocs.say("Ok, I've got the pointing picture, let's see how close we are.")

    pointing_threshold = point_config.get('threshold', 0.01) * u.deg

    pocs.logger.debug("Getting pointing error")
    pocs.logger.debug("Processing image: {}".format(fname))

    separation = 0 * u.deg
    pocs.logger.debug("Default separation: {}".format(separation))

    field = pocs.observatory.current_observation.field
    pocs.logger.debug("Observation: {}".format(field))

    fits_headers = pocs.observatory.get_standard_headers(observation=pocs.observatory.current_observation)
    pocs.logger.debug("pointing headers: {}".format(fits_headers))

    kwargs = {}
    kwargs['ra'] = field.ra.value
    kwargs['dec'] = field.dec.value
    kwargs['radius'] = 15.0

    ############################################################################
    # Image object method replaces following
    ############################################################################
    pocs.logger.debug("Processing CR2 files with kwargs: {}".format(kwargs))
    processed_info = images.process_cr2(fname, fits_headers=fits_headers, timeout=45, **kwargs)

    # Use the solve file
    fits_fname = processed_info.get('solved_fits_file', None)

    if os.path.exists(fits_fname):
        pocs.logger.debug("Solved pointing file: {}".format(fits_fname))
        # Get the WCS info and the HEADER info
        pocs.logger.debug("Getting WCS and FITS headers for: {}".format(fits_fname))

        wcs_info = images.get_wcsinfo(fits_fname)

        # Save pointing wcsinfo to use for future solves
        field.pointing_wcsinfo = wcs_info
        pocs.logger.debug("WCS Info: {}".format(field.pointing_wcsinfo))

        field = None
        with fits.open(fits_fname) as hdulist:
            hdu = hdulist[0]
            # pocs.logger.debug("FITS Headers: {}".format(hdu.header))

            field = SkyCoord(ra=float(hdu.header['RA']) * u.degree, dec=float(hdu.header['Dec']) * u.degree)
            pocs.logger.debug("field coords: {}".format(field))

        # Create two coordinates
        center = SkyCoord(ra=wcs_info['ra_center'], dec=wcs_info['dec_center'])
        pocs.logger.debug("Center coords: {}".format(center))

        if field is not None:
            separation = center.separation(field)

        pocs.logger.debug("Solved separation: {}".format(separation))
    else:
        pocs.logger.warning("Could not solve pointing image")

    ############################################################################
    # End replacement
    ############################################################################

    if separation > pointing_threshold:
        pocs.say("I'm still a bit away from the field so I'm going to try and get a bit closer.")

        # Tell the mount we are at the field, which is the center
        pocs.say("Syncing with the latest image...")
        has_field = pocs.observatory.mount.set_target_coordinates(center)
        pocs.observatory.mount.serial_query('calibrate_mount')

        # Now set back to field
        if has_field:
            if field is not None:
                pocs.observatory.mount.set_target_coordinates(field)
