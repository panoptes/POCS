import datetime

from camera import AbstractCamera


class Camera(AbstractCamera):

    def __init__(self):
        super().__init__()
        self.logger.info('Setting up simulated camera')
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
        self.logger.info('Connecting to simulated camera')
        self.connected = True
        self.logger.info('Connected')

    def start_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.info('Starting camera cooling')
        self.cooling_started = datetime.datetime.utcnow()
        self.cooling = True
        self.cooled = False
        self.logger.info('Cooling has begun')

    def stop_cooling(self):
        '''
        Cooling for the simluated camera will simply be on a timer.  The camera
        will reach cooled status after a set time period.
        '''
        self.logger.info('Stopping camera cooling')
        self.cooling = False
        self.cooled = False
        self.cooling_started = None
        self.logger.info('Cooling has begun')

    def is_connected(self):
        '''
        '''
        pass

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
