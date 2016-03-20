import os

from ..utils.database import PanMongo
from ..utils.logger import get_logger
from ..utils import current_time


class WeatherStation(object):

    """ The PANOPTES unit weather station

    This mostly provides convenience methods for querying the weather condition. The
    actual weather sensors run as a separate process from the PANOPTES unit.

    """

    def __init__(self, *args, **kwargs):

        self.logger = get_logger(self)
        self._is_safe = False
        self._translator = {True: 'safe', False: 'unsafe'}
        self.sensors = None

    def is_safe(self):
        """ Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        """
        return self._is_safe

    def check_conditions(self, stale=180):
        """ Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Note:
            `stale` not implemented in the base class.

        Returns:
            str:       String describing state::

                { True: 'safe', False: 'unsafe' }

        """

        return self._translator.get(self.is_safe(), 'unsafe')


class WeatherStationMongo(WeatherStation):

    """
    This object is used to determine the weather safe/unsafe condition.

    Queries a mongodb collection for most recent values.
    """

    def __init__(self, *args, **kwargs):
        ''' Initialize the weather station with a mongodb connection. '''
        super(WeatherStationMongo, self).__init__(*args, **kwargs)

        self.logger.debug("Getting weather station connection to mongodb")
        self._db = PanMongo()
        self._current = self._db.current
        self._archive_col = self._db.weather
        self._current_col = self._db.current

        self.logger.debug("Weather station connection: {}".format(self._current_col))

    def is_safe(self, stale=180):
        ''' Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        '''
        assert self._current_col, self.logger.warning("No connection to sensors, can't check weather safety")

        # Always assume False
        self._is_safe = False
        record = {'safe': False}

        try:
            record = self._current_col.find_one({'type': 'weather'})

            is_safe = record['data'].get('Safe', False)
            self.logger.debug("is_safe: {}".format(is_safe))

            timestamp = record['date']
            self.logger.debug("timestamp: {}".format(timestamp))

            age = (current_time().datetime - timestamp).total_seconds()
            self.logger.debug("age: {} seconds".format(age))

        except:
            self.logger.warning("Weather not safe or no record found in Mongo DB")
            is_safe = False
        else:
            if age > stale:
                self.logger.warning("Weather record looks stale, marking unsafe.")
                is_safe = False
        finally:
            self._is_safe = is_safe

        return self._is_safe


class WeatherStationSimulator(WeatherStation):

    """
    This object simulates safe/unsafe conditions.

    Args:
        simulator(path):    Set this to a file path to manually control safe/unsafe conditions.
            If the file exists, the weather is unsafe.  If the file does not exist, then conditions
            are safe.

    Returns:

    """

    def __init__(self, *args, **kwargs):
        ''' Simulator initializer  '''
        super().__init__(*args, **kwargs)

        if kwargs.get('simulator', None) is not None:
            if os.path.exists(kwargs['simulator']):
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
