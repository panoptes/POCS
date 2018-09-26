import os
import random

from threading import Event
from threading import Timer

import numpy as np

from astropy import units as u
from astropy.io import fits

from pocs.camera import AbstractCamera
from pocs.utils.images import fits as fits_utils


class Camera(AbstractCamera):

    def __init__(self, name='Simulated Camera', *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.logger.debug("Initializing simulated camera")
        self.connect()

    def connect(self):
        """ Connect to camera simulator

        The simulator merely markes the `connected` property.
        """
        # Create a random serial number
        self._serial_number = 'SC{:04d}'.format(random.randint(0, 9999))

        self._connected = True
        self.logger.debug('{} connected'.format(self.name))

    def take_observation(self, observation, headers=None, filename=None, *args, **kwargs):

        exp_time = kwargs.get('exp_time', observation.exp_time.value)
        if exp_time > 2:
            kwargs['exp_time'] = 2
            self.logger.debug("Trimming camera simulator exposure to 2 s")

        return super().take_observation(observation,
                                        headers,
                                        filename,
                                        *args,
                                        **kwargs)

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False,
                      *args,
                      **kwargs):
        """ Take an exposure for given number of seconds """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        if isinstance(seconds, u.Quantity):
            seconds = seconds.to(u.second)
            seconds = seconds.value

        self.logger.debug(
            'Taking {} second exposure on {}: {}'.format(
                seconds, self.name, filename))

        # Build FITS header
        header = self._fits_header(seconds, dark)

        # Set up a Timer that will wait for the duration of the exposure then
        # copy a dummy FITS file to the specified path and adjust the headers
        # according to the exposure time, type.
        exposure_event = Event()
        exposure_thread = Timer(interval=seconds,
                                function=self._fake_exposure,
                                args=[filename, header, exposure_event])
        exposure_thread.start()

        if blocking:
            exposure_event.wait()

        return exposure_event

    def _fake_exposure(self, filename, header, exposure_event):
        # Get example FITS file from test data directory
        file_path = os.path.join(
            os.environ['POCS'],
            'pocs', 'tests', 'data',
            'unsolved.fits'
        )
        fake_data = fits.getdata(file_path)

        if header['IMAGETYP'] == 'Dark Frame':
            # Replace example data with a bunch of random numbers
            fake_data = np.random.randint(low=975, high=1026,
                                          size=fake_data.shape,
                                          dtype=fake_data.dtype)

        fits_utils.write_fits(fake_data, header, filename, self.logger, exposure_event)

    def _process_fits(self, file_path, info):
        file_path = super()._process_fits(file_path, info)
        self.logger.debug('Overriding mount coordinates for camera simulator')
        solved_path = os.path.join(
            os.environ['POCS'],
            'pocs', 'tests', 'data',
            'solved.fits.fz'
        )
        solved_header = fits.getheader(solved_path)
        with fits.open(file_path, 'update') as f:
            hdu = f[0]
            hdu.header.set('RA-MNT', solved_header['RA-MNT'], 'Degrees')
            hdu.header.set('HA-MNT', solved_header['HA-MNT'], 'Degrees')
            hdu.header.set('DEC-MNT', solved_header['DEC-MNT'], 'Degrees')
        return file_path
