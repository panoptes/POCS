import asyncio

import datetime

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

    def connect(self):
        '''
        '''
        self.connected = True
        self.logger.debug('Connected')

    def take_exposure(self, seconds=1.0):
        """ Take an exposure for given number of seconds """

        self.logger.debug('Taking {} second exposure'.format(seconds))

        return True

    def start_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.debug('Starting camera cooling')
        self.cooling_started = datetime.datetime.utcnow()
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


if __name__ == '__main__':
    simulator = Camera()
    print(simulator.cooling)
