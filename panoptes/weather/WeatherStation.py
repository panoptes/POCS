import os
import sys

from datetime import datetime as dt
from datetime import timedelta as tdelta

from panoptes.utils import config, database

class WeatherStation():
    """
    This object is used to determine the weather safe/unsafe condition.  
    """
    def __init__(self):
        ## Set up log file for weather telemetry
        pass


    def check_conditions(self, stale=180):
        '''
        '''
        now = dt.utcnow()
        try:
            sensors = database.PanMongo().sensors
            safe = sensors.find_one( {'type': 'weather', 'status': 'current'} )['data']['Safe']
            timestamp = sensors.find_one( {'type': 'weather', 'status': 'current'} )['date']
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
    tranlator = {True: 'safe', False: 'unsafe'}
    print('Conditions are {}'.format(tranlator[safe]))

