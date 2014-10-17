import datetime
import os
import sys
import serial
import re
import time
import math
import numpy as np

import astropy.units as u
import astropy.table as table
import astropy.io.ascii as ascii

from panoptes.utils import logger
from panoptes.weather import WeatherStation


@logger.has_logger
class Simulator(WeatherStation.WeatherStation):
    def __init__(self):
        super().__init__()
        self.logger.info('Connecting to simulated weather station')
        self.last_update = None
        self.safe = None


    def make_safety_decision(self):
        '''
        Method makes decision whether conditions are safe or unsafe.
        '''
        self.last_update = datetime.datetime.utcnow()
        self.safe = 'SAFE'


    def update_telemetry_files(self):
        '''
        Updates the conditions telemetry file.
        '''
        ## First, write file with only timestamp and SAFE/UNSAFE condition
        if os.path.exists(self.condition_file):
            self.logger.debug('Opening prior conditions file: {}'.format(self.condition_file))
            conditions = ascii.read(self.condition_file, guess=True,
                                         format='basic',
                                         converters={'Timestamp': [ascii.convert_numpy(self.table_dtypes['Timestamp'])],
                                                     'Safe': [ascii.convert_numpy(self.table_dtypes['Safe'])]}
                                        )
        else:
            self.logger.debug('No prior conditions file found.  Generating new table.')
            conditions = table.Table(names=('Timestamp', 'Safe'), dtype=(self.table_dtypes['Timestamp'], self.table_dtypes['Safe']))
        new_row = {'Timestamp': self.last_update.strftime('%Y/%m/%d %H:%M:%S UT'),
                   'Safe': self.safe}
        self.logger.debug('Adding new row to table')
        conditions.add_row(new_row)
        self.logger.debug('Writing modified table to: {}'.format(self.condition_file))
        ascii.write(conditions, self.condition_file, format='basic')


if __name__ == '__main__':
    simulator = Simulator()
    simulator.make_safety_decision()
    simulator.update_telemetry_files()

