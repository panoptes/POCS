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
        self._serial_number = 'SC{:4d}'.format(random.randint(0, 9999))

        self._connected = True
        self.logger.debug('{} connected'.format(self.name))

    def take_observation(self, observation, headers=None, filename=None, *args, **kwargs):
        camera_event = Event()

        exp_time, file_path, image_id, metadata = self._setup_observation(observation,
                                                                          headers,
                                                                          filename,
                                                                          *args,
                                                                          **kwargs)

        filename = "solved.{}".format(self.file_extension)
        file_path = "{}/pocs/tests/data/{}".format(os.getenv('POCS'), filename)
        exp_time = 5
        self.logger.debug("Trimming camera simulator exposure to 5 s")

        self.take_exposure(seconds=exp_time, filename=file_path, *args, **kwargs)

        # Add most recent exposure to list
        observation.exposure_list[image_id] = file_path

        # Process the image after a set amount of time
        wait_time = exp_time + self.readout_time
        t = Timer(wait_time, self.process_exposure, (metadata, camera_event,))
        t.name = '{}Thread'.format(self.name)
        t.start()

        return camera_event

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False
                      ):
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
        file_path = "{}/pocs/tests/data/{}".format(os.getenv('POCS'), 'unsolved.fits')
        fake_data = fits.getdata(file_path)

        if header['IMAGETYP'] == 'Dark Frame':
            # Replace example data with a bunch of random numbers
            fake_data = np.random.randint(low=975, high=1026,
                                          size=fake_data.shape,
                                          dtype=fake_data.dtype)

        fits_utils.write_fits(fake_data, header, filename, self.logger, exposure_event)
