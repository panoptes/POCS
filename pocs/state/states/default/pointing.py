import os
import subprocess

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits

from ....utils import images


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
    pocs = event_data.model

    try:
        pocs.say("Taking guide picture.")

        # Get guide image
        guide_camera = pocs.observatory.primary_camera
        filename = pocs.observatory.construct_filename(guide=True)
        filename = filename.replace('guide.cr2', 'guide_{:03.0f}.cr2'.format(pocs._pointing_iteration))
        pocs.logger.debug("Path for guide: {}".format(filename))

        # Take guide picture and wait for result
        proc = guide_camera.take_exposure(seconds=pocs._pointing_exptime, filename=filename)
        try:
            pocs.logger.debug("Waiting for guide image: {}".format(filename))
            proc.wait(timeout=1.5 * pocs._pointing_exptime.value)
        except subprocess.TimeoutExpired:
            pocs.logger.debug("Killing camera, timeout expired")
            proc.terminate()
            pocs.next_state = 'park'
        except Exception as e:
            pocs.logger.error("Problem waiting for images: {}".format(e))
            pocs.next_state = 'park'
        else:
            # Sync the image. This will start a slew
            sync_coordinates(pocs, filename)

    except Exception as e:
        pocs.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))
        pocs.next_state = 'park'


def sync_coordinates(pocs, fname):
    """ Adjusts pointing error from the most recent image.

    Uses utility function to return pointing error. If the error is off by some
    threshold, sync the coordinates to the center and reacquire the target.
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
        The separation between the center of the solved image and the target.
    """
    pocs.say("Ok, I've got the guide picture, let's see how close we are.")
    pocs.logger.debug("Getting pointing error")
    pocs.logger.debug("Processing image: {}".format(fname))

    separation = 0 * u.deg
    pocs.logger.debug("Default separation: {}".format(separation))

    target = pocs.observatory.current_target
    pocs.logger.debug("Target: {}".format(target))

    fits_headers = pocs.observatory._get_standard_headers(target=target)
    pocs.logger.debug("Guide headers: {}".format(fits_headers))

    kwargs = {}
    kwargs['ra'] = target.ra.value
    kwargs['dec'] = target.dec.value
    kwargs['radius'] = 15.0

    pocs.logger.debug("Processing CR2 files with kwargs: {}".format(kwargs))
    processed_info = images.process_cr2(fname, fits_headers=fits_headers, timeout=45, **kwargs)
    # pocs.logger.debug("Processed info: {}".format(processed_info))

    # Use the solve file
    fits_fname = processed_info.get('solved_fits_file', None)

    if os.path.exists(fits_fname):
        pocs.logger.debug("Solved guide file: {}".format(fits_fname))
        # Get the WCS info and the HEADER info
        pocs.logger.debug("Getting WCS and FITS headers for: {}".format(fits_fname))

        wcs_info = images.get_wcsinfo(fits_fname)

        # Save guide wcsinfo to use for future solves
        target.guide_wcsinfo = wcs_info
        pocs.logger.debug("WCS Info: {}".format(target.guide_wcsinfo))

        target = None
        with fits.open(fits_fname) as hdulist:
            hdu = hdulist[0]
            # pocs.logger.debug("FITS Headers: {}".format(hdu.header))

            target = SkyCoord(ra=float(hdu.header['RA']) * u.degree, dec=float(hdu.header['Dec']) * u.degree)
            pocs.logger.debug("Target coords: {}".format(target))

        # Create two coordinates
        center = SkyCoord(ra=wcs_info['ra_center'], dec=wcs_info['dec_center'])
        pocs.logger.debug("Center coords: {}".format(center))

        if target is not None:
            separation = center.separation(target)

        pocs.logger.debug("Solved separation: {}".format(separation))
    else:
        pocs.logger.warning("Could not solve guide image")

    if separation < pocs._pointing_threshold:
        pocs.say("I'm pretty close to the target, starting track.")
        pocs.next_state = 'tracking'

    elif pocs._pointing_iteration >= pocs._max_iterations:
        pocs.say("I've tried to get closer to the target but can't. I'll just observe where I am.")
        pocs.next_state = 'tracking'

    else:
        pocs.say("I'm still a bit away from the target so I'm going to try and get a bit closer.")

        pocs._pointing_iteration = pocs._pointing_iteration + 1

        # Tell the mount we are at the target, which is the center
        pocs.say("Syncing with the latest image...")
        has_target = pocs.observatory.mount.set_target_coordinates(center)
        pocs.observatory.mount.serial_query('calibrate_mount')

        # Now set back to target
        if has_target:
            if target is not None:
                pocs.observatory.mount.set_target_coordinates(target)

        pocs.next_state = 'slewing'
