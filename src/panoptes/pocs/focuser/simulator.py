from panoptes.pocs.focuser import AbstractFocuser

import time
import random


class Focuser(AbstractFocuser):
    """
    Simple focuser simulator
    """

    def __init__(self,
                 name='Simulated Focuser',
                 port='/dev/ttyFAKE',
                 *args, **kwargs):
        super().__init__(*args, name=name, port=port, **kwargs)
        self.logger.debug("Initialising simulator focuser")
        self._is_moving = False
        self.connect()
        self.logger.info("{} initialised".format(self))

##################################################################################################
# Properties
##################################################################################################

    @property
    def min_position(self):
        """
        Returns position of close limit of focus travel, in encoder units
        """
        return self._min_position

    @property
    def max_position(self):
        """
        Returns position of far limit of focus travel, in encoder units
        """
        return self._max_position

    @property
    def is_moving(self):
        return self._is_moving

##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """
        Simulator pretends to connect a focuser and obtain details, current state.
        """
        time.sleep(0.1)
        self._connected = True
        self._serial_number = 'SF{:04d}'.format(random.randint(0, 9999))
        self._min_position = 0
        self._max_position = 22200
        if self.position is None:
            self._position = random.randint(0, self._max_position)
        self.logger.debug("Connected to focuser {}".format(self.uid))

    def move_to(self, position):
        """ Move focuser to a new encorder position """
        self.move_by(position - self.position)
        return self.position

    def move_by(self, increment):
        """ Move focuser by a given amount """
        self.logger.debug('Moving focuser {} by {}'.format(self.uid, increment))
        self._is_moving = True
        time.sleep(1)
        previous_position = self._position
        position = previous_position + int(increment)
        position = min(position, self.max_position)
        position = max(position, self.min_position)
        self._position = position
        self._is_moving = False
        return position - previous_position
