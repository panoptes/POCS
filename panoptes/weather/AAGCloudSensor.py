#!/usr/bin/env python

import datetime
import os
import sys
import serial
import re
import time
import argparse
import math
import numpy as np

import astropy.units as u
import astropy.table as table
import astropy.io.ascii as ascii

from panoptes.utils import logger
from panoptes.weather import WeatherStation


@logger.has_logger
class AAGCloudSensor(WeatherStation.WeatherStation):
    '''
    This class is for the AAG Cloud Sensor device which can be communicated with
    via serial commands.

    http://www.aagware.eu/aag/cloudwatcherNetwork/TechInfo/Rs232_Comms_v100.pdf
    http://www.aagware.eu/aag/cloudwatcherNetwork/TechInfo/Rs232_Comms_v110.pdf
    http://www.aagware.eu/aag/cloudwatcherNetwork/TechInfo/Rs232_Comms_v120.pdf

    Command List (from Rs232_Comms_v100.pdf)
    !A = Get internal name (recieves 2 blocks)
    !B = Get firmware version (recieves 2 blocks)
    !C = Get values (recieves 5 blocks)
         Zener voltage, Ambient Temperature, Ambient Temperature, Rain Sensor Temperature, HSB
    !D = Get internal errors (recieves 5 blocks)
    !E = Get rain frequency (recieves 2 blocks)
    !F = Get switch status (recieves 2 blocks)
    !G = Set switch open (recieves 2 blocks)
    !H = Set switch closed (recieves 2 blocks)
    !Pxxxx = Set PWM value to xxxx (recieves 2 blocks)
    !Q = Get PWM value (recieves 2 blocks)
    !S = Get sky IR temperature (recieves 2 blocks)
    !T = Get sensor temperature (recieves 2 blocks)
    !z = Reset RS232 buffer pointers (recieves 1 blocks)
    !K = Get serial number (recieves 2 blocks)

    Return Codes
    '1 '    Infra red temperature in hundredth of degree Celsius
    '2 '    Infra red sensor temperature in hundredth of degree Celsius
    '3 '    Analog0 output 0-1023 => 0 to full voltage (Ambient Temp NTC)
    '4 '    Analog2 output 0-1023 => 0 to full voltage (LDR ambient light)
    '5 '    Analog3 output 0-1023 => 0 to full voltage (Rain Sensor Temp NTC)
    '6 '    Analog3 output 0-1023 => 0 to full voltage (Zener Voltage reference)
    'E1'    Number of internal errors reading infra red sensor: 1st address byte
    'E2'    Number of internal errors reading infra red sensor: command byte
    'E3'    Number of internal errors reading infra red sensor: 2nd address byte
    'E4'    Number of internal errors reading infra red sensor: PEC byte NB: the error counters are reset after being read.
    'N '    Internal Name
    'V '    Firmware Version number
    'Q '    PWM duty cycle
    'R '    Rain frequency counter
    'X '    Switch Opened
    'Y '    Switch Closed
    '''

    def __init__(self, serial_address='/dev/ttyS0'):
        super().__init__()
        ## Initialize Serial Connection
        self.logger.debug('Using serial address: {}'.format(serial_address))
        if serial_address:
            self.logger.info('Connecting to AAG Cloud Sensor')
            try:
                self.AAG = serial.Serial(serial_address, 9600, timeout=2)
                self.logger.info("Connected to Cloud Sensor on {}".format(serial_address))
            except OSError as e:
                self.logger.error('Unable to connect to AAG Cloud Sensor')
                self.logger.error('  {}'.format(e.errno))
                self.logger.error('  {}'.format(e.strerror))
                self.AAG = None
            except:
                self.logger.error("Unable to connect to AAG Cloud Sensor")
                self.AAG = None
        else:
            self.AAG = None
        ## Initialize Values
        self.last_update = None
        self.safe = None
        self.ambient_temp = None
        self.sky_temp = None
        self.wind_speed = None
        self.internal_voltage = None
        self.LDR_resistance = None
        self.rain_sensor_temp = None
        self.PWM = None
        self.errors = None
        self.switch = None
        ## Table Info (add custom dtypes to values in WeatherStation class)
        self.table_dtypes['Ambient Temperature'] = 'f4'
        self.table_dtypes['Sky Temperature'] = 'f4'
        self.table_dtypes['Rain Frequency'] = 'f4'
        self.table_dtypes['Wind Speed'] = 'f4'
        self.table_dtypes['Internal Voltage'] = 'f4'
        self.table_dtypes['LDR Resistance'] = 'f4'
        self.table_dtypes['Rain Sensor Temperature'] = 'f4'
        self.table_dtypes['PWM'] = 'f4'
        self.table_dtypes['E1'] = 'i4'
        self.table_dtypes['E2'] = 'i4'
        self.table_dtypes['E3'] = 'i4'
        self.table_dtypes['E4'] = 'i4'
        self.table_dtypes['Switch'] = 'S6'
        ## Command Translation
        self.commands = {'!A': 'Get internal name',
                         '!B': 'Get firmware version',
                         '!C': 'Get values',
                         '!D': 'Get internal errors',
                         '!E': 'Get rain frequency',
                         '!F': 'Get switch status',
                         '!G': 'Set switch open',
                         '!H': 'Set switch closed',
                         '!Q': 'Get PWM value',
                         '!S': 'Get sky IR temperature',
                         '!T': 'Get sensor temperature',
                         '!z': 'Reset RS232 buffer pointers',
                         '!K': 'Get serial number',
                         'v!': 'Query if anemometer enabled',
                         'V!': 'Get wind speed',
                         '!Pxxxx': 'Set PWM value to xxxx',
                         }
        self.expects = {'!A': '!N\s+(\w+)!',
                        '!B': '!V\s+([\d\.\-]+)!',
                        '!C': '!6\s+([\d\.\-]+)!4\s+([\d\.\-]+)!5\s+([\d\.\-]+)!',
                        '!D': '!E1\s+([\d\.]+)!E2\s+([\d\.]+)!E3\s+([\d\.]+)!E4\s+([\d\.]+)!',
                        '!E': '!R\s+([\d\.\-]+)!',
                        '!F': '!Y\s+([\d\.\-]+)!',
                        '!Q': '!Q\s+([\d\.\-]+)!',
                        '!S': '!1\s+([\d\.\-]+)!',
                        '!T': '!2\s+([\d\.\-]+)!',
                        '!K': '!K(\d+)\s*\\x00!',
                        'v!': '!v\s+([\d\.\-]+)!',
                        'V!': '!w\s+([\d\.\-]+)!',
                        }
        self.delays = {'!A': 0.100,
                       '!B': 0.100,
                       '!C': 0.100,
                       '!D': 0.100,
                       '!E': 0.350,
                       '!F': 0.100,
                       '!Q': 0.100,
                       '!S': 0.100,
                       '!T': 0.100,
                       '!K': 0.100,
                       'v!': 0.100,
                       'V!': 0.100,
                       }
        if self.AAG:
            ## Query Device Name
            result = self.query('!A')
            if result:
                self.name = result[0].strip()
            else:
                self.name = ''
            self.logger.info('Device Name is "{}"'.format(self.name))
            ## Query Firmware Version
            result = self.query('!B')
            if result:
                self.firmware_version = result[0].strip()
            else:
                self.firmware_version = ''
            self.logger.info('Firmware Version = {}'.format(self.firmware_version))
            ## Query Serial Number
            result = self.query('!K')
            if result:
                self.serial_number = result[0].strip()
            else:
                self.serial_number = ''
            self.logger.info('Serial Number: {}'.format(self.serial_number))



    def send(self, send, delay=0.100):
        if send in self.commands.keys():
            self.logger.info('Sending command: {}'.format(self.commands[send]))
        else:
            self.logger.warning('Unknown command: "{}"'.format(send))
            return None

        self.logger.debug('  Clearing buffer')
        cleared = self.AAG.read(self.AAG.inWaiting())
        if len(cleared) > 0:
            self.logger.debug('  Cleared: "{}"'.format(cleared.decode('utf-8')))

        self.AAG.write(send.encode('utf-8'))
        time.sleep(delay)
        response = self.AAG.read(self.AAG.inWaiting()).decode('utf-8')
        self.logger.debug('  Response: "{}"'.format(response))
        ResponseMatch = re.match('(!.*)\\x11\s{12}0', response)
        if ResponseMatch:
            result = ResponseMatch.group(1)
        else:
            result = response

        return result


    def query(self, send, maxtries=5):
        if not send in self.expects.keys():
            self.logger.warning('Unknown query: "{}"'.format(send))
            return None
        delay = self.delays[send]
        expect = self.expects[send]
        count = 0
        while count <= maxtries:
            count += 1
            result = self.send(send, delay=delay)

            MatchExpect = re.match(expect, result)
            if not MatchExpect:
                self.logger.debug('Did not find {} in response "{}"'.format(expect, result))
                result = None
            else:
                self.logger.debug('Found {} in response "{}"'.format(expect, result))
                result = MatchExpect.groups()
                break
        return result


    def get_ambient_temperature(self, n=5):
        '''
        Populates the self.ambient_temp property
        
        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 5.
        '''
        values = []
        for i in range(0,n):
            value = float(self.query('!T')[0])/100.
            self.logger.debug('  Ambient Temperature Query = {:.1f}'.format(value))
            values.append(value)
        if len(values) >= n-1:
            self.ambient_temp = np.median(values)*u.Celsius
        else:
            self.ambient_temp = None
        self.logger.info('Ambient Temperature = {:.1f}'.format(self.ambient_temp))
        return self.ambient_temp


    def get_sky_temperature(self, n=5):
        '''
        Populates the self.sky_temp property
        
        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 1.
        
        Does this n times as recommended by the "Communication operational 
        recommendations" section in Rs232_Comms_v100.pdf
        '''
        values = []
        for i in range(0,n):
            value = float(self.query('!S')[0])/100.
            self.logger.debug('  Sky Temperature Query = {:.1f}'.format(value))
            values.append(value)
        if len(values) >= n-1:
            self.sky_temp = np.median(values)*u.Celsius
        else:
            self.sky_temp = None
        self.logger.info('Sky Temperature = {:.1f}'.format(self.sky_temp))
        return self.sky_temp


    def get_values(self, n=5):
        '''
        Populates the self.internal_voltage, self.LDR_resistance, and 
        self.rain_sensor_temp properties
        
        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" items 4, 6, 7.
        '''
        ZenerConstant = 3
        LDRPullupResistance = 56.
        RainPullUpResistance = 1
        RainResAt25 = 1
        RainBeta = 3450.
        ABSZERO = 273.15
        internal_voltages = []
        LDR_resistances = []
        rain_sensor_temps = []
        for i in range(0,5,1):
            responses = self.query('!C')
            if responses:
                internal_voltage = 1023 * ZenerConstant / float(responses[0])
                internal_voltages.append(internal_voltage)
                LDR_resistance = LDRPullupResistance / ((1023. / float(responses[1])) - 1.)
                LDR_resistances.append(LDR_resistance)
                r = math.log(RainPullUpResistance / ((1023. / float(responses[2])) - 1.) / RainResAt25)
                rain_sensor_temp = 1. / (r / RainBeta + 1. / (ABSZERO + 25.)) - ABSZERO
                rain_sensor_temps.append(rain_sensor_temp)

        ## Median Results
        if len(internal_voltages) >= n-1:
            self.internal_voltage = np.median(internal_voltages) * u.volt
            self.logger.info('Internal Voltage = {}'.format(self.internal_voltage))
        else:
            self.internal_voltage = None
        if len(LDR_resistances) >= n-1:
            self.LDR_resistance = np.median(LDR_resistances) * 1000. * u.ohm
            self.logger.info('LDR Resistance = {}'.format(self.LDR_resistance))
        else:
            self.LDR_resistance = None
        if len(rain_sensor_temps) >= n-1:
            self.rain_sensor_temp = np.median(rain_sensor_temps) * u.Celsius
            self.logger.info('Rain Sensor Temp = {}'.format(self.rain_sensor_temp))
        else:
            self.rain_sensor_temp = None

        return (self.internal_voltage, self.LDR_resistance, self.rain_sensor_temp)


    def get_rain_frequency(self, n=5):
        '''
        Populates the self.rain_frequency property
        '''
        values = []
        for i in range(0,n):
            value = float(self.query('!E')[0]) * 100. / 1023.
            self.logger.debug('  Rain Freq Query = {:.1f}'.format(value))
            values.append(value)
        if len(values) >= n-1:
            self.rain_frequency = np.median(values)
        else:
            self.rain_frequency = None
        self.logger.info('Rain Frequency = {:.1f}'.format(self.rain_frequency))
        return self.rain_frequency


    def get_PWM(self):
        '''
        Populates the self.PWM property.
        
        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 3.
        '''
        value = self.query('!Q')[0]
        self.PWM = float(value) * 100. / 1023.
        self.logger.info('PWM Value = {:.1f}'.format(self.PWM))
        return self.PWM


    def get_errors(self):
        '''
        Populates the self.IR_errors property
        '''
        response = self.query('!D')
        if response:
            self.errors = {'!E1': str(int(response[0])),
                           '!E2': str(int(response[1])),
                           '!E3': str(int(response[2])),
                           '!E4': str(int(response[3])) }
            self.logger.info("Internal Error 1: '{}'".format(self.errors['!E1']))
            self.logger.info("Internal Error 2: '{}'".format(self.errors['!E2']))
            self.logger.info("Internal Error 3: '{}'".format(self.errors['!E3']))
            self.logger.info("Internal Error 4: '{}'".format(self.errors['!E4']))
        else:
            self.errors = {'!E1': None,
                           '!E2': None,
                           '!E3': None,
                           '!E4': None }
        return self.errors


    def get_switch(self, maxtries=3):
        '''
        Populates the self.switch property
        
        Unlike other queries, this method has to check if the return matches a
        !X or !Y pattern (indicating open and closed respectively) rather than
        read a value.
        '''
        self.switch = None
        tries = 0
        status = None
        while not status:
            tries += 1
            response = self.send('!F')
            if re.match('!Y            1!', response):
                status = 'OPEN'
            elif re.match('!X            1!', response):
                status = 'CLOSED'
            else:
                status = None
            if not status and tries >= maxtries:
                status = 'UNKNOWN'
        self.switch = status
        self.logger.info('Switch Status = {}'.format(self.switch))
        return self.switch


    def wind_speed_enabled(self, maxtries=3):
        '''
        Method returns true or false depending on whether the device supports
        wind speed measurements.
        '''
        enabled = bool(self.query('v!')[0])
        if enabled:
            self.logger.debug('Anemometer enabled')
        else:
            self.logger.debug('Anemometer not enabled')
        return enabled


    def get_wind_speed(self, n=9):
        '''
        Populates the self.wind_speed property
        
        Based on the information in Rs232_Comms_v120.pdf document
        
        Medians 5 measurements.  This isn't mentioned specifically by the manual
        but I'm guessing it won't hurt.
        '''
        if self.wind_speed_enabled():
            values = []
            for i in range(0,n):
                result = self.query('V!')
                if result:
                    value = float(result[0])
                    self.logger.debug('  Ambient Temperature Query = {:.1f}'.format(value))
                    values.append(value)
            if len(values) >= 3:
                self.wind_speed = np.median(values)*u.km/u.hr
                self.logger.info('Wind speed = {:.1f}'.format(self.wind_speed))
            else:
                self.wind_speed = None
        else:
            self.wind_speed = None
        return self.wind_speed


    def update_weather(self, update_mongo=True):
        '''
        Queries the values for writing to the telemetry file.
        '''
        data = {}
        if self.get_sky_temperature():
            data['Sky Temperature (C)'] = self.sky_temp.value
        if self.get_ambient_temperature():
            data['Ambient Temperature (C)'] = self.ambient_temp.value
        if self.get_values():
            data['Internal Voltage (V)'] = self.internal_voltage.value
            data['LDR Resistance (ohm)'] = self.LDR_resistance.value
            data['Rain Sensor Temp (C)'] = self.rain_sensor_temp.value
        if self.get_rain_frequency():
            data['Rain Frequency'] = self.rain_frequency
        if self.get_PWM():
            data['PWM Value'] = self.PWM
        if self.get_errors():
            data['Errors'] = self.errors
        if self.get_switch():
            data['Switch Status'] = self.switch
        if self.get_wind_speed():
            data['Wind Speed (km/h)'] = self.wind_speed.value
        ## Make Safety Decision
        data['Safe'] = self.make_safety_decision(data)

        if update_mongo:
            try:
                from panoptes.utils import config, logger, database
                # Connect to sensors collection
                sensors = database.PanMongo().sensors
                sensors.insert({
                    "time": datetime.datetime.utcnow(),
                    "type": "environment",
                    "data": data
                })
            except:
                print('Failed to update mongo database')
        else:
            for key in data.keys():
                print('{:>26s}: {}'.format(key, data[key]))

        return self.safe


    def make_safety_decision(self, data):
        '''
        Method makes decision whether conditions are safe or unsafe.
        '''
        self.safe = 'UNSAFE'
        return self.safe


if __name__ == '__main__':
    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = argparse.ArgumentParser(
             description="Program description.")
    ## add flags
#     parser.add_argument("-p", "--plot",
#         action="store_true", dest="plot",
#         default=False, help="Plot the data instead of querying new values.")
    ## add arguments
    parser.add_argument("--dev",
        type=str, dest="device",
        default='/dev/ttyUSB0',
        help="Device address for the weather station (default = /dev/ttyUSB0)")
    parser.add_argument("--interval",
        type=float, dest="interval",
        default=30.,
        help="Time (in seconds) to wait between queries (default = 30 s)")

    args = parser.parse_args()


    ##-------------------------------------------------------------------------
    ## Update Weather Telemetry
    ##-------------------------------------------------------------------------
    AAG = AAGCloudSensor(serial_address=args.device)
    while True:
        AAG.update_weather(update_mongo=False)
        time.sleep(args.interval)
