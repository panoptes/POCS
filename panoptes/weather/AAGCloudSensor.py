#!/usr/bin/env python

import datetime
import os
import sys
import serial
import re
import time
import argparse
import numpy as np

import astropy.units as u
import astropy.table as table
import astropy.io.ascii as ascii

from panoptes.utils import logger
from panoptes.weather import WeatherStation

def movingaverage(interval, window_size):
    window= np.ones(int(window_size))/float(window_size)
    return np.convolve(interval, window, 'same')

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
    '''

    def __init__(self, serial_address='/dev/ttyS0'):
        super().__init__()
        ## Initialize Serial Connection
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
                        '!Q': '!Q\s+([\d\.\-]+)!',
                        '!S': '!1\s+([\d\.\-]+)!',
                        '!T': '!2\s+([\d\.\-]+)!',
                        '!K': '!K(\d+)\s*\\x00!',
                        'v!': '!v\s+([\d\.\-]+)!',
                        'V!': '!w\s+([\d\.\-]+)!',
                        'M!': '!M(.{12})',
                        }
        self.delays = {\
                       '!E': 0.400,
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
        if send in self.commands.keys():
            self.logger.debug('Sending command: {}'.format(self.commands[send]))
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
        if send in self.delays.keys():
            delay = self.delays[send]
        else:
            delay = 0.200
        expect = self.expects[send]
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
        data['Safe'] = self.make_safety_decision(data)

        if update_mongo:
            try:
                from panoptes.utils import config, logger, database
                # Connect to sensors collection
                sensors = database.PanMongo().sensors
                self.logger.info('Connected to mongo')
                sensors.insert({
                    "date": datetime.datetime.utcnow(),
                    "type": "weather",
                    "data": data
                })
                self.logger.info('  Inserted mongo document')
                sensors.update({"status": "current", "type": "weather"},\
                               {"$set": {\
                                   "date": datetime.datetime.utcnow(),\
                                   "type": "weather",\
                                   "data": data,\
                               }},\
                               True)
                self.logger.info('  Updated current status document')
            except:
                self.logger.warning('Failed to update mongo database')
        else:
            print('{:>26s}: {}'.format('Date and Time',\
                   datetime.datetime.utcnow().strftime('%Y/%m/%d %H:%M:%S')))
            for key in ['Ambient Temperature (C)', 'Sky Temperature (C)',\
                        'PWM Value', 'Rain Frequency', 'Safe']:
                if key in data.keys():
                    print('{:>26s}: {}'.format(key, data[key]))
                else:
                    print('{:>26s}: {}'.format(key, 'no data'))
            print('')

        return self.safe


    def make_safety_decision(self, data):
        '''
        Method makes decision whether conditions are safe or unsafe.
        '''
        self.safe = 'UNSAFE'
        return self.safe


def plot_weather(date_string):
    from panoptes.utils import config, logger, database
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
        date = datetime.datetime.utcnow()
        date_string = date.strftime('%Y%m%dUT')
        start = datetime.datetime(date.year, date.month, date.day, 0, 0, 0, 0)
        end = date+datetime.timedelta(0, 60*60)
    else:
        today = False
        date = datetime.datetime.strptime(date_string, '%Y%m%dUT')
        start = datetime.datetime(date.year, date.month, date.day, 0, 0, 0, 0)
        end = datetime.datetime(date.year, date.month, date.day, 23, 59, 59, 0)

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
    plot_positions = [ ( [0.000, 0.760, 0.465, 0.240], [0.535, 0.760, 0.465, 0.240] ),
                       ( [0.000, 0.495, 0.465, 0.240], [0.535, 0.495, 0.465, 0.240] ),
                       ( [0.000, 0.245, 0.465, 0.240], [0.535, 0.245, 0.465, 0.240] ),
                       ( [0.000, 0.000, 0.465, 0.235], [0.535, 0.000, 0.465, 0.235] ),
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
                     markersize=3, markeredgewidth=0,\
                     drawstyle="default")
    plt.ylabel("Ambient Temp. (C)")
    plt.grid(which='major', color='k')
    t_axes.xaxis.set_major_locator(hours)
    t_axes.xaxis.set_major_formatter(hours_fmt)
    plt.xlim(start, end)

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
                     markersize=3, markeredgewidth=0,\
                     drawstyle="default")
    plt.ylabel("Sky Temp. (C)")
    plt.grid(which='major', color='k')
    s_axes.xaxis.set_major_locator(hours)
    s_axes.xaxis.set_major_formatter(hours_fmt)
    s_axes.xaxis.set_ticklabels([])
    plt.xlim(start, end)

    ##-------------------------------------------------------------------------
    ## Plot Temperature Difference vs. Time
    td_axes = plt.axes(plot_positions[2][0])
    temp_diff = [x['data']['Sky Temperature (C)'] - x['data']['Ambient Temperature (C)']\
                 for x in entries\
                 if 'Sky Temperature (C)' in x['data'].keys()\
                 and 'Ambient Temperature (C)' in x['data'].keys()]
    time = [x['date'] for x in entries\
            if 'Sky Temperature (C)' in x['data'].keys()\
            and 'Ambient Temperature (C)' in x['data'].keys()]
    td_axes.plot_date(time, temp_diff, 'ko',\
                      markersize=3, markeredgewidth=0,\
                      drawstyle="default")
    plt.ylabel("Sky-Amb. Temp. (C)")
    plt.grid(which='major', color='k')
    td_axes.xaxis.set_major_locator(hours)
    td_axes.xaxis.set_major_formatter(hours_fmt)
    td_axes.xaxis.set_ticklabels([])
    plt.xlim(start, end)

    ##-------------------------------------------------------------------------
    ## Plot Wind Speed vs. Time
    w_axes = plt.axes(plot_positions[3][0])
    wind_speed = [x['data']['Wind Speed (km/h)']\
                  for x in entries\
                  if 'Wind Speed (km/h)' in x['data'].keys()]
    wind_mavg = movingaverage(wind_speed, 10)
    time = [x['date'] for x in entries\
                if 'Wind Speed (km/h)' in x['data'].keys()]
    w_axes.plot_date(time, wind_speed, 'ko',\
                     markersize=3, markeredgewidth=0,\
                     drawstyle="default")
    w_axes.plot_date(time, wind_mavg, 'b-',\
                     markersize=3, markeredgewidth=0,\
                     drawstyle="default")
    plt.ylabel("Wind Speed (km/h)")
    plt.grid(which='major', color='k')
    w_axes.xaxis.set_major_locator(hours)
    w_axes.xaxis.set_major_formatter(hours_fmt)
    plt.xlim(start, end)

    ##-------------------------------------------------------------------------
    ## Plot Brightness vs. Time
    ldr_axes = plt.axes(plot_positions[0][1])
    max_ldr = 28587999.99999969
    ldr_value = [x['data']['LDR Resistance (ohm)']\
                  for x in entries\
                  if 'LDR Resistance (ohm)' in x['data'].keys()]
    brightness = [10.**(2. - 2.*x/max_ldr) for x in ldr_value]
    time = [x['date'] for x in entries\
                if 'LDR Resistance (ohm)' in x['data'].keys()]
    ldr_axes.plot_date(time, brightness, 'ko',\
                       markersize=3, markeredgewidth=0,\
                       drawstyle="default")
    plt.ylabel("Brightness (%)")
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
    ## Plot Rain Frequency vs. Time
    rf_axes = plt.axes(plot_positions[1][1])
    rf_value = [x['data']['Rain Frequency']\
                  for x in entries\
                  if 'Rain Frequency' in x['data'].keys()]
    time = [x['date'] for x in entries\
                if 'Rain Frequency' in x['data'].keys()]
    rf_axes.plot_date(time, rf_value, 'ko',\
                      markersize=3, markeredgewidth=0,\
                      drawstyle="default")
    plt.ylabel("Rain Frequency")
    plt.grid(which='major', color='k')
    rf_axes.xaxis.set_major_locator(hours)
    rf_axes.xaxis.set_major_formatter(hours_fmt)
    rf_axes.xaxis.set_ticklabels([])
    plt.xlim(start, end)

    ##-------------------------------------------------------------------------
    ## Plot PWM Value vs. Time
    pwm_axes = plt.axes(plot_positions[2][1])
    pwm_value = [x['data']['PWM Value']\
                  for x in entries\
                  if 'PWM Value' in x['data'].keys()]
    time = [x['date'] for x in entries\
                if 'PWM Value' in x['data'].keys()]
    pwm_axes.plot_date(time, pwm_value, 'ko',\
                       markersize=3, markeredgewidth=0,\
                       drawstyle="default")
    plt.ylabel("PWM Value")
    plt.grid(which='major', color='k')
    pwm_axes.xaxis.set_major_locator(hours)
    pwm_axes.xaxis.set_major_formatter(hours_fmt)
    plt.xlim(start, end)

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
        default='/dev/ttyUSB0',
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
            while True:
                AAG.update_weather(update_mongo=args.mongo)
                time.sleep(args.interval)
    else:
        plot_weather(args.date)

