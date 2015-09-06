import os
import sys

from datetime import datetime as dt
from datetime import timedelta as tdelta

from panoptes.utils import config, database

class WeatherStation():
    """
    This object is used to determine the weather safe/unsafe condition.
    """
    def __init__(self, simulator=None):
        '''
        Keyword Arguments
        -----------------
        simulator:
            set this to a file path to manually control safe/unsafe conditions.
            If the file exists, the weather is unsafe.  If the file does not
            exist, then conditions are safe.
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
                safe = self.sensors.find_one( {'type': 'weather', 'status': 'current'} )['data']['Safe']
                timestamp = self.sensors.find_one( {'type': 'weather', 'status': 'current'} )['date']
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
