import asyncio
import os

from astropy import units as u

from .camera import AbstractCamera


class Camera(AbstractCamera):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.debug("Initializing simulator camera")

        self._loop = asyncio.get_event_loop()
        self._loop_delay = kwargs.get('loop_delay', 5.0)

        # Simulator
        self._serial_number = '999999'
        self._file_num = 0

    @property
    def uid(self):
        """ Return a unique id for the camera

        This returns the first six digits of the unique serial number

        Returns:
            int:    Unique hardware id for camera
        """
        return self._serial_number[0:6]

    def connect(self):
        """ Connect to camera simulator

        The simulator merely markes the `connected` property.
        """
        self._connected = True
        self.logger.debug('Connected')

    def construct_filename(self):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera

        Returns:
            str:    Filename format
        """
        self._file_num = self._file_num + 1

        filename = os.path.join(self._image_dir, self._serial_number, '{:03d}.cr2'.format(self._file_num))

        return filename

    def take_exposure(self, seconds=1.0 * u.second, filename=None):
        """ Take an exposure for given number of seconds """

        self.logger.debug('Taking {} second exposure'.format(seconds))

        if filename is None:
            filename = self.construct_filename()

        return filename
