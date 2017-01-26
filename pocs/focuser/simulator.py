from .. import PanBase
from .focuser import AbstractFocuser

import time


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
        self.connect()
        self.logger.info("\t\t\t {} initialised".format(self))

##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """
        Simulator pretends to connect a focuser and obtain details, current state.
        """
        time.sleep(1)
        self._connected = True
        self._serial_number = 'SF9999'
        self._position = 0
        self.logger.debug("Connected to focuser {}".format(self.uid))

    def move_to(self, position):
        """ Move focuser to a new encorder position """
        self.logger.debug('Moving focuser {} to {}'.format(self.uid, position))
        time.sleep(1)
        self._position = position

    def move_by(self, increment):
        """ Move focuser by a given amount """
        self.logger.debug('Moving focuser {} by {}'.format(self.uid, increment))
        time.sleep(1)
        self._position += increment
