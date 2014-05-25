import datetime
import os
import sys
import re

from astropy.io import ascii
import astropy.table as table

from panoptes.utils import logger


@logger.has_logger
class WeatherStation():
    """
    Main weather station class
    """

    def __init__(self):
        ## Set up log file for weather telemetry
        self.telemetry_path = os.path.join('/', 'var', 'log', 'PanoptesWeather')
        if not os.path.exists(self.telemetry_path): os.mkdir(self.telemetry_path)
        self.update_logfiles()
        self.table_dtypes = {'Timestamp': 'S22',
                             'Safe': 'S6'}


    def update_logfiles(self):
        now = datetime.datetime.utcnow()
        self.condition_filename = 'condition_{}UT.txt'.format(now.strftime('%Y%m%d'))
        self.condition_file = os.path.join(self.telemetry_path, self.condition_filename)
        self.telemetry_filename = 'telemetry_{}UT.txt'.format(now.strftime('%Y%m%d'))
        self.telemetry_file = os.path.join(self.telemetry_path, self.telemetry_filename)


    def is_safe(self, stale=180):
        self.logger.debug('Opening conditions file: {}'.format(self.condition_file))
        conditions = ascii.read(self.condition_file, guess=True,
                                     format='basic',
                                     converters={'Timestamp': [ascii.convert_numpy(self.table_dtypes['Timestamp'])],
                                                 'Safe': [ascii.convert_numpy(self.table_dtypes['Safe'])]}
                                    )
        last_entry = conditions[-1]
        time_string = last_entry['Timestamp'].decode("utf-8")
        safe_string = last_entry['Safe'].decode("utf-8")
        timestamp = datetime.datetime.strptime(time_string, '%Y/%m/%d %H:%M:%S UT')
        now = datetime.datetime.utcnow()
        dt = now - timestamp
        if dt.total_seconds() > stale:
            self.logger.warning('Weather data is stale by {:.1f} seconds'.format(dt.total_seconds()))
            return False
        else:
            if safe_string == 'SAFE':
                self.logger.info('Weather is SAFE (data is {:.1f} seconds old)'.format(dt.total_seconds()))
                return True
            elif safe_string == 'UNSAFE':
                self.logger.info('Weather is UNSAFE (data is {:.1f} seconds old)'.format(dt.total_seconds()))
                return False
            else:
                self.logger.warning('Weather telemetry not parsed')
                return None



if __name__ == '__main__':
    weather = WeatherStation()
    weather.is_safe()

