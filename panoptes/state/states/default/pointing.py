import os
from functools import partial

from astropy import units as u
from astropy.io import fits
from astropy.coordinates import SkyCoord

from ....utils import images, error


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

    try:
        pan.say("Taking guide picture.")

        guide_camera = pan.observatory.get_guide_camera()

        filename = pan.observatory.construct_filename(guide=True)
        filename = filename.replace('guide.cr2', 'guide_{:03.0f}.cr2'.format(pan._pointing_iteration))
        pan.logger.debug("Path for guide: {}".format(filename))

        guide_image = guide_camera.take_exposure(seconds=pan._pointing_exptime, filename=filename)

        try:
            pan.logger.debug("Waiting for guide image: {}".format(guide_image))
            pan.wait_until_files_exist(
                guide_image, callback=partial(sync_coordinates, pan), timeout=2 * pan._pointing_exptime)
        except error.Timeout as e:
            pan.logger.warning("Problem taking pointing image")
            pan.goto('park')
        except Exception as e:
            pan.logger.error("Problem waiting for images: {}".format(e))
            pan.goto('park')

    except Exception as e:
        pan.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))
        pan.goto('park')


def sync_coordinates(pan, future):
    """ Adjusts pointing error from the most recent image.

    Receives a future from an asyncio call (e.g.,`wait_until_files_exist`) that contains
    filename of recent image. Uses utility function to return pointing error. If the error
    is off by some threshold, sync the coordinates to the center and reacquire the target.
    Iterate on process until threshold is met then start tracking.

    Parameters
    ----------
    future : {asyncio.Future}
        Future from returned from asyncio call, `.get_result` contains filename of image.

    Returns
    -------
    u.Quantity
        The separation between the center of the solved image and the target.
    """
    pan.logger.debug("Getting pointing error")
    pan.say("Ok, I've got the guide picture, let's see how close we are")

    separation = 0 * u.deg
    pan.logger.debug("Default separation: {}".format(separation))

    if future.done() and not future.cancelled():
        pan.logger.debug("Task completed successfully, getting image name")

        fname = future.result()[0]

        pan.logger.debug("Processing image: {}".format(fname))

        target = pan.observatory.current_target
        pan.logger.debug("Target: {}".format(target))

        fits_headers = pan.observatory._get_standard_headers(target=target)
        pan.logger.debug("Guide headers: {}".format(fits_headers))

        kwargs = {}
        kwargs['ra'] = target.ra.value
        kwargs['dec'] = target.dec.value
        kwargs['radius'] = 15.0

        pan.logger.debug("Processing CR2 files with kwargs: {}".format(kwargs))
        processed_info = images.process_cr2(fname, fits_headers=fits_headers, timeout=45, **kwargs)
        # pan.logger.debug("Processed info: {}".format(processed_info))

        # Use the solve file
        fits_fname = processed_info.get('solved_fits_file', None)

        if os.path.exists(fits_fname):
            pan.logger.debug("Solved guide file: {}".format(fits_fname))
            # Get the WCS info and the HEADER info
            pan.logger.debug("Getting WCS and FITS headers for: {}".format(fits_fname))

            wcs_info = images.get_wcsinfo(fits_fname)

            # Save guide wcsinfo to use for future solves
            target.guide_wcsinfo = wcs_info
            pan.logger.debug("WCS Info: {}".format(target.guide_wcsinfo))

            target = None
            with fits.open(fits_fname) as hdulist:
                hdu = hdulist[0]
                # pan.logger.debug("FITS Headers: {}".format(hdu.header))

                target = SkyCoord(ra=float(hdu.header['RA']) * u.degree, dec=float(hdu.header['Dec']) * u.degree)
                pan.logger.debug("Target coords: {}".format(target))

            # Create two coordinates
            center = SkyCoord(ra=wcs_info['ra_center'], dec=wcs_info['dec_center'])
            pan.logger.debug("Center coords: {}".format(center))

            if target is not None:
                separation = center.separation(target)
        else:
            pan.logger.warning("Could not solve guide image")
    else:
        pan.logger.debug("Future cancelled. Result from callback: {}".format(future.result()))

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
        has_target = pan.observatory.mount.set_target_coordinates(center)

        if has_target:
            # Tell the mount we are at the target, which is the center
            pan.observatory.mount.serial_query('calibrate_mount')
            pan.say("Syncing with the latest image...")

            # Now set back to target
            if target is not None:
                pan.observatory.mount.set_target_coordinates(target)

        pan.goto('slew_to_target')
