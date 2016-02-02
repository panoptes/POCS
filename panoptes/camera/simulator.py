import os
import asyncio

from astropy import units as u

from ..utils import current_time
from .camera import AbstractCamera


class Camera(AbstractCamera):

    def __init__(self, config, **kwargs):
        super().__init__(config)

        self._loop = asyncio.get_event_loop()
        self._loop_delay = kwargs.get('loop_delay', 5.0)

        self.logger.info('\t\t Using simulator camera')
        # Properties for all cameras
        self.connected = False
        self.cooling = None
        self.cooled = None
        self.exposing = None
        # Properties for simulator only
        self.cooling_started = None
        self._serial_number = config.get('uid', 'SIMULATOR')

        self._file_num = 0

    @property
    def uid(self):
        return self._serial_number[0:6]

    def connect(self):
        '''
        '''
        self.connected = True
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

    def start_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.debug('Starting camera cooling')
        self.cooling_started = current_time()
        self.cooling = True
        self.cooled = False
        self.logger.debug('Cooling has begun')

    def stop_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.debug('Stopping camera cooling')
        self.cooling = False
        self.cooled = False
        self.cooling_started = None
        self.logger.debug('Cooling has begun')

    def is_connected(self):
        '''
        '''
        pass

    # -------------------------------------------------------------------------
    # Query/Update Methods
    # -------------------------------------------------------------------------
    def is_cooling(self):
        '''
        '''
        pass

    def is_cooled(self):
        '''
        '''
        pass

    def is_exposing(self):
        '''
        '''
        pass
