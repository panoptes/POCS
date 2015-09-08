import os
import sys

from datetime import datetime as dt
from datetime import timedelta as tdelta

from panoptes.utils import config, database


class WeatherStation(object):
    """
    This object is used to determine the weather safe/unsafe condition.
    """

    def __init__(self):
        '''
        '''
        self._is_safe = False
        self._sensors = None
        self._translator = {True: 'safe', False: 'unsafe'}

    def is_safe(self):
        """ Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        """
        return self._is_safe

    def check_condition(self, stale=180):
        """ Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Note:
            `stale` not implemented in the base class.

        Returns:
            str:       String describing state::

                { True: 'safe', False: 'unsafe' }

        """

        return self._translator.get(self._is_safe, 'unsafe')


class WeatherStationMongo():
    """
    This object is used to determine the weather safe/unsafe condition.

    Queries a mongodb collection for most recent values.
    """

    def __init__(self):
        ''' Initialize the weather station with a mongodb connection. '''
        super().__init__(self)

        self._sensors = database.PanMongo().sensors

    def is_safe(self, stale=180):
        ''' Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        '''
        assert self._sensors is not None, self.logger.warning("No connection to sensors.")

        is_safe = False
        now = dt.utcnow()
        try:
            is_safe = self.sensors.find_one({'type': 'weather', 'status': 'current'})[
                'data']['Safe']
            timestamp = self.sensors.find_one({'type': 'weather', 'status': 'current'})['date']
            age = (now - timestamp).total_seconds()
        except:
            is_safe = False
        else:
            if age > stale:
                is_safe = False

        self._is_safe = is_safe


class WeatherStationSimulator(WeatherStation):
    """
    This object simulates safe/unsafe conditions.

    Args:
        simulator(path):    Set this to a file path to manually control safe/unsafe conditions.
            If the file exists, the weather is unsafe.  If the file does not exist, then conditions
            are safe.

    Returns:

    """

    def __init__(self, simulator=None):
        ''' Simulator initializer  '''
        self._is_safe = False
        self._sensors = None

        if simulator is not None:
            if os.path.exists(simulator):
                self._is_safe = False
            else:
                self._is_safe = True


    def set_safe(self):
        """ Sets the simulator to safe weather """
        self._is_safe = True

    def set_unsafe(self):
        """ Sets the simulator to unsafe weather """
        self._is_safe = False

    def is_safe(self, stale=180):
        ''' Simulator simply returns the `self._is_safe` param '''
        return self._is_safe


if __name__ == '__main__':
    weather = WeatherStationMongo()
    safe = weather.check_conditions()
    translator = {True: 'safe', False: 'unsafe'}
    print('Conditions are {}'.format(translator[safe]))
