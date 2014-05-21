import datetime
import os
import sys
import re

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
        self.update_logfile()


    def update_logfile(self):
        now = datetime.datetime.utcnow()
        self.telemetry_filename = 'weather_{}UT.txt'.format(now.strftime('%Y%m%d'))
        self.telemetry_file = os.path.join(self.telemetry_path, self.telemetry_filename)


    def is_safe(self, stale=180):
        with open(self.telemetry_file, 'r') as telemetryFO:
            lines = telemetryFO.readlines()
        last_line = lines[-1]
        timestamp = datetime.datetime.strptime(last_line[0:22], '%Y/%m/%d %H:%M:%S UT')
        now = datetime.datetime.utcnow()
        dt = now - timestamp
        if dt.total_seconds() > stale:
            self.logger.warning('Weather data is stale by {:.1f} seconds'.format(dt.total_seconds()))
            return False
        else:
            MatchSafe = re.match('\s{3}SAFE', last_line[22:])
            MatchUnSafe = re.match('\sUNSAFE', last_line[22:])
            if MatchSafe:
                self.logger.info('Weather is SAFE (data is {:.1f} seconds old)'.format(dt.total_seconds()))
                return True
            elif MatchUnSafe:
                self.logger.info('Weather is UNSAFE (data is {:.1f} seconds old)'.format(dt.total_seconds()))
                return False
            else:
                self.logger.warning('Weather telemetry not parsed')
                return False


if __name__ == '__main__':
    weather = WeatherStation()
    weather.is_safe()

