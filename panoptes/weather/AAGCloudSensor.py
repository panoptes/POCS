#!/usr/bin/env python

import os
import sys
import serial
import re
from datetime import datetime as dt
from datetime import timedelta as tdelta
import time
import argparse
import numpy as np

import astropy.units as u
import astropy.table as table
import astropy.io.ascii as ascii

from panoptes.utils import logger, config, database
from panoptes.weather import WeatherStation

##-----------------------------------------------------------------------------
## Quick moving average function
##-----------------------------------------------------------------------------
def movingaverage(interval, window_size):
    window= np.ones(int(window_size))/float(window_size)
    return np.convolve(interval, window, 'same')

##-----------------------------------------------------------------------------
## PID Class (for rain heater PID loop)
##-----------------------------------------------------------------------------
class PID:
    '''
    Pseudocode from Wikipedia:
    
    previous_error = 0
    integral = 0 
    start:
      error = setpoint - measured_value
      integral = integral + error*dt
      derivative = (error - previous_error)/dt
      output = Kp*error + Ki*integral + Kd*derivative
      previous_error = error
      wait(dt)
      goto start
    '''
    def __init__(self, Kp=2., Ki=0., Kd=1., set_point=None, output_limits=None):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.Pval = None
        self.Ival = 0.0
        self.Dval = 0.0
        self.previous_error = None
        self.set_point = None
        if set_point: self.set_point = set_point
        self.output_limits = output_limits


    def recalculate(self, value, dt=1.0, new_set_point=None):
        if new_set_point:
            self.set_point = float(new_set_point)
        error = self.set_point - value
        self.Pval = error
        self.Ival = self.Ival + error*dt
        if self.previous_error:
            self.Dval = (error - self.previous_error)/dt
        output = self.Kp*error + self.Ki*self.Ival + self.Kd*self.Dval
        if self.output_limits:
            if output > max(self.output_limits): output = max(self.output_limits)
            if output < min(self.output_limits): output = min(self.output_limits)
        self.previous_error = error
        return output


    def tune(self, Kp=None, Ki=None, Kd=None):
        if Kp: self.Kp = Kp
        if Ki: self.Ki = Ki
        if Kd: self.Kd = Kd


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
    'E4'    Number of internal errors reading infra red sensor: PEC byte NB: the error
            counters are reset after being read.
    'N '    Internal Name
    'V '    Firmware Version number
    'Q '    PWM duty cycle
    'R '    Rain frequency counter
    'X '    Switch Opened
    'Y '    Switch Closed

    Advice from the manual:
    
    * When communicating with the device send one command at a time and wait for
    the respective reply, checking that the correct number of characters has
    been received.
    
    * Perform more than one single reading (say, 5) and apply a statistical
    analysis to the values to exclude any outlier.
    
    * The rain frequency measurement is the one that takes more time - 280 ms
    
    * The following reading cycle takes just less than 3 seconds to perform:
        * Perform 5 times:
            * get IR temperature
            * get Ambient temperature
            * get Values
            * get Rain Frequency
        * get PWM value
        * get IR errors
        * get SWITCH Status

    '''

    def __init__(self, serial_address=None):
        super().__init__()

        ## Read configuration
        self.cfg = config.load_config()['weather']['aag_cloud']

        ## Initialize Serial Connection
        if not serial_address:
            if 'serial_port' in self.cfg.keys():
                serial_address = self.cfg['serial_port']
            else:
                serial_address = '/dev/ttyUSB0'
        self.logger.debug('Using serial address: {}'.format(serial_address))
        if serial_address:
            self.logger.info('Connecting to AAG Cloud Sensor')
            try:
                self.AAG = serial.Serial(serial_address, 9600, timeout=2)
                self.logger.info("  Connected to Cloud Sensor on {}".format(serial_address))
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
        ## Thresholds

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
        self.safe_dict = None
        self.hibernate = 0.200  ## time to wait after failed query
        ## Command Translation
        self.commands = {'!A': 'Get internal name',
                         '!B': 'Get firmware version',
                         '!C': 'Get values',
                         '!D': 'Get internal errors',
                         '!E': 'Get rain frequency',
                         '!F': 'Get switch status',
                         '!G': 'Set switch open',
                         '!H': 'Set switch closed',
                         'P\d\d\d\d!': 'Set PWM value',
                         '!Q': 'Get PWM value',
                         '!S': 'Get sky IR temperature',
                         '!T': 'Get sensor temperature',
                         '!z': 'Reset RS232 buffer pointers',
                         '!K': 'Get serial number',
                         'v!': 'Query if anemometer enabled',
                         'V!': 'Get wind speed',
                         'M!': 'Get electrical constants',
                         '!Pxxxx': 'Set PWM value to xxxx',
                         }
        self.expects = {'!A': '!N\s+(\w+)!',
                        '!B': '!V\s+([\d\.\-]+)!',
                        '!C': '!6\s+([\d\.\-]+)!4\s+([\d\.\-]+)!5\s+([\d\.\-]+)!',
                        '!D': '!E1\s+([\d\.]+)!E2\s+([\d\.]+)!E3\s+([\d\.]+)!E4\s+([\d\.]+)!',
                        '!E': '!R\s+([\d\.\-]+)!',
                        '!F': '!Y\s+([\d\.\-]+)!',
                        'P\d\d\d\d!': '!Q\s+([\d\.\-]+)!',
                        '!Q': '!Q\s+([\d\.\-]+)!',
                        '!S': '!1\s+([\d\.\-]+)!',
                        '!T': '!2\s+([\d\.\-]+)!',
                        '!K': '!K(\d+)\s*\\x00!',
                        'v!': '!v\s+([\d\.\-]+)!',
                        'V!': '!w\s+([\d\.\-]+)!',
                        'M!': '!M(.{12})',
                        }
        self.delays = {\
                       '!E': 0.350,
                       }
        if self.AAG:
            ## Query Device Name
            result = self.query('!A')
            if result:
                self.name = result[0].strip()
            else:
                self.name = ''
            self.logger.info('  Device Name is "{}"'.format(self.name))

            ## Query Firmware Version
            result = self.query('!B')
            if result:
                self.firmware_version = result[0].strip()
            else:
                self.firmware_version = ''
            self.logger.info('  Firmware Version = {}'.format(self.firmware_version))

            ## Query Serial Number
            result = self.query('!K')
            if result:
                self.serial_number = result[0].strip()
            else:
                self.serial_number = ''
            self.logger.info('  Serial Number: {}'.format(self.serial_number))



    def send(self, send, delay=0.100):

        found_command = False
        for cmd in self.commands.keys():
            if re.match(cmd, send):
                self.logger.debug('Sending command: {}'.format(self.commands[cmd]))
                found_command = True
                break
        if not found_command:
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
        found_command = False
        for cmd in self.commands.keys():
            if re.match(cmd, send):
                self.logger.debug('Sending command: {}'.format(self.commands[cmd]))
                found_command = True
                break
        if not found_command:
            self.logger.warning('Unknown command: "{}"'.format(send))
            return None

        if cmd in self.delays.keys():
            delay = self.delays[cmd]
        else:
            delay = 0.200
        expect = self.expects[cmd]
        count = 0
        result = None
        while not result and (count <= maxtries):
            count += 1
            result = self.send(send, delay=delay)

            MatchExpect = re.match(expect, result)
            if not MatchExpect:
                self.logger.debug('Did not find {} in response "{}"'.format(expect, result))
                result = None
                time.sleep(self.hibernate)
            else:
                self.logger.debug('Found {} in response "{}"'.format(expect, result))
                result = MatchExpect.groups()
        return result


    def get_ambient_temperature(self, n=5):
        '''
        Populates the self.ambient_temp property
        
        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 5.
        '''
        self.logger.info('Getting ambient temperature')
        values = []
        for i in range(0,n):
            try:
                value = float(self.query('!T')[0])/100.
            except:
                pass
            else:
                self.logger.debug('  Ambient Temperature Query = {:.1f}'.format(value))
                values.append(value)
        if len(values) >= n-1:
            self.ambient_temp = np.median(values)*u.Celsius
            self.logger.info('  Ambient Temperature = {:.1f}'.format(self.ambient_temp))
        else:
            self.ambient_temp = None
            self.logger.info('  Failed to Read Ambient Temperature')
        return self.ambient_temp


    def get_sky_temperature(self, n=9):
        '''
        Populates the self.sky_temp property
        
        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 1.
        
        Does this n times as recommended by the "Communication operational 
        recommendations" section in Rs232_Comms_v100.pdf
        '''
        self.logger.info('Getting sky temperature')
        values = []
        for i in range(0,n):
            try:
                value = float(self.query('!S')[0])/100.
            except:
                pass
            else:
                self.logger.debug('  Sky Temperature Query = {:.1f}'.format(value))
                values.append(value)
        if len(values) >= n-1:
            self.sky_temp = np.median(values)*u.Celsius
            self.logger.info('  Sky Temperature = {:.1f}'.format(self.sky_temp))
        else:
            self.sky_temp = None
            self.logger.info('  Failed to Read Sky Temperature')
        return self.sky_temp


    def get_values(self, n=5):
        '''
        Populates the self.internal_voltage, self.LDR_resistance, and 
        self.rain_sensor_temp properties
        
        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" items 4, 6, 7.
        '''
        self.logger.info('Getting "values"')
        ZenerConstant = 3
        LDRPullupResistance = 56.
        RainPullUpResistance = 1
        RainResAt25 = 1
        RainBeta = 3450.
        ABSZERO = 273.15
        internal_voltages = []
        LDR_resistances = []
        rain_sensor_temps = []
        for i in range(0,n):
            responses = self.query('!C')
            try:
                internal_voltage = 1023 * ZenerConstant / float(responses[0])
                internal_voltages.append(internal_voltage)
                LDR_resistance = LDRPullupResistance / ((1023. / float(responses[1])) - 1.)
                LDR_resistances.append(LDR_resistance)
                r = np.log(RainPullUpResistance / ((1023. / float(responses[2])) - 1.) / RainResAt25)
                rain_sensor_temp = 1. / (r / RainBeta + 1. / (ABSZERO + 25.)) - ABSZERO
                rain_sensor_temps.append(rain_sensor_temp)
            except:
                pass

        ## Median Results
        if len(internal_voltages) >= n-1:
            self.internal_voltage = np.median(internal_voltages) * u.volt
            self.logger.info('  Internal Voltage = {}'.format(self.internal_voltage))
        else:
            self.internal_voltage = None
            self.logger.info('  Failed to read Internal Voltage')

        if len(LDR_resistances) >= n-1:
            self.LDR_resistance = np.median(LDR_resistances) * 1000. * u.ohm
            self.logger.info('  LDR Resistance = {}'.format(self.LDR_resistance))
        else:
            self.LDR_resistance = None
            self.logger.info('  Failed to read LDR Resistance')

        if len(rain_sensor_temps) >= n-1:
            self.rain_sensor_temp = np.median(rain_sensor_temps) * u.Celsius
            self.logger.info('  Rain Sensor Temp = {}'.format(self.rain_sensor_temp))
        else:
            self.rain_sensor_temp = None
            self.logger.info('  Failed to read Rain Sensor Temp')

        return (self.internal_voltage, self.LDR_resistance, self.rain_sensor_temp)


    def get_rain_frequency(self, n=5):
        '''
        Populates the self.rain_frequency property
        '''
        self.logger.info('Getting rain frequency')
        values = []
        for i in range(0,n):
            try:
                value = float(self.query('!E')[0]) * 100. / 1023.
                self.logger.debug('  Rain Freq Query = {:.1f}'.format(value))
                values.append(value)
            except:
                pass
        if len(values) >= n-1:
            self.rain_frequency = np.median(values)
            self.logger.info('  Rain Frequency = {:.1f}'.format(self.rain_frequency))
        else:
            self.rain_frequency = None
            self.logger.info('  Failed to read Rain Frequency')
        return self.rain_frequency


    def get_PWM(self):
        '''
        Populates the self.PWM property.
        
        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 3.
        '''
        self.logger.info('Getting PWM value')
        try:
            value = self.query('!Q')[0]
            self.PWM = float(value) * 100. / 1023.
            self.logger.info('  PWM Value = {:.1f}'.format(self.PWM))
        except:
            self.PWM = None
            self.logger.info('  Failed to read PWM Value')
        return self.PWM


    def set_PWM(self, percent):
        '''
        '''
        if percent < 5: percent = 5.
        if percent > 100: percent = 100.
        self.logger.info('Setting PWM value to {:.1f} %'.format(percent))
        send_digital = int(1023. * float(percent) / 100.)
        send_string = 'P{:04d}!'.format(send_digital)
        result = self.query(send_string)
        if result:
            self.PWM = float(result[0]) * 100. / 1023.
            self.logger.info('  PWM Value = {:.1f}'.format(self.PWM))


    def get_errors(self):
        '''
        Populates the self.IR_errors property
        '''
        self.logger.info('Getting errors')
        response = self.query('!D')
        if response:
            self.errors = {'!E1': str(int(response[0])),
                           '!E2': str(int(response[1])),
                           '!E3': str(int(response[2])),
                           '!E4': str(int(response[3])) }
            self.logger.info("  Internal Errors: {} {} {} {}".format(\
                             self.errors['!E1'],\
                             self.errors['!E2'],\
                             self.errors['!E3'],\
                             self.errors['!E4'],\
                             ))

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
        self.logger.info('Getting switch status')
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
        self.logger.info('  Switch Status = {}'.format(self.switch))
        return self.switch


    def wind_speed_enabled(self):
        '''
        Method returns true or false depending on whether the device supports
        wind speed measurements.
        '''
        self.logger.debug('Checking if wind speed is enabled')
        try:
            enabled = bool(self.query('v!')[0])
            if enabled:
                self.logger.debug('  Anemometer enabled')
            else:
                self.logger.debug('  Anemometer not enabled')
        except:
            enabled = None
        return enabled


    def get_wind_speed(self, n=9):
        '''
        Populates the self.wind_speed property
        
        Based on the information in Rs232_Comms_v120.pdf document
        
        Medians 5 measurements.  This isn't mentioned specifically by the manual
        but I'm guessing it won't hurt.
        '''
        self.logger.info('Getting wind speed')
        if self.wind_speed_enabled():
            values = []
            for i in range(0,n):
                result = self.query('V!')
                if result:
                    value = float(result[0])
                    self.logger.debug('  Wind Speed Query = {:.1f}'.format(value))
                    values.append(value)
            if len(values) >= 3:
                self.wind_speed = np.median(values)*u.km/u.hr
                self.logger.info('  Wind speed = {:.1f}'.format(self.wind_speed))
            else:
                self.wind_speed = None
        else:
            self.wind_speed = None
        return self.wind_speed


    def update_weather(self, update_mongo=True):
        '''
        '''
        data = {}
        data['Device Name'] = self.name
        data['Firmware Version'] = self.firmware_version
        data['Device Serial Number'] = self.serial_number
        if self.get_sky_temperature():
            data['Sky Temperature (C)'] = self.sky_temp.value
        if self.get_ambient_temperature():
            data['Ambient Temperature (C)'] = self.ambient_temp.value
        self.get_values()
        if self.internal_voltage:
            data['Internal Voltage (V)'] = self.internal_voltage.value
        if self.LDR_resistance:
            data['LDR Resistance (ohm)'] = self.LDR_resistance.value
        if self.rain_sensor_temp:
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
        self.safe_dict = make_safety_decision(self.cfg)
        data['Safe'] = self.safe_dict['Safe']
        data['Sky Safe'] = self.safe_dict['Sky']
        data['Wind Safe'] = self.safe_dict['Wind']
        data['Gust Safe'] = self.safe_dict['Gust']
        data['Rain Safe'] = self.safe_dict['Rain']

        if update_mongo:
            try:
                from panoptes.utils import config, logger, database
                # Connect to sensors collection
                sensors = database.PanMongo().sensors
                self.logger.info('Connected to mongo')
                sensors.insert({
                    "date": dt.utcnow(),
                    "type": "weather",
                    "data": data
                })
                self.logger.info('  Inserted mongo document')
                sensors.update({"status": "current", "type": "weather"},\
                               {"$set": {\
                                   "date": dt.utcnow(),\
                                   "type": "weather",\
                                   "data": data,\
                               }},\
                               True)
                self.logger.info('  Updated current status document')
            except:
                self.logger.warning('Failed to update mongo database')
        else:
            print('{:>26s}: {}'.format('Date and Time',\
                   dt.utcnow().strftime('%Y/%m/%d %H:%M:%S')))
            for key in ['Ambient Temperature (C)', 'Sky Temperature (C)',\
                        'PWM Value', 'Rain Frequency', 'Safe']:
                if key in data.keys():
                    print('{:>26s}: {}'.format(key, data[key]))
                else:
                    print('{:>26s}: {}'.format(key, 'no data'))
            print('')

        return self.safe


def make_safety_decision(cfg):
    '''
    Method makes decision whether conditions are safe or unsafe.
    '''
    ## If sky-amb > threshold, then cloudy (safe)
    if 'threshold_cloudy' in cfg.keys():
        threshold_cloudy = cfg['threshold_cloudy']
    else:
        threshold_cloudy = -20
    ## If sky-amb > threshold, then very cloudy (unsafe)
    if 'threshold_very_cloudy' in cfg.keys():
        threshold_very_cloudy = cfg['threshold_very_cloudy']
    else:
        threshold_very_cloudy = -15

    ## If avg_wind > threshold, then windy (safe)
    if 'threshold_windy' in cfg.keys():
        threshold_windy = cfg['threshold_windy']
    else:
        threshold_windy = 20
    ## If avg_wind > threshold, then very windy (unsafe)
    if 'threshold_very_windy' in cfg.keys():
        threshold_very_windy = cfg['threshold_very_windy']
    else:
        threshold_very_windy = 30

    ## If wind > threshold, then gusty (safe)
    if 'threshold_gusty' in cfg.keys():
        threshold_gusty = cfg['threshold_gusty']
    else:
        threshold_gusty = 40
    ## If wind > threshold, then very gusty (unsafe)
    if 'threshold_very_gusty' in cfg.keys():
        threshold_very_gusty = cfg['threshold_very_gusty']
    else:
        threshold_very_gusty = 50

    ## If rain frequency < threshold, then unsafe
    if 'threshold_rainy' in cfg.keys():
        threshold_rain = cfg['threshold_rainy']
    else:
        threshold_rain = 230

    ## Get Last 15 minutes of data
    end = dt.utcnow()
    start = end - tdelta(0, 15*60)
    sensors = database.PanMongo().sensors
    entries = [x for x in sensors.find( {"type" : "weather", 'date': {'$gt': start, '$lt': end} } )]
    print('Found {} weather data entries in last 15 minutes'.format(len(entries)))

    ## Cloudiness
    sky_diff = [x['data']['Sky Temperature (C)'] - x['data']['Ambient Temperature (C)']\
                for x in entries\
                if 'Ambient Temperature (C)' in x['data'].keys()\
                and 'Sky Temperature (C)' in x['data'].keys()]
    if len(sky_diff) == 0:
        sky_safe = False
    elif max(sky_diff) < threshold_very_cloudy:
        sky_safe = True
    else:
        sky_safe = False

    ## Wind (average and gusts)
    wind_speed = [x['data']['Wind Speed (km/h)']\
                  for x in entries\
                  if 'Wind Speed (km/h)' in x['data'].keys()]

    if len(wind_speed) == 0:
        wind_safe = False
        gust_safe = False
    else:
        typical_data_interval = (end - min([x['date'] for x in entries])).total_seconds()/len(entries)
        mavg_count = int(np.ceil(120./typical_data_interval))
        wind_mavg = movingaverage(wind_speed, mavg_count)
        if max(wind_mavg) > threshold_very_windy:
            wind_safe = False
        else:
            wind_safe = True
        if max(wind_speed) > threshold_very_gusty:
            gust_safe = False
        else:
            gust_safe = True

    ## Rain
    rf_value = [x['data']['Rain Frequency']\
                  for x in entries\
                  if 'Rain Frequency' in x['data'].keys()]

    if len(rf_value) == 0:
        rain_safe = False
    elif min(rf_value) < threshold_rain:
        rain_safe = False
    else:
        rain_safe = True

    safe = sky_safe & wind_safe & gust_safe & rain_safe
    translator = {True: 'safe', False: 'unsafe'}
    if safe:
        print('Safe (Sky: {}, Wind: {}, Gust: {}, Rain: {})'.format(\
              translator[sky_safe], translator[wind_safe],\
              translator[gust_safe], translator[rain_safe]))
    else:
        print('Unsafe (Sky: {}, Wind: {}, Gust: {}, Rain: {})'.format(\
              translator[sky_safe], translator[wind_safe],\
              translator[gust_safe], translator[rain_safe]))

    safe_dict = {'Safe': safe,
                 'Sky': sky_safe,
                 'Wind': wind_safe,
                 'Gust': gust_safe,
                 'Rain': rain_safe}
    return safe_dict


def plot_weather(date_string):
    import matplotlib as mpl
    mpl.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.dates import HourLocator, MinuteLocator, DateFormatter
    plt.ioff()
    import ephem

    dpi=100
    Figure = plt.figure(figsize=(13,9.5), dpi=dpi)
    hours = HourLocator(byhour=range(24), interval=1)
    hours_fmt = DateFormatter('%H')

    if not date_string:
        today = True
        date = dt.utcnow()
        date_string = date.strftime('%Y%m%dUT')
        start = dt(date.year, date.month, date.day, 0, 0, 0, 0)
        end = date+tdelta(0, 30*60)
    else:
        today = False
        date = dt.strptime(date_string, '%Y%m%dUT')
        start = dt(date.year, date.month, date.day, 0, 0, 0, 0)
        end = dt(date.year, date.month, date.day, 23, 59, 59, 0)

    ##------------------------------------------------------------------------
    ## Use pyephem determine sunrise and sunset times
    ##------------------------------------------------------------------------
    Observatory = ephem.Observer()
    Observatory.lon = "-155:34:33.9"
    Observatory.lat = "+19:32:09.66"
    Observatory.elevation = 3400.0
    Observatory.temp = 10.0
    Observatory.pressure = 680.0
    Observatory.date = date.strftime('%Y/%m/%d 10:00:00')

    Observatory.horizon = '0.0'
    sunset  = Observatory.previous_setting(ephem.Sun()).datetime()
    sunrise = Observatory.next_rising(ephem.Sun()).datetime()
    Observatory.horizon = '-6.0'
    evening_civil_twilight = Observatory.previous_setting(ephem.Sun(), use_center=True).datetime()
    morning_civil_twilight = Observatory.next_rising(ephem.Sun(), use_center=True).datetime()
    Observatory.horizon = '-12.0'
    evening_nautical_twilight = Observatory.previous_setting(ephem.Sun(), use_center=True).datetime()
    morning_nautical_twilight = Observatory.next_rising(ephem.Sun(), use_center=True).datetime()
    Observatory.horizon = '-18.0'
    evening_astronomical_twilight = Observatory.previous_setting(ephem.Sun(), use_center=True).datetime()
    morning_astronomical_twilight = Observatory.next_rising(ephem.Sun(), use_center=True).datetime()


    ##-------------------------------------------------------------------------
    ## Plot a day's weather
    ##-------------------------------------------------------------------------
    plot_positions = [ ( [0.000, 0.760, 0.460, 0.240], [0.540, 0.760, 0.460, 0.240] ),
                       ( [0.000, 0.495, 0.460, 0.240], [0.540, 0.495, 0.460, 0.240] ),
                       ( [0.000, 0.245, 0.460, 0.240], [0.540, 0.245, 0.460, 0.240] ),
                       ( [0.000, 0.000, 0.460, 0.235], [0.540, 0.000, 0.460, 0.235] ),
                     ]
    
    # Connect to sensors collection
    sensors = database.PanMongo().sensors
    entries = [x for x in sensors.find( {"type" : "weather", 'date': {'$gt': start, '$lt': end} } )]

    ##-------------------------------------------------------------------------
    ## Plot Ambient Temperature vs. Time
    t_axes = plt.axes(plot_positions[0][0])
    plt.title('Weather for {}'.format(date_string))
    amb_temp = [x['data']['Ambient Temperature (C)']\
                for x in entries\
                if 'Ambient Temperature (C)' in x['data'].keys()]
    time = [x['date'] for x in entries\
                if 'Ambient Temperature (C)' in x['data'].keys()]
    t_axes.plot_date(time, amb_temp, 'ko',\
                     markersize=2, markeredgewidth=0,\
                     drawstyle="default")
    plt.ylabel("Ambient Temp. (C)")
    plt.grid(which='major', color='k')
    plt.yticks(range(-100,100,10))
    t_axes.xaxis.set_major_locator(hours)
    t_axes.xaxis.set_major_formatter(hours_fmt)
    plt.xlim(start, end)
    plt.ylim(-5,35)

    plt.axvspan(sunset, evening_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.1)
    plt.axvspan(evening_civil_twilight, evening_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
    plt.axvspan(evening_nautical_twilight, evening_astronomical_twilight, ymin=0, ymax=1, color='blue', alpha=0.3)
    plt.axvspan(evening_astronomical_twilight, morning_astronomical_twilight, ymin=0, ymax=1, color='blue', alpha=0.5)
    plt.axvspan(morning_astronomical_twilight, morning_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.3)
    plt.axvspan(morning_nautical_twilight, morning_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
    plt.axvspan(morning_civil_twilight, sunrise, ymin=0, ymax=1, color='blue', alpha=0.1)

    ##-------------------------------------------------------------------------
    ## Plot Sky Temperature vs. Time
    s_axes = plt.axes(plot_positions[1][0])
    sky_temp = [x['data']['Sky Temperature (C)']\
                for x in entries\
                if 'Sky Temperature (C)' in x['data'].keys()]
    time = [x['date'] for x in entries\
                if 'Sky Temperature (C)' in x['data'].keys()]
    s_axes.plot_date(time, sky_temp, 'ko',\
                     markersize=2, markeredgewidth=0,\
                     drawstyle="default")
    plt.ylabel("Sky Temp. (C)")
    plt.grid(which='major', color='k')
    plt.yticks(range(-100,100,10))
    s_axes.xaxis.set_major_locator(hours)
    s_axes.xaxis.set_major_formatter(hours_fmt)
    s_axes.xaxis.set_ticklabels([])
    plt.xlim(start, end)
    plt.ylim(-35,5)

    ##-------------------------------------------------------------------------
    ## Plot Brightness vs. Time
    ldr_axes = plt.axes(plot_positions[2][0])
    max_ldr = 28587999.99999969
    ldr_value = [x['data']['LDR Resistance (ohm)']\
                  for x in entries\
                  if 'LDR Resistance (ohm)' in x['data'].keys()]
    brightness = [10.**(2. - 2.*x/max_ldr) for x in ldr_value]
    time = [x['date'] for x in entries\
                if 'LDR Resistance (ohm)' in x['data'].keys()]
    ldr_axes.plot_date(time, brightness, 'ko',\
                       markersize=2, markeredgewidth=0,\
                       drawstyle="default")
    plt.ylabel("Brightness (%)")
    plt.yticks(range(-100,100,10))
    plt.ylim(-5,105)
    plt.grid(which='major', color='k')
    ldr_axes.xaxis.set_major_locator(hours)
    ldr_axes.xaxis.set_major_formatter(hours_fmt)
    ldr_axes.xaxis.set_ticklabels([])
    plt.xlim(start, end)

    plt.axvspan(sunset, evening_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.1)
    plt.axvspan(evening_civil_twilight, evening_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
    plt.axvspan(evening_nautical_twilight, evening_astronomical_twilight, ymin=0, ymax=1, color='blue', alpha=0.3)
    plt.axvspan(evening_astronomical_twilight, morning_astronomical_twilight, ymin=0, ymax=1, color='blue', alpha=0.5)
    plt.axvspan(morning_astronomical_twilight, morning_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.3)
    plt.axvspan(morning_nautical_twilight, morning_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
    plt.axvspan(morning_civil_twilight, sunrise, ymin=0, ymax=1, color='blue', alpha=0.1)


    ##-------------------------------------------------------------------------
    ## Plot PWM Value vs. Time
    pwm_axes = plt.axes(plot_positions[3][0])
    pwm_value = [x['data']['PWM Value']\
                  for x in entries\
                  if 'PWM Value' in x['data'].keys()\
                  and 'Rain Sensor Temp (C)' in x['data'].keys()\
                  and 'Ambient Temperature (C)' in x['data'].keys()]
    rst_delta = [x['data']['Rain Sensor Temp (C)'] - x['data']['Ambient Temperature (C)']\
                 for x in entries\
                 if 'PWM Value' in x['data'].keys()\
                 and 'Rain Sensor Temp (C)' in x['data'].keys()\
                 and 'Ambient Temperature (C)' in x['data'].keys()]

    time = [x['date'] for x in entries\
                if 'PWM Value' in x['data'].keys()]
    pwm_axes.plot_date(time, pwm_value, 'bo', label='PWM Value',\
                       markersize=2, markeredgewidth=0,\
                       drawstyle="default")
    plt.ylabel("PWM Value")
    plt.ylim(-5,105)
    plt.xlim(start, end)
    plt.grid(which='major', color='k')
    pwm_axes.xaxis.set_major_locator(hours)
    pwm_axes.xaxis.set_major_formatter(hours_fmt)

    rst_axes = pwm_axes.twinx()
    rst_axes.set_ylabel('Rain Sensor Delta (C)')
    rst_axes.plot_date(time, rst_delta, 'ro-', label='RST Delta (C)',\
                       markersize=2, markeredgewidth=0,\
                       drawstyle="default")
    rst_axes.plot_date([start, end], [0, 0], 'k-', alpha=0.5)
    rst_axes.plot_date([start, end], [5, 5], 'k-', alpha=0.5)
    rst_axes.plot_date([start, end], [15, 15], 'k-', alpha=0.5)
    plt.ylim(-10,30)
#     plt.legend(loc='best')


    ##-------------------------------------------------------------------------
    ## Plot Temperature Difference vs. Time
    td_axes = plt.axes(plot_positions[0][1])
    plt.title('Safety Conditions for {}'.format(date_string))
    temp_diff = [x['data']['Sky Temperature (C)'] - x['data']['Ambient Temperature (C)']\
                 for x in entries\
                 if 'Sky Temperature (C)' in x['data'].keys()\
                 and 'Ambient Temperature (C)' in x['data'].keys()\
                 and 'Sky Safe' in x['data'].keys()]
    sky_safe = [x['data']['Sky Safe']\
                for x in entries\
                if 'Sky Temperature (C)' in x['data'].keys()\
                and 'Ambient Temperature (C)' in x['data'].keys()\
                and 'Sky Safe' in x['data'].keys()]
    time = [x['date'] for x in entries\
            if 'Sky Temperature (C)' in x['data'].keys()\
            and 'Ambient Temperature (C)' in x['data'].keys()\
            and 'Sky Safe' in x['data'].keys()]
    td_axes.plot_date(time, temp_diff, 'ko',\
                      markersize=2, markeredgewidth=0,\
                      drawstyle="default")
    td_axes.fill_between(time, -60, temp_diff, where=np.array(sky_safe)==1,\
                         color='green', alpha=0.5)
    td_axes.fill_between(time, -60, temp_diff, where=np.array(sky_safe)==0,\
                         color='red', alpha=0.5)
    plt.ylabel("Sky-Amb. Temp. (C)")
    plt.grid(which='major', color='k')
    plt.yticks(range(-100,100,10))
    td_axes.xaxis.set_major_locator(hours)
    td_axes.xaxis.set_major_formatter(hours_fmt)
    plt.xlim(start, end)
    plt.ylim(-60,10)

    ##-------------------------------------------------------------------------
    ## Plot Wind Speed vs. Time
    w_axes = plt.axes(plot_positions[1][1])
    wind_speed = [x['data']['Wind Speed (km/h)']\
                  for x in entries\
                  if 'Wind Speed (km/h)' in x['data'].keys()\
                  and 'Wind Safe' in x['data'].keys()\
                  and 'Gust Safe' in x['data'].keys()]
    wind_safe = [int(x['data']['Wind Safe']) + 2*int(x['data']['Gust Safe'])\
                  for x in entries\
                  if 'Wind Speed (km/h)' in x['data'].keys()\
                  and 'Wind Safe' in x['data'].keys()\
                  and 'Gust Safe' in x['data'].keys()]
    wind_mavg = movingaverage(wind_speed, 10)
    time = [x['date'] for x in entries\
                if 'Wind Speed (km/h)' in x['data'].keys()\
                and 'Wind Safe' in x['data'].keys()\
                and 'Gust Safe' in x['data'].keys()]
    w_axes.plot_date(time, wind_speed, 'ko', alpha=0.5,\
                     markersize=2, markeredgewidth=0,\
                     drawstyle="default")
    w_axes.plot_date(time, wind_mavg, 'b-',\
                     markersize=3, markeredgewidth=0,\
                     drawstyle="default")
    w_axes.plot_date([start, end], [0, 0], 'k-',ms=1)
    w_axes.fill_between(time, -5, wind_speed, where=np.array(wind_safe)==3,\
                         color='green', alpha=0.5)
    ## Gust Safe, Wind not Safe
    w_axes.fill_between(time, -5, wind_speed, where=np.array(wind_safe)==2,\
                         color='red', alpha=0.4)
    ## Gust not Safe, Wind Safe
    w_axes.fill_between(time, -5, wind_speed, where=np.array(wind_safe)==1,\
                         color='red', alpha=0.6)
    ## Gust not Safe, Wind not Safe
    w_axes.fill_between(time, -5, wind_speed, where=np.array(wind_safe)==0,\
                         color='red', alpha=0.8)
    plt.ylabel("Wind Speed (km/h)")
    plt.grid(which='major', color='k')
    plt.yticks(range(-100,100,10))
    w_axes.xaxis.set_major_locator(hours)
    w_axes.xaxis.set_major_formatter(hours_fmt)
    w_axes.xaxis.set_ticklabels([])
    plt.xlim(start, end)
    wind_max = max([45, np.ceil(max(wind_speed)/5.)*5.])
    plt.ylim(-2,55)


    ##-------------------------------------------------------------------------
    ## Plot Rain Frequency vs. Time
    rf_axes = plt.axes(plot_positions[2][1])
    rf_value = [x['data']['Rain Frequency']\
                  for x in entries\
                  if 'Rain Frequency' in x['data'].keys()\
                  and 'Rain Safe' in x['data'].keys()]
    rain_safe = [int(x['data']['Rain Safe'])\
                 for x in entries\
                 if 'Rain Frequency' in x['data'].keys()\
                 and 'Rain Safe' in x['data'].keys()]
    time = [x['date'] for x in entries\
            if 'Rain Frequency' in x['data'].keys()\
            and 'Rain Safe' in x['data'].keys()]
    rf_axes.plot_date(time, rf_value, 'ko',\
                      markersize=2, markeredgewidth=0,\
                      drawstyle="default")
    rf_axes.fill_between(time, 0, rf_value, where=np.array(rain_safe)==1,\
                         color='green', alpha=0.5)
    rf_axes.fill_between(time, 0, rf_value, where=np.array(rain_safe)==0,\
                         color='red', alpha=0.5)
    plt.ylabel("Rain Frequency")
    plt.grid(which='major', color='k')
    rf_axes.xaxis.set_major_locator(hours)
    rf_axes.xaxis.set_major_formatter(hours_fmt)
    rf_axes.xaxis.set_ticklabels([])
    plt.ylim(150,275)
    plt.xlim(start, end)



    ##-------------------------------------------------------------------------
    ## Safe/Unsafe vs. Time
    safe_axes = plt.axes(plot_positions[3][1])
    safe_value = [int(x['data']['Safe'])\
                  for x in entries\
                  if 'Safe' in x['data'].keys()]
    safe_time = [x['date'] for x in entries\
                  if 'Safe' in x['data'].keys()]

    safe_axes.plot_date(safe_time, safe_value, 'ko',\
                       markersize=2, markeredgewidth=0,\
                       drawstyle="default")
    safe_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value)==1,\
                     color='green', alpha=0.5)
    safe_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value)==0,\
                     color='red', alpha=0.5)
    plt.ylabel("Safe")
    plt.xlim(start, end)
    plt.ylim(-0.1, 1.1)
    plt.yticks([0,1])
    plt.grid(which='major', color='k')
    safe_axes.xaxis.set_major_locator(hours)
    safe_axes.xaxis.set_major_formatter(hours_fmt)



    ##-------------------------------------------------------------------------
    plot_filename = '{}.png'.format(date_string)
    plot_file = os.path.expanduser('~panoptes/weather_plots/{}'.format(plot_filename))
    plt.savefig(plot_file, dpi=dpi, bbox_inches='tight', pad_inches=0.10)


if __name__ == '__main__':
    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = argparse.ArgumentParser(
             description="Program description.")
    ## add flags
    parser.add_argument("-p", "--plot",
        action="store_true", dest="plot",
        default=False, help="Plot the data instead of querying new values.")
    parser.add_argument("-1", "--one",
        action="store_true", dest="one",
        default=False, help="Make one query only (default is infinite loop).")
    parser.add_argument("--no_mongo",
        action="store_false", dest="mongo",
        default=True, help="Do not send results to mongo database.")
    ## add arguments for telemetry queries
    parser.add_argument("--device",
        type=str, dest="device",
        help="Device address for the weather station (default = /dev/ttyUSB0)")
    parser.add_argument("-i", "--interval",
        type=float, dest="interval",
        default=30.,
        help="Time (in seconds) to wait between queries (default = 30 s)")
    ## add arguments for plot
    parser.add_argument("-d", "--date",
        type=str, dest="date",
        default=None,
        help="UT Date to plot")

    args = parser.parse_args()


    if not args.plot:
        ##-------------------------------------------------------------------------
        ## Update Weather Telemetry
        ##-------------------------------------------------------------------------
        AAG = AAGCloudSensor(serial_address=args.device)
        if args.one:
            AAG.update_weather(update_mongo=args.mongo)
        else:
            heaterPID = PID(Kp=1.0, Ki=0.01, Kd=1.0, output_limits=[0,100])
            now = dt.utcnow()
            while True:
                last = now
                now = dt.utcnow()
                loop_duration = (now - last).total_seconds()
                AAG.update_weather(update_mongo=args.mongo)                
                if AAG.rain_sensor_temp and AAG.ambient_temp:
                    if AAG.safe_dict['Rain']:
                        offset = 5.0
                    else:
                        offset = 20.0
                    rst = AAG.rain_sensor_temp.to(u.Celsius).value
                    amb = AAG.ambient_temp.to(u.Celsius).value
                    print('  PWM value = {:.0f} %, RST = {:.1f}, AmbTemp = {:.1f}, Delta = {:+.1f}, Target Delta = {:+.0f}'.format(\
                          AAG.PWM, rst, amb, rst-amb, offset))
                    new_PWM = heaterPID.recalculate(rst,\
                                                    dt=loop_duration,\
                                                    new_set_point=amb + offset)
                    print('  Pval, Ival, Dval = {:.1f}, {:.1f}, {:.1f}'.format(\
                          heaterPID.Pval, heaterPID.Ival, heaterPID.Dval))
                    print('  Updated PWM value = {:.1f} %'.format(new_PWM))
                    AAG.set_PWM(new_PWM)
                else:
                    if not AAG.rain_sensor_temp:
                        print('  No rain sensor temp value')
                    if not AAG.ambient_temp:
                        print('  No ambient temp value')
                print('  Sleeping for {:.0f} seconds ...'.format(args.interval))
                time.sleep(args.interval)
    else:
        plot_weather(args.date)

