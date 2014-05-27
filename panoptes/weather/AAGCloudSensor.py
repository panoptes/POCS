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
#         WeatherStation.WeatherStation.__init__(self)
        ## Initialize Serial Connection
        self.logger.debug('Using serial address: {}'.format(serial_address))
        self.logger.info('Connecting to AAG Cloud Sensor')
        try:
            self.AAG = serial.Serial(serial_address, 9600, timeout=2)
            self.logger.info("Connected to Cloud Sensor on {}".format(serial_address))
        except:
            self.logger.error("Unable to connect to AAG Cloud Sensor")
            self.AAG = None
            raise
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
        self.table_dtypes['Wind Speed'] = 'f4'
        self.table_dtypes['Internal Voltage'] = 'f4'
        self.table_dtypes['LDR Resistance'] = 'f4'
        self.table_dtypes['Rain Sensor Temperature'] = 'f4'
        self.table_dtypes['PWM'] = 'f4'
        self.table_dtypes['Errors'] = 'S10'
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
                         '!Pxxxx': 'Set PWM value to xxxx',
                         '!Q': 'Get PWM value',
                         '!S': 'Get sky IR temperature',
                         '!T': 'Get sensor temperature',
                         '!z': 'Reset RS232 buffer pointers',
                         '!K': 'Get serial number',
                         'v!': 'Query if anemometer enabled',
                         'V!': 'Get wind speed',
                         }
        ## Clear Serial Buffer
        self.clear_buffer()
        ## Query Device Name
        self.name = self.query('!A', '!N').strip()
        self.logger.info('Device Name is "{}"'.format(self.name))
        ## Query Firmware Version
        self.firmware_version = float(self.query('!B', '!V'))
        self.logger.info('Firmware Version = {}'.format(self.firmware_version))
        ## Query Serial Number
        self.serial_number = self.query('!K', '!K(\d{4})')
        self.logger.info('Serial Number: {}'.format(self.serial_number))


    def clear_buffer(self):
        ## Clear Response Buffer
        while self.AAG.inWaiting() > 0:
            self.logger.debug('Clearing Buffer: {0}'.format(self.AAG.read(1)))


    def query(self, send, expect, max_tries=5):
        assert self.AAG
        if type(expect) == str:
            nResponses = 1
            ResponsePattern = '{}'.format(expect.replace('!', '\!')) + '([\s\w\d\.]{13})'
            ## Check if expect is a full pattern
            if len(expect) > 2:
                ResponsePattern = expect
        elif type(expect) == list:
            nResponses = len(expect)
            ResponsePattern = ''
            for i in range(0,nResponses,1):
                ResponsePattern += '{}'.format(expect[i].replace('!', '\!')) + '([\s\w\d\.]{'+'{}'.format(15-len(expect[1]))+'})'
        if send in self.commands.keys():
            self.logger.info('Sending command: {}'.format(self.commands[send]))
        else:
            self.logger.warning('Sending unknown command')
        send = send.encode('utf-8')
        nBytes = nResponses*15
        result = None
        tries = 0
        while not result:
            tries += 1
            self.logger.debug("Sending: {}".format(send))
            self.AAG.write(send)
            self.logger.debug("Reading serial response ...")
            responseString = self.AAG.read((nResponses+1)*15)
            responseString = str(responseString, 'utf-8')
            ## Check for Hand Shaking Block
            HSBgood = re.match('!'+chr(17)+'\s{12}0', responseString[-15:])
            if not HSBgood:
                self.logger.debug("Handshaking Block Bad")
                self.logger.debug("Unknown handshaking block: '{}'".format(responseString[-15:]))
            else:
                self.logger.debug("Found handshaking block: '{}'".format(responseString[-15:]))
            ## Check that Response Matches Standard Pattern
            self.logger.debug('Pattern to Match to Response: {}'.format(ResponsePattern))
            ResponseMatch = re.match(ResponsePattern, responseString[0:-15])
            if not ResponseMatch:
                self.logger.debug("Response does not match: '{}'".format(responseString[0:-15]))
            if HSBgood and ResponseMatch:
                self.logger.debug("Response matches: '{}'".format(responseString[0:-15]))
                ResponseArray = []
                for i in range(0,nResponses):
                    ResponseArray.append(ResponseMatch.group(i+1))
                if len(ResponseArray) == 1:
                    result = ResponseArray[0]
                else:
                    result = ResponseArray
            else:
                result = None
            if not result and tries >= max_tries:
                self.logger.warning('Failed to parse result after {} tries.'.format(max_tries))
                return None
        return result


    def get_ambient_temperature(self):
        '''
        Populates the self.ambient_temp property
        
        Calulation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 5.
        '''
