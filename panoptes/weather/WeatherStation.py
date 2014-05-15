import os
import datetime

import panoptes.utils.logger as logger

@logger.has_logger
class WeatherStation():
    """
    Main weather station class
    """

    def __init__(self):
        self.logger.info('Starting WeatherStation')
        ## Set up log file for weather telemetry
        self.telemetry_path = os.path.join('/', 'var', 'log', 'PanoptesWeather')
        now = datetime.datetime.now()
        self.telemetry_filename = 'weather_{}.txt'.format(now.strftime('%Y%m%d'))
        if not os.path.exists(self.telemetry_path): os.mkdir(self.telemetry_path)
        self.telemetry_file = os.path.join(self.telemetry_path, self.telemetry_filename)
        
    