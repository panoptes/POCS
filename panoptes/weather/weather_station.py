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
        self.safe = False
        self.sensors = None

    def check_conditions(self, stale=180):
        ''' Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        '''
        is_safe = false
        return is_safe


class WeatherStationMongo():
    """
    This object is used to determine the weather safe/unsafe condition.

    Queries a mongodb collection for most recent values.
    """

    def __init__(self):
        ''' Initialize the weather station with a mongodb connection. '''
        super().__init__(self)

        self.sensors = database.PanMongo().sensors

    def check_conditions(self, stale=180):
        ''' Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        '''
        assert self.sensors is not None, self.logger.warning("No connection to sensors.")

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

        return is_safe


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
        '''
        Keyword Arguments
        -----------------
        simulator:
        '''
        self.safe = False
        self.simulator = simulator
        self.sensors = None

        if not self.simulator:
            self.sensors = database.PanMongo().sensors

    def check_conditions(self, stale=180):
        '''
        '''
        if self.simulator:
            if os.path.exists(self.simulator):
                safe = False
            else:
                safe = True
        else:
            now = dt.utcnow()
            try:
                safe = self.sensors.find_one({'type': 'weather', 'status': 'current'})[
                    'data']['Safe']
                timestamp = self.sensors.find_one({'type': 'weather', 'status': 'current'})['date']
                age = (now - timestamp).total_seconds()
            except:
                safe = False
            else:
                if age > stale:
                    safe = False

        return safe


if __name__ == '__main__':
    weather = WeatherStation()
    safe = weather.check_conditions()
    translator = {True: 'safe', False: 'unsafe'}
    print('Conditions are {}'.format(translator[safe]))
