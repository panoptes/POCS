import os
import random

from threading import Event
from threading import Timer

import numpy as np

from astropy import units as u
from astropy.io import fits
from astropy.time import Time

from pocs.utils import current_time

from pocs.camera import AbstractCamera


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

    def take_observation(self, observation, headers=None, **kwargs):
        camera_event = Event()

        if headers is None:
            headers = {}

        start_time = headers.get('start_time', current_time(flatten=True))

        filename = "solved.{}".format(self.file_extension)

        file_path = "{}/pocs/tests/data/{}".format(os.getenv('POCS'), filename)

        image_id = '{}_{}_{}'.format(
            self.config['name'],
            self.uid,
            start_time
        )
        self.logger.debug("image_id: {}".format(image_id))

        sequence_id = '{}_{}_{}'.format(
            self.config['name'],
            self.uid,
            observation.seq_time
        )

        # Camera metadata
        metadata = {
            'camera_name': self.name,
            'camera_uid': self.uid,
            'field_name': observation.field.field_name,
            'file_path': file_path,
            'filter': self.filter_type,
            'image_id': image_id,
            'is_primary': self.is_primary,
            'sequence_id': sequence_id,
            'start_time': start_time,
        }
        metadata.update(headers)
        exp_time = kwargs.get('exp_time', observation.exp_time.value)

        exp_time = 5
        self.logger.debug("Trimming camera simulator exposure to 5 s")

        self.take_exposure(seconds=exp_time, filename=file_path)

        # Add most recent exposure to list
        observation.exposure_list[image_id] = file_path.replace('.cr2', '.fits')

        # Process the image after a set amount of time
        wait_time = exp_time + self.readout_time
        t = Timer(wait_time, self.process_exposure, (metadata, camera_event,))
        t.name = '{}Thread'.format(self.name)
        t.start()

        return camera_event

    def take_exposure(self, seconds=1.0 * u.second, filename=None, dark=False, blocking=False):
        """ Take an exposure for given number of seconds """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        if isinstance(seconds, u.Quantity):
            seconds = seconds.to(u.second)
            seconds = seconds.value

        self.logger.debug(
            'Taking {} second exposure on {}: {}'.format(
                seconds, self.name, filename))

        # Set up a Timer that will wait for the duration of the exposure then
        # copy a dummy FITS file to the specified path and adjust the headers
        # according to the exposure time, type.
        start_time = Time.now()
        exposure_event = Event()
        exposure_thread = Timer(interval=seconds,
                                function=self._fake_exposure,
                                args=[seconds, start_time, filename, exposure_event, dark])
        exposure_thread.start()

        if blocking:
            exposure_event.wait()

        return exposure_event

    def process_exposure(self, info, signal_event):
        """Processes the exposure

        Args:
            info (dict): Header metadata saved for the image
            signal_event (threading.Event): An event that is set signifying that the
                camera is done with this exposure
        """
        image_id = info['image_id']
        file_path = info['file_path']
        self.logger.debug("Processing {} {}".format(image_id, file_path))

        self.logger.debug("Adding image metadata to db: {}".format(image_id))
        self.db.insert_current('observations', info)

        # Mark the event as done
        signal_event.set()

    def _fake_exposure(self, seconds, start_time, filename, exposure_event, dark):
        # Get example FITS file from test data directory
        file_path = "{}/pocs/tests/data/{}".format(os.getenv('POCS'), 'unsolved.fits')
        hdu_list = fits.open(file_path)

        # Modify headers to roughly reflect requested exposure
        hdu_list[0].header.set('INSTRUME', self.uid)
        hdu_list[0].header.set('DATE-OBS', start_time.fits)
        hdu_list[0].header.set('EXPTIME', seconds, 'Seconds')
        if dark:
            hdu_list[0].header.set('IMAGETYP', 'Dark Frame')
            fake_data = np.random.randint(low=975, high=1026,
                                          size=hdu_list[0].data.shape,
                                          dtype=hdu_list[0].data.dtype)
            hdu_list[0].data = fake_data
        else:
            hdu_list[0].header.set('IMAGETYP', 'Light Frame')

        # Write FITS file to requested location
        if os.path.dirname(filename):
            os.makedirs(os.path.dirname(filename), mode=0o775, exist_ok=True)

        try:
            hdu_list.writeto(filename)
        except OSError:
            pass

        # Set event to mark exposure complete.
        exposure_event.set()
