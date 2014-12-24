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

from panoptes.utils import logger, config, database, messaging, error
from panoptes.environment import WeatherStation


@logger.has_logger
@config.has_config
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

    def __init__(self, serial_address='/dev/ttyUSB0'):
        super().__init__()
        # Initialize Serial Connection
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

        # Connect directly to the sensors collection
        self.db = database.PanMongo().sensors

        # Initialize Values
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

        # Command Translation
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
        if self.AAG:
            # Clear Serial Buffer
            self.clear_buffer()
            # Query Device Name
            self.name = self.query('!A', '!N').strip()
            self.logger.info('Device Name is "{}"'.format(self.name))
            # Query Firmware Version
            self.firmware_version = float(self.query('!B', '!V'))
            self.logger.info('Firmware Version = {}'.format(self.firmware_version))
            # Query Serial Number
            self.serial_number = self.query('!K', '!K(\d{4})([\w\s\d]{8})')
            self.logger.info('Serial Number: {}'.format(self.serial_number))

    def check_weather(self):
        '''
        Queries the values for writing to the telemetry file. This is the main method
        for the weather station.
        '''
        self.get_ambient_temperature()
        self.get_sky_temperature()
        self.get_wind_speed()
        self.get_rain_frequency()
        self.get_PWM()
        self.get_values()
        self.get_errors()
        self.get_switch()
        self.make_safety_decision()
        self.last_update = datetime.datetime.utcnow()
        self.save()

    def clear_buffer(self):
        '''
        Clear response buffer.
        '''
        count = 0
        while self.AAG.inWaiting() > 0:
            count += 1
            contents = self.AAG.read(1)
        self.logger.debug('Cleared {} bytes from buffer'.format(count))

    def query(self, send, expects, max_tries=5, delay=0.5):
        '''
        Generic query for the AAG cloud sensor.  Give the string indicating the
        type of query and the string which you expect to match in the return.
        '''
        assert self.AAG
        self.clear_buffer()
        # Figure out what patterns to look for in response
        if type(expects) == str:
            nResponses = 1
            if len(expects) > 3:
                # If expects is a long string, it must be the full pattern
                ResponsePatterns = {expects[0:2]: expects}
                expects = [expects[0:2]]
            else:
                # If expects is a short string, it is just the leading flag characters
                ResponsePatterns = {expects: '{}'.format(expects.replace('!', '\!')) + '([\s\w\d\.]{13})'}
                expects = [expects]
            # In either case, also look for HSB
            ResponsePatterns['HSB'] = '\!' + chr(17) + '\s{12}0'
            expects.append('HSB')
        elif type(expects) == list:
            nResponses = len(expects)
            expects.append('HSB')
            ResponsePatterns = {}
            for expect in expects:
                ResponsePatterns[expect] = '{}'.format(
                    expect.replace('!', '\!')) + '([\s\w\d\.]{' + '{}'.format(15 - len(expect)) + '})'
            ResponsePatterns['HSB'] = '\!' + chr(17) + '\s{12}0'

        # Send command
        if send in self.commands.keys():
            self.logger.info('Sending command: {}'.format(self.commands[send]))
        else:
            self.logger.warning('Sending unknown command')
        send = send.encode('utf-8')
        nBytes = nResponses * 15
        complete_result = None
        tries = 0
        while not complete_result:
            tries += 1
            self.logger.debug("Sending: {}".format(send))
            self.AAG.write(send)
            time.sleep(delay)
            responseString = str(self.AAG.read((nResponses + 1) * 15), 'utf-8')
            response_list = []
            for i in range(0, nResponses + 1, 1):
                response_list.append(responseString[i * 15:(i + 1) * 15])
                self.logger.debug('Response: "{}"'.format(responseString[i * 15:(i + 1) * 15]))

            # Look for expected responses
            result = {}
            for response in response_list:
                for expect in expects:
                    IsMatch = re.match(ResponsePatterns[expect], response)
                    if IsMatch:
                        self.logger.debug('Found match to {:>3s}: "{}"'.format(expect, response))
                        if expect != 'HSB':
                            result[expect] = IsMatch.group(1)

            checklist = [expect in result.keys() for expect in expects if expect != 'HSB']
            if np.all(checklist):
                self.logger.info('Found all expected results')
                complete_result = result
            else:
                self.logger.debug('Did not find all expected results')
                if tries >= max_tries:
                    self.logger.warning('Did not find all expected results after {} tries'.format(max_tries))
                    return None
        if nResponses == 1:
            return complete_result[expects[0]]
        else:
            return complete_result

    def query_int_median(self, send, expect, navg=5, max_tries=5, clip=False):
        '''
        Wrapper around the query method which assumes the result is an integer
        and which queries five times and medians the result and return that.
        '''
        values = []
        for i in range(0, navg, 1):
            response = self.query(send, expect, max_tries=max_tries)
            try:
                response = int(response)
                if clip:
                    if int(response) > 1022:
                        response = 1022
                    if int(response) < 1:
                        response = 1
                values.append(int(response))
            except:
                pass
        if len(values) >= navg - 1:
            value = np.median(values)
            self.logger.debug('Queried {} {} {} times and result was {:.1f}'.format(send, expect, navg, value))
        else:
            value = None
        return value

    def get_ambient_temperature(self):
        '''
        Populates the self.ambient_temp property

        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 5.
        '''
        value = self.query_int_median('!T', '!2')
        if value:
            self.ambient_temp = (float(value) / 100. + 273.15) * u.K
            self.logger.info('Ambient Temperature = {:.1f}'.format(self.ambient_temp))
        else:
            self.ambient_temp = None

    def get_sky_temperature(self):
        '''
        Populates the self.sky_temp property

        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 1.

        Does this n times as recommended by the "Communication operational
        recommendations" section in Rs232_Comms_v100.pdf
        '''
        value = self.query_int_median('!S', '!1')
        if value:
            self.sky_temp = (float(value) / 100. + 273.15) * u.K
            self.logger.info('Sky Temperature = {:.1f}'.format(self.sky_temp))
        else:
            self.sky_temp = None

    def get_rain_frequency(self):
        '''
        Populates the self.rain_frequency property
        '''
        value = self.query_int_median('!E', '!R', clip=True)
        if value:
            self.rain_frequency = float(value) * 100. / 1023.
            self.logger.info('Rain Frequency = {:.1f}'.format(self.rain_frequency))
        else:
            self.rain_frequency = None

    def get_PWM(self):
        '''
        Populates the self.PWM property.

        Calculation is taken from Rs232_Comms_v100.pdf section "Converting values
        sent by the device to meaningful units" item 3.
        '''
        value = self.query_int_median('!Q', '!Q', clip=True)
        if value:
            self.PWM = float(value) * 100. / 1023.
            self.logger.info('PWM Value = {:.1f}'.format(self.PWM))
        else:
            self.PWM = None

    def get_values(self):
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
        for i in range(0, 5, 1):
            responses = AAG.query('!C', ['!6', '!4', '!5'])
            if responses:
                internal_voltage = 1023 * ZenerConstant / float(responses['!6'])
                internal_voltages.append(internal_voltage)
                LDR_resistance = LDRPullupResistance / ((1023. / float(responses['!4'])) - 1.)
                LDR_resistances.append(LDR_resistance)
                r = math.log(RainPullUpResistance / ((1023. / float(responses['!5'])) - 1.) / RainResAt25)
                rain_sensor_temp = 1. / (r / RainBeta + 1. / (ABSZERO + 25.))
                rain_sensor_temps.append(rain_sensor_temp)
        # Median Results
        if len(internal_voltages) >= 4:
            self.internal_voltage = np.median(internal_voltages) * u.volt
            self.logger.info('Internal Voltage = {}'.format(self.internal_voltage))
        else:
            self.internal_voltage = None
        if len(LDR_resistances) >= 4:
            self.LDR_resistance = np.median(LDR_resistances) * u.kiloOhm
            self.logger.info('LDR Resistance = {}'.format(self.LDR_resistance))
        else:
            self.LDR_resistance = None
        if len(rain_sensor_temps) >= 4:
            self.rain_sensor_temp = np.median(rain_sensor_temps) * u.K
            self.logger.info('Rain Sensor Temp = {}'.format(self.rain_sensor_temp))
        else:
            self.rain_sensor_temp = None

    def get_errors(self):
        '''
        Populates the self.IR_errors property
        '''
        response = AAG.query('!D', ['!E1', '!E2', '!E3', '!E4'])
        if response:
            self.errors = {'!E1': str(int(response['!E1'])),
                           '!E2': str(int(response['!E2'])),
                           '!E3': str(int(response['!E3'])),
                           '!E4': str(int(response['!E4']))}
            self.logger.info("Internal Error 1: '{}'".format(int(response['!E1'])))
            self.logger.info("Internal Error 2: '{}'".format(int(response['!E2'])))
            self.logger.info("Internal Error 3: '{}'".format(int(response['!E3'])))
            self.logger.info("Internal Error 4: '{}'".format(int(response['!E4'])))
        else:
            self.errors = {'!E1': None,
                           '!E2': None,
                           '!E3': None,
                           '!E4': None}

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

    def wind_speed_enabled(self, max_tries=3):
        '''
        Method returns true or false depending on whether the device supports
        wind speed measurements.
        '''
        result = self.query('v!', '!v')
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

        Medians 5 measurements.  This isn't mentioned specifically by the manual
        but I'm guessing it won't hurt.
        '''
        if AAG.wind_speed_enabled():
            WindSpeeds = []
            for i in range(0, 5, 1):
                response = self.query('V!', '!w')
                if response:
                    WindSpeeds.append(float(response))
            if len(WindSpeeds) >= 4:
                self.wind_speed = np.median(WindSpeeds) * u.km / u.hr
                self.logger.info('Wind speed = {:.1f}'.format(self.wind_speed))
            else:
                self.wind_speed = None
        else:
            self.wind_speed = 0. * u.km / u.hr

    def save(self):
        """
        Saves the telemetry data to the mongo db
        """
        self.logger.debug('Saving telemetry data')

        weather_data = {
            'type': 'aag_weather',
            'date': self.last_update
            'data': {
                   'Safe': self.safe,
                   'Ambient Temperature': self.ambient_temp.value,
                   'Sky Temperature': self.sky_temp.value,
                   'Rain Frequency': self.rain_frequency,
                   'Wind Speed': self.wind_speed.value,
                   'Internal Voltage': self.internal_voltage.value,
                   'LDR Resistance': self.LDR_resistance.value,
                   'Rain Sensor Temperature': self.rain_sensor_temp.value,
                   'PWM': self.PWM,
                   'E1': self.errors['!E1'],
                   'E2': self.errors['!E2'],
                   'E3': self.errors['!E3'],
                   'E4': self.errors['!E4'],
                   'Switch': self.switch
            }
        }

        # Insert record
        self.db.insert(weather_data)

        # Update the 'current' record
        weather_data['status'] = 'current'
        self.db.update(
            {"status": "current"},
            {"$set": {
                "date": self.last_update,
                "data": weather_data}
             },
            True
        )


    def make_safety_decision(self):
        '''
        Method makes decision whether conditions are safe or unsafe.
        '''
        self.safe = 'UNSAFE'


def decimal_hours(DTO):
    """
    Utility function used in plotting
    """
    assert type(DTO) == datetime.datetime
    decimal = DTO.hour + DTO.minute / 60. + DTO.second / 3600.
    return decimal


if __name__ == '__main__':
    # -------------------------------------------------------------------------
    # Parse Command Line Arguments
    # -------------------------------------------------------------------------
    # create a parser object for understanding command-line arguments
    parser = argparse.ArgumentParser(
        description="Program description.")
    # add flags
    parser.add_argument("-p", "--plot",
                        action="store_true", dest="plot",
                        default=False, help="Plot the data instead of querying new values.")
    # add arguments
    parser.add_argument("-d", "--date",
                        type=str, dest="plotdate",
                        help="Date to plot")
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Update Weather Telemetry
    # -------------------------------------------------------------------------
    if not args.plot:
        AAG = AAGCloudSensor(serial_address='/dev/ttyUSB0')
        AAG.check_weather()
        AAG.logger.info('Done.')

    # -------------------------------------------------------------------------
    # Make Plots
    # -------------------------------------------------------------------------
    if args.plot:
        import matplotlib.pyplot as pyplot
        import ephem
        # ---------------------------------------------------------------------
        # Read Telemetry
        # ---------------------------------------------------------------------
        dummyAAG = AAGCloudSensor(serial_address=None)
        if not args.plotdate:
            DateString = datetime.datetime.utcnow().strftime('%Y%m%d')
        else:
            DateString = args.plotdate
        dummyAAG.telemetry_file = os.path.join(
            '/', 'var', 'panoptes', 'logs', 'PanoptesWeather', 'telemetry_{}UT.txt'.format(DateString))
        assert os.path.exists(dummyAAG.telemetry_file)
        dummyAAG.logger.info('Reading telemetry for {}'.format(DateString))
        telemetry = dummyAAG._read_AAG_telemetry()

        time_decimal = [decimal_hours(datetime.datetime.strptime(
            val.decode('utf-8'), '%Y/%m/%d %H:%M:%S UT')) for val in telemetry['Timestamp']]
        time_decimal_column = table.Column(name='hours', data=time_decimal)
        telemetry.add_column(time_decimal_column, 2)

        dummyAAG.logger.debug('  Convert temperatures to C and F')
        ambient_temp_C = [val - 273.15 for val in telemetry['Ambient Temperature']]
        telemetry.add_column(table.Column(name='Ambient Temperature (C)', data=ambient_temp_C))
        ambient_temp_F = [32. + (val - 273.15) * 1.8 for val in telemetry['Ambient Temperature']]
        telemetry.add_column(table.Column(name='Ambient Temperature (F)', data=ambient_temp_F))

        sky_temp_C = [val - 273.15 for val in telemetry['Sky Temperature']]
        telemetry.add_column(table.Column(name='Sky Temperature (C)', data=sky_temp_C))
        sky_temp_F = [32. + (val - 273.15) * 1.8 for val in telemetry['Sky Temperature']]
        telemetry.add_column(table.Column(name='Sky Temperature (F)', data=sky_temp_F))

        RST_C = [val - 273.15 for val in telemetry['Rain Sensor Temperature']]
        telemetry.add_column(table.Column(name='Rain Sensor Temperature (C)', data=RST_C))
        RST_F = [32. + (val - 273.15) * 1.8 for val in telemetry['Rain Sensor Temperature']]
        telemetry.add_column(table.Column(name='Rain Sensor Temperature (F)', data=RST_F))

        sky_difference_C = []
        sky_difference_F = []
        for i in range(0, len(telemetry['Ambient Temperature (C)'])):
            diff_C = telemetry['Sky Temperature (C)'][i] - telemetry['Ambient Temperature (C)'][i]
            diff_F = telemetry['Sky Temperature (F)'][i] - telemetry['Ambient Temperature (F)'][i]
            sky_difference_C.append(diff_C)
            sky_difference_F.append(diff_F)
        telemetry.add_column(table.Column(name='Sky Difference (C)', data=sky_difference_C))
        telemetry.add_column(table.Column(name='Sky Difference (F)', data=sky_difference_F))

        # ---------------------------------------------------------------------
        # Use pyephem determine sunrise and sunset times
        # ---------------------------------------------------------------------
        dummyAAG.logger.debug('  Determine sunrise and sunset times')
        Observatory = ephem.Observer()
        Observatory.lon = "-155:34:33.9"
        Observatory.lat = "+19:32:09.66"
        Observatory.elevation = 3400.0
        Observatory.temp = 10.0
        Observatory.pressure = 680.0
        Observatory.date = DateString[0:4] + "/" + DateString[4:6] + "/" + DateString[6:8] + " 10:00:00.0"

        Observatory.horizon = '0.0'
        SunsetTime = Observatory.previous_setting(ephem.Sun()).datetime()
        SunriseTime = Observatory.next_rising(ephem.Sun()).datetime()
        SunsetDecimal = float(datetime.datetime.strftime(SunsetTime, "%H")) + float(
            datetime.datetime.strftime(SunsetTime, "%M")) / 60. + float(datetime.datetime.strftime(SunsetTime, "%S")) / 3600.
        SunriseDecimal = float(datetime.datetime.strftime(SunriseTime, "%H")) + float(
            datetime.datetime.strftime(SunriseTime, "%M")) / 60. + float(datetime.datetime.strftime(SunriseTime, "%S")) / 3600.
        Observatory.horizon = '-6.0'
        EveningCivilTwilightTime = Observatory.previous_setting(ephem.Sun(), use_center=True).datetime()
        MorningCivilTwilightTime = Observatory.next_rising(ephem.Sun(), use_center=True).datetime()
        EveningCivilTwilightDecimal = float(datetime.datetime.strftime(EveningCivilTwilightTime, "%H")) + float(datetime.datetime.strftime(
            EveningCivilTwilightTime, "%M")) / 60. + float(datetime.datetime.strftime(EveningCivilTwilightTime, "%S")) / 3600.
        MorningCivilTwilightDecimal = float(datetime.datetime.strftime(MorningCivilTwilightTime, "%H")) + float(datetime.datetime.strftime(
            MorningCivilTwilightTime, "%M")) / 60. + float(datetime.datetime.strftime(MorningCivilTwilightTime, "%S")) / 3600.
        Observatory.horizon = '-12.0'
        EveningNauticalTwilightTime = Observatory.previous_setting(ephem.Sun(), use_center=True).datetime()
        MorningNauticalTwilightTime = Observatory.next_rising(ephem.Sun(), use_center=True).datetime()
        EveningNauticalTwilightDecimal = float(datetime.datetime.strftime(EveningNauticalTwilightTime, "%H")) + float(datetime.datetime.strftime(
            EveningNauticalTwilightTime, "%M")) / 60. + float(datetime.datetime.strftime(EveningNauticalTwilightTime, "%S")) / 3600.
        MorningNauticalTwilightDecimal = float(datetime.datetime.strftime(MorningNauticalTwilightTime, "%H")) + float(datetime.datetime.strftime(
            MorningNauticalTwilightTime, "%M")) / 60. + float(datetime.datetime.strftime(MorningNauticalTwilightTime, "%S")) / 3600.
        Observatory.horizon = '-18.0'
        EveningAstronomicalTwilightTime = Observatory.previous_setting(ephem.Sun(), use_center=True).datetime()
        MorningAstronomicalTwilightTime = Observatory.next_rising(ephem.Sun(), use_center=True).datetime()
        EveningAstronomicalTwilightDecimal = float(datetime.datetime.strftime(EveningAstronomicalTwilightTime, "%H")) + float(datetime.datetime.strftime(
            EveningAstronomicalTwilightTime, "%M")) / 60. + float(datetime.datetime.strftime(EveningAstronomicalTwilightTime, "%S")) / 3600.
        MorningAstronomicalTwilightDecimal = float(datetime.datetime.strftime(MorningAstronomicalTwilightTime, "%H")) + float(datetime.datetime.strftime(
            MorningAstronomicalTwilightTime, "%M")) / 60. + float(datetime.datetime.strftime(MorningAstronomicalTwilightTime, "%S")) / 3600.

        dummyAAG.logger.debug('  Determine moon altitude values')
        Observatory.date = DateString[0:4] + "/" + DateString[4:6] + "/" + DateString[6:8] + " 0:00:01.0"
        TheMoon = ephem.Moon()
        TheMoon.compute(Observatory)
        MoonsetTime = Observatory.next_setting(ephem.Moon()).datetime()
        MoonriseTime = Observatory.next_rising(ephem.Moon()).datetime()
        MoonsetDecimal = float(datetime.datetime.strftime(MoonsetTime, "%H")) + float(
            datetime.datetime.strftime(MoonsetTime, "%M")) / 60. + float(datetime.datetime.strftime(MoonsetTime, "%S")) / 3600.
        MoonriseDecimal = float(datetime.datetime.strftime(MoonriseTime, "%H")) + float(
            datetime.datetime.strftime(MoonriseTime, "%M")) / 60. + float(datetime.datetime.strftime(MoonriseTime, "%S")) / 3600.

        MoonTimes = np.arange(0, 24, 0.1)
        MoonAlts = []
        for MoonTime in MoonTimes:
            TimeString = "%02d:%02d:%04.1f" % (
                math.floor(MoonTime), math.floor((MoonTime % 1) * 60), ((MoonTime % 1 * 60) % 1) * 60.0)
            Observatory.date = DateString[0:4] + "/" + DateString[4:6] + "/" + DateString[6:8] + " " + TimeString
            TheMoon.compute(Observatory)
            MoonAlts.append(TheMoon.alt * 180. / ephem.pi)
        MoonAlts = np.array(MoonAlts)

        MoonPeakAlt = max(MoonAlts)
        MoonPeakTime = (MoonTimes[(MoonAlts == MoonPeakAlt)])[0]
        MoonPeakTimeString = "%02d:%02d:%04.1f" % (
            math.floor(MoonPeakTime), math.floor((MoonPeakTime % 1) * 60), ((MoonPeakTime % 1 * 60) % 1) * 60.0)
        Observatory.date = DateString[0:4] + "/" + DateString[4:6] + "/" + DateString[6:8] + " " + MoonPeakTimeString
        TheMoon.compute(Observatory)
        MoonPhase = TheMoon.phase

        MoonFill = MoonPhase / 100. * 0.5 + 0.05

        # ---------------------------------------------------------------------
        # Make Plot of Entire UT Day
        # ---------------------------------------------------------------------
        dummyAAG.logger.debug('  Generate temperature plot')
        PlotFile = os.path.join('/', 'var', 'log', 'PanoptesWeather', 'weather_{}UT.png'.format(DateString))
        dpi = 100
        pyplot.ioff()
        Figure = pyplot.figure(figsize=(13, 9.5), dpi=dpi)
        PlotStartUT = 0
        PlotEndUT = 24
        nUTHours = 25

        # Plot Positions
        width = 1.000
        height = 0.230
        vspace = 0.015

        # ---------------------------------------------------------------------
        # Temperatures
        # ---------------------------------------------------------------------
        nplots = 1
        TemperatureAxes = pyplot.axes([0.0, 1.0 - nplots * height, 1.0, height], xticklabels=[])
        pyplot.plot(telemetry['hours'], telemetry['Ambient Temperature (F)'], 'ko-',
                    alpha=1.0, markersize=2, markeredgewidth=0)
        pyplot.plot(telemetry['hours'], telemetry['Rain Sensor Temperature (F)'], 'ro-',
                    alpha=0.4, markersize=2, markeredgewidth=0)
        pyplot.title('Weather Data for {}/{}/{} UT'.format(DateString[0:4], DateString[4:6], DateString[6:8]))
        pyplot.ylabel("Temperature (F)")
        pyplot.xticks(np.linspace(PlotStartUT, PlotEndUT, nUTHours, endpoint=True))
        pyplot.xlim(PlotStartUT, PlotEndUT)
        pyplot.grid()

        pyplot.yticks(np.linspace(0, 120, 13, endpoint=True))
        pyplot.ylim(min(telemetry['Ambient Temperature (F)']) - 5, max(telemetry['Ambient Temperature (F)']) + 5)

        # Overplot Twilights
        pyplot.axvspan(SunsetDecimal, EveningCivilTwilightDecimal, ymin=0, ymax=1, color='blue', alpha=0.1)
        pyplot.axvspan(EveningCivilTwilightDecimal, EveningNauticalTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.2)
        pyplot.axvspan(EveningNauticalTwilightDecimal, EveningAstronomicalTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.3)
        pyplot.axvspan(EveningAstronomicalTwilightDecimal, MorningAstronomicalTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.5)
        pyplot.axvspan(MorningAstronomicalTwilightDecimal, MorningNauticalTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.3)
        pyplot.axvspan(MorningNauticalTwilightDecimal, MorningCivilTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.2)
        pyplot.axvspan(MorningCivilTwilightDecimal, SunriseDecimal, ymin=0, ymax=1, color='blue', alpha=0.1)

        # Overplot Moon Up Time
        MoonAxes = TemperatureAxes.twinx()
        MoonAxes.set_ylabel('Moon Alt (%.0f%% full)' % MoonPhase, color='y')
        pyplot.plot(MoonTimes, MoonAlts, 'y-')
        pyplot.ylim(0, 100)
        pyplot.yticks([10, 30, 50, 70, 90], color='y')
        pyplot.xticks(np.linspace(PlotStartUT, PlotEndUT, nUTHours, endpoint=True))
        pyplot.xlim(PlotStartUT, PlotEndUT)
        pyplot.fill_between(MoonTimes, 0, MoonAlts, where=MoonAlts > 0, color='yellow', alpha=MoonFill)

        # ---------------------------------------------------------------------
        # Cloudiness
        # ---------------------------------------------------------------------
        nplots += 1
        CloudinessAxes = pyplot.axes([0.0, 1.0 - height * nplots - vspace * (nplots - 1), 1.0, height], xticklabels=[])
        pyplot.plot(telemetry['hours'], telemetry['Sky Difference (F)'], 'ko-',
                    alpha=1.0, markersize=2, markeredgewidth=0)
        pyplot.ylabel("Sky Difference (F)")
        pyplot.xticks(np.linspace(PlotStartUT, PlotEndUT, nUTHours, endpoint=True))
        pyplot.xlim(PlotStartUT, PlotEndUT)
        pyplot.grid()

        pyplot.yticks(np.linspace(-100, 0, 21, endpoint=True))
        pyplot.ylim(min(telemetry['Sky Difference (F)']) - 5, +5)

        # Overplot Twilights
        pyplot.axvspan(SunsetDecimal, EveningCivilTwilightDecimal, ymin=0, ymax=1, color='blue', alpha=0.1)
        pyplot.axvspan(EveningCivilTwilightDecimal, EveningNauticalTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.2)
        pyplot.axvspan(EveningNauticalTwilightDecimal, EveningAstronomicalTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.3)
        pyplot.axvspan(EveningAstronomicalTwilightDecimal, MorningAstronomicalTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.5)
        pyplot.axvspan(MorningAstronomicalTwilightDecimal, MorningNauticalTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.3)
        pyplot.axvspan(MorningNauticalTwilightDecimal, MorningCivilTwilightDecimal,
                       ymin=0, ymax=1, color='blue', alpha=0.2)
        pyplot.axvspan(MorningCivilTwilightDecimal, SunriseDecimal, ymin=0, ymax=1, color='blue', alpha=0.1)

        # Overplot Moon Up Time
        MoonAxes = TemperatureAxes.twinx()
        MoonAxes.set_ylabel('Moon Alt (%.0f%% full)' % MoonPhase, color='y')
        pyplot.plot(MoonTimes, MoonAlts, 'y-')
        pyplot.ylim(0, 100)
        pyplot.yticks([10, 30, 50, 70, 90], color='y')
        pyplot.xticks(np.linspace(PlotStartUT, PlotEndUT, nUTHours, endpoint=True))
        pyplot.xlim(PlotStartUT, PlotEndUT)
        pyplot.fill_between(MoonTimes, 0, MoonAlts, where=MoonAlts > 0, color='yellow', alpha=MoonFill)

        # ---------------------------------------------------------------------
        # Wind
        # ---------------------------------------------------------------------
        nplots += 1
        WindAxes = pyplot.axes([0.0, 1.0 - height * nplots - vspace * (nplots - 1), 1.0, height], xticklabels=[])
        pyplot.plot(telemetry['hours'], telemetry['Wind Speed'], 'ko-',
                    alpha=1.0, markersize=2, markeredgewidth=0)
        pyplot.ylabel("Wind Speed (km/h)")
        pyplot.xticks(np.linspace(PlotStartUT, PlotEndUT, nUTHours, endpoint=True))
        pyplot.xlim(PlotStartUT, PlotEndUT)
        pyplot.grid()

        pyplot.yticks(np.linspace(0, 100, 21, endpoint=True))
        pyplot.ylim(0, max([20, max(telemetry['Wind Speed']) + 5]))

        # ---------------------------------------------------------------------
        # Rain
        # ---------------------------------------------------------------------
        nplots += 1
#         print([0.0, 1.0-height*nplots-vspace*(nplots-1), 1.0, height])
        RainAxes = pyplot.axes([0.0, 1.0 - height * nplots - vspace * (nplots - 1), 1.00, height])
        pyplot.plot(telemetry['hours'], telemetry['LDR Resistance'] / 1000., 'bo-', label='LDR Resistance',
                    alpha=1.0, markersize=2, markeredgewidth=0)
        pyplot.plot(telemetry['hours'], telemetry['Rain Frequency'] / 1023. * 100, 'ro-', label='Rain Freq. (%)',
                    alpha=1.0, markersize=2, markeredgewidth=0)
        pyplot.ylabel("Rain/Wetness")
        pyplot.yticks(np.linspace(0, 100, 11, endpoint=True))
        pyplot.ylim(0, 100)
        pyplot.xticks(np.linspace(PlotStartUT, PlotEndUT, nUTHours, endpoint=True))
        pyplot.xlim(PlotStartUT, PlotEndUT)
        pyplot.grid()
        pyplot.xlabel('Time (UT Hours)')
        pyplot.legend(loc='best')


# Overplot Twilights
#         pyplot.axvspan(SunsetDecimal, EveningCivilTwilightDecimal, ymin=0, ymax=1, color='blue', alpha=0.1)
#         pyplot.axvspan(EveningCivilTwilightDecimal, EveningNauticalTwilightDecimal, ymin=0, ymax=1, color='blue', alpha=0.2)
#         pyplot.axvspan(EveningNauticalTwilightDecimal, EveningAstronomicalTwilightDecimal, ymin=0, ymax=1, color='blue', alpha=0.3)
#         pyplot.axvspan(EveningAstronomicalTwilightDecimal, MorningAstronomicalTwilightDecimal, ymin=0, ymax=1, color='blue', alpha=0.5)
#         pyplot.axvspan(MorningAstronomicalTwilightDecimal, MorningNauticalTwilightDecimal, ymin=0, ymax=1, color='blue', alpha=0.3)
#         pyplot.axvspan(MorningNauticalTwilightDecimal, MorningCivilTwilightDecimal, ymin=0, ymax=1, color='blue', alpha=0.2)
#         pyplot.axvspan(MorningCivilTwilightDecimal, SunriseDecimal, ymin=0, ymax=1, color='blue', alpha=0.1)
#
# Overplot Moon Up Time
#         MoonAxes = TemperatureAxes.twinx()
#         MoonAxes.set_ylabel('Moon Alt (%.0f%% full)' % MoonPhase, color='y')
#         pyplot.plot(MoonTimes, MoonAlts, 'y-')
#         pyplot.ylim(0,100)
#         pyplot.yticks([10,30,50,70,90], color='y')
#         pyplot.xticks(np.linspace(PlotStartUT,PlotEndUT,nUTHours,endpoint=True))
#         pyplot.xlim(PlotStartUT,PlotEndUT)
#         pyplot.fill_between(MoonTimes, 0, MoonAlts, where=MoonAlts>0, color='yellow', alpha=MoonFill)

        pyplot.savefig(PlotFile, dpi=dpi, bbox_inches='tight', pad_inches=0.10)
        dummyAAG.logger.info('  Done')
