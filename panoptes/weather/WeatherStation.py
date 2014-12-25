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
    This object is used to determine the weather safe/unsafe condition.  It
    reads a simple text file written by the program for the particular type of
    weather station.
    """
    def __init__(self):
        ## Set up log file for weather telemetry
        self.telemetry_path = os.path.join('/', 'var', 'panoptes', 'logs', 'PanoptesWeather')
        if not os.path.exists(self.telemetry_path): os.mkdir(self.telemetry_path)
        self.update_logfiles()
        self.table_dtypes = {'Timestamp': 'S22',
                             'Safe': 'S6'}


    def update_logfiles(self):
        '''
        Check the UT date and re-define the filenames for the telemetry and
        conditions fies based on today's UT date.
        '''
        now = datetime.datetime.utcnow()
        self.condition_filename = 'condition_{}UT.txt'.format(now.strftime('%Y%m%d'))
        self.condition_file = os.path.join(self.telemetry_path, self.condition_filename)
        self.telemetry_filename = 'telemetry_{}UT.txt'.format(now.strftime('%Y%m%d'))
        self.telemetry_file = os.path.join(self.telemetry_path, self.telemetry_filename)


    def check_conditions(self, stale=180):
        '''
        Read the conditions file and populate the safe property with True or
        False based on the latest datum.
        '''
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
            self.safe = False
        else:
            if safe_string == 'SAFE':
                self.logger.info('Weather is SAFE (data is {:.1f} seconds old)'.format(dt.total_seconds()))
                self.safe = True
            elif safe_string == 'UNSAFE':
                self.logger.info('Weather is UNSAFE (data is {:.1f} seconds old)'.format(dt.total_seconds()))
                self.safe = False
            else:
                self.logger.warning('Weather telemetry not parsed')
                self.safe = None



if __name__ == '__main__':
    weather = WeatherStation()
    weather.check_conditions()