#         AmbTemps = []
#         for i in range(0,5,1):
#             response = int(self.query('!T', '!2'))
#             if response:
#                 if response > 1022: response = 1022
#                 if response < 1: response = 1
#                 AmbPullUpResistance = 9.9
#                 AmbResAt25 = 10.
#                 r = math.log(AmbPullUpResistance / ((1023. / float(response)) - 1.) / AmbResAt25)
#                 AmbBeta = 3811
#                 ABSZERO = 273.15
#                 AmbTemps.append(1. / (r / AmbBeta + 1 / (ABSZERO + 25)))
#         if len(AmbTemps) >= 4:
#             self.ambient_temp = np.median(AmbTemps) * u.K
#             self.logger.info('Ambient Temperature is {:.1f}'.format(self.ambient_temp))
#         else:
#             self.ambient_temp = None
        AmbTemps = []
        for i in range(0,5,1):
            response = int(self.query('!T', '!2'))
            if response:
                AmbTemps.append((float(response)/100. + 273.15))
        if len(AmbTemps) >= 4:
            self.ambient_temp = np.median(AmbTemps) * u.K
            self.logger.info('Ambient Temperature is {:.1f}'.format(self.ambient_temp))
        else:
            self.ambient_temp = None




    def get_sky_temperature(self):
        '''
        Populates the self.sky_temp property
        
        Calulation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 1.
        
        Does this n times as recommended by the "Communication operational 
        recommendations" section in Rs232_Comms_v100.pdf
        '''
        SkyTemps = []
        for i in range(0,5,1):
            response = self.query('!S', '!1')
            if response:
                SkyTemps.append((float(response)/100. + 273.15))
        if len(SkyTemps) >= 4:
            self.sky_temp = np.median(SkyTemps) * u.K
            self.logger.info('Sky Temperature is {:.1f}'.format(self.sky_temp))
        else:
            self.sky_temp = None


    def get_values(self):
        '''
        Populates the self.internal_voltage, self.LDR_resistance, and 
        self.rain_sensor_temp properties
        
        Calulation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" items 4, 6, 7.
        '''
        internal_voltages = []
        LDR_resistances = []
        rain_sensor_temps = []
        for i in range(0,5,1):
            responses = AAG.query('!C', ['!6', '!4', '!5'])
            ## First result is the zener value
            response = int(responses[0])
            if response:
                ZenerConstant = 3
                internal_voltages.append(1023 * ZenerConstant / response)
            ## Second value us the LDR value
            response = int(responses[1])
            if response:
                if response > 1022: response = 1022
                if response < 1: response = 1
                LDRPullupResistance = 56.
                LDR_resistances.append(LDRPullupResistance / ((1023. / response) - 1.))
            ## Third reponse is rain sensor temperature
            response = int(responses[2])
            if response:
                if response > 1022: response = 1022
                if response < 1: response = 1
                RainPullUpResistance = 1
                RainResAt25 = 1
                r = math.log(RainPullUpResistance / ((1023. / float(response)) - 1.) / RainResAt25)
                RainBeta = 3450.
                ABSZERO = 273.15
                rain_sensor_temps.append(1. / (r / RainBeta + 1. / (ABSZERO + 25.)))
        ## Median Results
        if len(internal_voltages) >= 4:
            self.internal_voltage = np.median(internal_voltages) * u.volt
            self.logger.info('Internal Voltage = {}'.format(self.internal_voltage))
        else:
            self.internal_voltage = None
        if len(LDR_resistances) >= 4:
            self.LDR_resistance = np.median(LDR_resistances) * u.kiloohm
            self.logger.info('LDR Resistance = {}'.format(self.LDR_resistance))
        else:
            self.LDR_resistance = None
        if len(rain_sensor_temps) >= 4:
            self.rain_sensor_temp = np.median(rain_sensor_temps) * u.K
            self.logger.info('Rain Sensor Temp = {}'.format(self.rain_sensor_temp))
        else:
            self.rain_sensor_temp = None




    def get_PWM(self):
        '''
        Populates the self.PWM property.
        
        Calulation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 3.
        '''
        result = int(self.query('!Q', '!Q'))
        if result:
            self.PWM = 100. * float(result) / 1023.
            self.logger.info('Pulse Width Modulation Value = {}'.format(self.PWM))
        else:
            if result == 0:
                self.PWM = 100. * float(result) / 1023.
                self.logger.info('Pulse Width Modulation Value = {}'.format(self.PWM))
            else:
                self.PWM = None


    def get_rain_freq(self):
        '''
        Populates the self.rain_frequency property.
        
        Calulation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 8.
        '''
        response = self.query('!E', '!R')
        if response:
            self.rain_frequency = int(response)
            self.logger.info('Rain Frequency (0-1023) = {}'.format(self.rain_frequency))
        else:
            self.rain_frequency = None


    def get_errors(self):
        '''
        Populates the self.IR_errors property
        '''
        response = AAG.query('!D', ['!E1', '!E2', '!E3', '!E4'])
        if response:
            error_vals = [value.strip() for value in response]
            self.errors = ' '.join(error_vals)
            self.logger.info("IR Errors: '{}'".format(self.errors))
        else:
            self.errors = None


    def get_switch(self):
        '''
        Populates the self.switch property
        
        Unlike other queries, this method has to check if the return matches a
        !X or !Y pattern (indicating open and closed respectively) rather than
        read a value.
        '''
        self.switch = None
        max_tries = 3
        tries = 0
        status = None
        while not status:
            tries += 1
            query_open = self.query('!F', '!X', max_tries=2)
            query_closed = self.query('!F', '!Y', max_tries=2)
            if query_open and not query_closed:
                status = 'OPEN'
            elif not query_open and query_closed:
                status = 'CLOSED'
            else:
                status = None
            if not status and tries >= max_tries:
                status = 'UNKNOWN'
        self.switch = status
        self.logger.info('Switch Status = {}'.format(self.switch))


    def reversed_query(self, send, expect, max_tries=5):
        '''
        Need to use special method to query if the wind speed anemometer is
        available because the format appears to be backwards with the hand
        shaking block first and the data second.
        '''
        assert self.AAG
        nResponses = 1
        ResponsePattern = '!'+chr(17)+'\s{12}0'+'{}'.format(expect.replace('!', '\!'))+'([\s\w\d\.]{13})'
        if send in self.commands.keys():
            self.logger.info('Sending command: {}'.format(self.commands[send]))
        else:
            self.logger.warning('Sending unknown command')
        send = send.encode('utf-8')
        nBytes = nResponses*15
        result = None
        tries = 0
        while not result:
            tries += 1
            self.logger.debug("Sending: {}".format(send))
            self.AAG.write(send)
            self.logger.debug("Reading serial response ...")
            responseString = self.AAG.read((nResponses+1)*15)
            responseString = str(responseString, 'utf-8')
            ResponseMatch = re.match(ResponsePattern, responseString)
            if not ResponseMatch:
                self.logger.debug("Response does not match: '{}'".format(responseString))
                result = None
            else:
                self.logger.debug("Response matches: '{}'".format(responseString))
                result = ResponseMatch.group(1)
            if not result and tries >= max_tries:
                self.logger.warning('Failed to parse result after {} tries.'.format(max_tries))
                return None
        return result


    def wind_speed_enabled(self, max_tries=3):
        '''
        Method returns true or false depending on whether the device supports
        wind speed measurements.
        '''
        result = self.reversed_query('v!', '!v')
        if result:
            if int(result) == 1:
                self.logger.debug('Anemometer enabled')
                return True
            else:
                self.logger.debug('Anemometer not enabled')
                return False
        else:
            self.logger.debug('Anemometer not enabled')
            return False


    def get_wind_speed(self):
        '''
        Populates the self.wind_speed property
        
        Based on the information in Rs232_Comms_v120.pdf document
        '''
        if AAG.wind_speed_enabled():
            result = self.reversed_query('V!', '!w')
            if result:
                self.wind_speed = int(result) * u.km / u.hr
                self.logger.info('Wind speed = {}'.format(self.wind_speed))
            else:
                self.wind_speed = None
        else:
            self.wind_speed = None


    def update_weather(self):
        '''
        Queries the values for writing to the telemetry file.
        '''
        self.get_ambient_temperature()
        self.get_sky_temperature()
        self.get_wind_speed()
        self.get_values()
        self.get_PWM()
        self.get_errors()
        self.get_switch()
        self.make_safety_decision()
        self.last_update = datetime.datetime.utcnow()
        self.update_telemetry_files()


    def update_telemetry_files(self):
        '''
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

        ## Second, write file with all data
        if os.path.exists(self.telemetry_file):
            self.logger.debug('Opening prior telemetry file: {}'.format(self.telemetry_file))
            telemetry = ascii.read(self.telemetry_file, guess=False,
                                   format='basic',
                                   names=('Timestamp', 'Safe', 'Ambient Temperature', 'Sky Temperature', 'Wind Speed', 
                                          'Internal Voltage', 'LDR Resistance', 'Rain Sensor Temperature', 'PWM',
                                          'Errors', 'Switch'),
                                   converters={'Timestamp': [ascii.convert_numpy(self.table_dtypes['Timestamp'])],
                                               'Safe': [ascii.convert_numpy(self.table_dtypes['Safe'])],
                                               'Ambient Temperature': [ascii.convert_numpy(self.table_dtypes['Ambient Temperature'])],
                                               'Sky Temperature': [ascii.convert_numpy(self.table_dtypes['Sky Temperature'])],
                                               'Wind Speed': [ascii.convert_numpy(self.table_dtypes['Wind Speed'])],
                                               'Internal Voltage': [ascii.convert_numpy(self.table_dtypes['Internal Voltage'])],
                                               'LDR Resistance': [ascii.convert_numpy(self.table_dtypes['LDR Resistance'])],
                                               'Rain Sensor Temperature': [ascii.convert_numpy(self.table_dtypes['Rain Sensor Temperature'])],
                                               'PWM': [ascii.convert_numpy(self.table_dtypes['PWM'])],
                                               'Errors': [ascii.convert_numpy(self.table_dtypes['Errors'])],
                                               'Switch': [ascii.convert_numpy(self.table_dtypes['Switch'])] }
                                  )
        else:
            self.logger.debug('No prior telemetry file found.  Generating new table.')
            telemetry = table.Table(names=('Timestamp', 'Safe',
                                           'Ambient Temperature', 'Sky Temperature', 'Wind Speed', 
                                           'Internal Voltage', 'LDR Resistance', 'Rain Sensor Temperature', 'PWM',
                                           'Errors', 'Switch'),
                                    dtype=(self.table_dtypes['Timestamp'],
                                           self.table_dtypes['Safe'],
                                           self.table_dtypes['Ambient Temperature'],
                                           self.table_dtypes['Sky Temperature'],
                                           self.table_dtypes['Wind Speed'],
                                           self.table_dtypes['Internal Voltage'],
                                           self.table_dtypes['LDR Resistance'],
                                           self.table_dtypes['Rain Sensor Temperature'],
                                           self.table_dtypes['PWM'],
                                           self.table_dtypes['Errors'],
                                           self.table_dtypes['Switch'])
                                    )
        new_row = {'Timestamp': self.last_update.strftime('%Y/%m/%d %H:%M:%S UT'),
                   'Safe': self.safe,
                   'Ambient Temperature': self.ambient_temp.value,
                   'Sky Temperature': self.sky_temp.value,
                   'Wind Speed': self.wind_speed.value,
                   'Internal Voltage': self.internal_voltage.value,
                   'LDR Resistance': self.LDR_resistance.value,
                   'Rain Sensor Temperature': self.rain_sensor_temp.value,
                   'PWM': self.PWM,
                   'Errors': self.errors,
                   'Switch': self.switch}
        self.logger.debug('Adding new row to table')
        telemetry.add_row(new_row)
        self.logger.debug('Writing modified table to: {}'.format(self.telemetry_file))
        ascii.write(telemetry, self.telemetry_file, format='basic')


    def make_safety_decision(self):
        '''
        Method makes decision whether conditions are safe or unsafe.
        '''
        self.safe = 'UNSAFE'




if __name__ == '__main__':
    AAG = AAGCloudSensor(serial_address='/dev/ttyAMA0')
    AAG.update_weather()
    AAG.logger.info('Done.')


