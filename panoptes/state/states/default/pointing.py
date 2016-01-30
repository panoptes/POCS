import os
from functools import partial

from astropy import units as u
from astropy.io import fits
from astropy.coordinates import SkyCoord

from ....utils import images


def on_enter(self, event_data):
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

    try:
        self.say("Taking guide picture.")

        guide_camera = self.observatory.get_guide_camera()

        filename = self.observatory.construct_filename(guide=True)
        filename = filename.replace('guide.cr2', 'guide_{:03.0f}.cr2'.format(self._pointing_iteration))
        self.logger.debug("Path for guide: {}".format(filename))

        guide_image = guide_camera.take_exposure(seconds=self._pointing_exptime, filename=filename)
        self.logger.debug("Waiting for guide image: {}".format(guide_image))

        try:
            future = self.wait_until_files_exist(guide_image)

            self.logger.debug("Adding callback for guide image")
            future.add_done_callback(partial(self.sync_coordinates))
        except Exception as e:
            self.logger.error("Problem waiting for images: {}".format(e))
            self.goto('park')

    except Exception as e:
        self.say("Hmm, I had a problem checking the pointing error. Sending to parking. {}".format(e))
        self.goto('park')


def sync_coordinates(self, future):
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
    self.logger.debug("Getting pointing error")
    self.say("Ok, I've got the guide picture, let's see how close we are")

    separation = 0 * u.deg
    self.logger.debug("Default separation: {}".format(separation))

    if future.done() and not future.cancelled():
        self.logger.debug("Task completed successfully, getting image name")

        fname = future.result()[0]

        self.logger.debug("Processing image: {}".format(fname))

        target = self.observatory.current_target

        fits_headers = self._get_standard_headers(target=target)
        self.logger.debug("Guide headers: {}".format(fits_headers))

        kwargs = {}
        if 'ra_center' in target._guide_wcsinfo:
            kwargs['ra'] = target._guide_wcsinfo['ra_center'].value
        if 'dec_center' in target._guide_wcsinfo:
            kwargs['dec'] = target._guide_wcsinfo['dec_center'].value
        if 'fieldw' in target._guide_wcsinfo:
            kwargs['radius'] = target._guide_wcsinfo['fieldw'].value

        self.logger.debug("Processing CR2 files with kwargs: {}".format(kwargs))
        processed_info = images.process_cr2(fname, fits_headers=fits_headers, timeout=45, **kwargs)
        # self.logger.debug("Processed info: {}".format(processed_info))

        # Use the solve file
        fits_fname = processed_info.get('solved_fits_file', None)

        if os.path.exists(fits_fname):
            # Get the WCS info and the HEADER info
            self.logger.debug("Getting WCS and FITS headers for: {}".format(fits_fname))

            wcs_info = images.get_wcsinfo(fits_fname)
            self.logger.debug("WCS Info: {}".format(wcs_info))

            # Save guide wcsinfo to use for future solves
            target._guide_wcsinfo = wcs_info

            target = None
            with fits.open(fits_fname) as hdulist:
                hdu = hdulist[0]
                # self.logger.debug("FITS Headers: {}".format(hdu.header))

                target = SkyCoord(ra=float(hdu.header['RA']) * u.degree, dec=float(hdu.header['Dec']) * u.degree)
                self.logger.debug("Target coords: {}".format(target))

            # Create two coordinates
            center = SkyCoord(ra=wcs_info['ra_center'], dec=wcs_info['dec_center'])
            self.logger.debug("Center coords: {}".format(center))

            if target is not None:
                separation = center.separation(target)
    else:
        self.logger.debug("Future cancelled. Result from callback: {}".format(future.result()))

    self.logger.debug("Separation: {}".format(separation))
    if separation < self._pointing_threshold:
        self.say("I'm pretty close to the target, starting track.")
        self.goto('track')
    elif self._pointing_iteration >= self._max_iterations:
        self.say("I've tried to get closer to the target but can't. I'll just observe where I am.")
        self.goto('track')
    else:
        self.say("I'm still a bit away from the target so I'm going to try and get a bit closer.")

        self._pointing_iteration = self._pointing_iteration + 1

        # Set the target to center
        has_target = self.observatory.mount.set_target_coordinates(center)

        if has_target:
            # Tell the mount we are at the target, which is the center
            self.observatory.mount.serial_query('calibrate_mount')
            self.say("Syncing with the latest image...")

            # Now set back to target
            if target is not None:
                self.observatory.mount.set_target_coordinates(target)

        self.goto('slew_to_target')
