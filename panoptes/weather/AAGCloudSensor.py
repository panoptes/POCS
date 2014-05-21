import datetime
import os
import sys
import serial
import re
import time
import numpy as np

import astropy.units as u

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

    def __init__(self, serial_address='/dev/ttyS0', telemetry_file=os.path.join('/', 'var', 'log', 'PanoptesWeather')):
        super().__init__()
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
        ## Initialize Values
        self.last_update = None
        self.SkyTemp = None
        self.AmbTemp = None
        self.zener_voltage = None
        self.LDR_voltage = None
        self.rain_sensor_temp = None
        self.safe = None


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
        response = self.query('!T', '!2')
        AmbTemp = (float(response)/100. + 273.15) * u.K
        self.logger.info('Ambient Temperature is {:.1f}'.format(AmbTemp))
        return AmbTemp


    def get_sky_temperature(self):
        response = self.query('!S', '!1')
        SkyTemp = (float(response)/100. + 273.15) * u.K
        self.logger.info('Sky Temperature is {:.1f}'.format(SkyTemp))
        return SkyTemp


    def get_values(self):
        response = AAG.query('!C', ['!6', '!4', '!5'])
        zener_voltage = int(response[0])
        self.logger.info('Zener Voltage (0-1023) = {}'.format(zener_voltage))
        LDR_voltage = int(response[1])
        self.logger.info('LDR Voltage (0-1023) = {}'.format(LDR_voltage))
        rain_sensor_temp = int(response[2])
        self.logger.info('Ran Sensor Temp NTC (0-1023) = {}'.format(rain_sensor_temp))
        return (zener_voltage, LDR_voltage, rain_sensor_temp)


    def get_rain_freq(self):
        response = self.query('!E', '!R')
        rain_frequency = int(response)
        self.logger.info('Rain Frequency (0-1023) = {}'.format(rain_frequency))
        return rain_frequency


    def get_IR_errors(self):
        response = AAG.query('!D', ['!E1', '!E2', '!E3', '!E4'])
        IR_errors = [int(val) for val in response]
        self.logger.info('IR Errors: {} {} {} {}'.format(IR_errors[0], IR_errors[1], IR_errors[2], IR_errors[3]))
        return IR_errors


    def query_switch(self):
        status = None
        max_tries = 3
        tries = 0
        while not status:
            tries += 1
            if self.query('!F', '!X', max_tries=1):
                status = 'OPEN'
            elif self.query('!F', '!Y', max_tries=1):
                status = 'CLOSED'
            else:
                status = None
            if not status and tries >= max_tries:
                return None
        self.logger.info('Switch Status = {}'.format(status))
        return status


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
        if AAG.wind_speed_enabled():
            result = self.reversed_query('V!', '!w')
            if result:
                self.wind_speed = int(result) * u.km / u.hr
                self.logger.info('Wind speed = {}'.format(self.wind_speed))
            else:
                self.wind_speed = None
        else:
            self.wind_speed = None
        return self.wind_speed


    def get_weather_status(self):
        '''
        This follows the recommended procedure as described in the pdf manual:
        
        The device firmware was developed using MikroBasic. The RS232
        communications make use of microprocessor interrupts. On the other hand
        the rain frequency is measured using an internal counter and an
        interrupt microprocessor line.

        To prevent a mix up in the microprocessor interrupts, I strongly suggest
        the following:
        1) When communicating with the device send one command at a time and
           wait for the respective reply, checking that the correct number of
           characters has been received;
        2) Perform more than one single reading (say, 5) and apply a statistical
           analysis to the values to exclude any outlier. I am using 5 readings
           and calculate the average value (AVG) and standard deviation (STD).
           Any values that are outside the range AVG- STD and AVG+STD are
           excluded. The final value is the average of the values which were not
           excluded;
        3) The rain frequency measurement is the one that takes more time, 280ms
        4) The following reading cycle takes just less than 3 seconds to perform
            Perform 5 times
                get IR temperature        command "S!"
                get Ambient temperature   command "T!"
                get Values                command "C!"
                get Rain Frequency        command "E!"
            loop
            get PWM value                 command "Q!"
            get IR errors                 command "D!"
            get SWITCH status             command "F!"
        5) The Visual Basic 6 main program makes use of the RS232 control event
           to handle the device replies, thus avoiding the program to wait for
           the end of the above cycle.
        6) The algorithm that controls the heating cycles of the rain sensor is
           also programmed in the Visual Basic 6 main program and not in the
           device microprocessor.
        '''
        SkyTemps = []
        AmbTemps = []
        zener_voltages = []
        LDR_voltages = []
        rain_sensor_temps = []
        RainFreqs = []
        for i in range(0,5,1):
            SkyTemps.append(self.get_sky_temperature().value)
            AmbTemps.append(self.get_ambient_temperature().value)
            values = self.get_values()
            zener_voltages.append(values[0])
            LDR_voltages.append(values[1])
            rain_sensor_temps.append(values[2])
            RainFreqs.append(self.get_rain_freq())
        self.PWM_value = int(self.query('!Q', '!Q'))
        self.IR_errors = self.get_IR_errors()
        self.switch = self.query_switch()
        
        self.last_update = datetime.datetime.utcnow()
        self.SkyTemp = np.median(SkyTemps)
        self.AmbTemp = np.median(AmbTemps)
        self.zener_voltage = int(np.median(zener_voltages))
        self.LDR_voltage = int(np.median(LDR_voltages))
        self.rain_sensor_temp = int(np.median(rain_sensor_temps))
        self.rain_freq = int(np.median(RainFreqs))
        self.make_safety_decision()

        ## Write Information to Telemetry File
        if not os.path.exists(self.telemetry_file):
            ## Write Header Line
            info_line = '# AAG Cloud Sensor Telemetry (firmware version = {}, serial = {})'.format(self.firmware_version, self.serial_number)
            header_line = '{:22s}, {:>6s}, {:>10s}, {:>10s}, {:>9s}, {:>8s}, {:>8s}, {:>8s}, {:>8s}, {:>7s}, {:>6s}'.format(
                                          '# Date and Time',
                                          'Status',
                                          'SkyTemp(K)',
                                          'AmbTemp(K)',
                                          'ZenerVolt',
                                          'LDRVolt',
                                          'RainTemp',
                                          'RainFreq',
                                          'PWMValue',
                                          'Errors',
                                          'Switch',
                                          )
            with open(self.telemetry_file, 'a') as telemetryFO:
                self.logger.debug("Telemetry: '{}'".format(header_line))
                telemetryFO.write(info_line + '\n')
                telemetryFO.write(header_line + '\n')
            
        telemetry_line = '{:22s}, {:>6s}, {:>10.3f}, {:>10.3f}, {:>9d}, {:>8d}, {:>8d}, {:>8d}, {:>8d}, {:>7s}, {:>6s}'.format(
                                           self.last_update.strftime('%Y/%m/%d %H:%M:%S UT'),
                                           self.safe,
                                           self.SkyTemp,
                                           self.AmbTemp,
                                           self.zener_voltage,
                                           self.LDR_voltage,
                                           self.rain_sensor_temp,
                                           self.rain_freq,
                                           self.PWM_value,
                                           '{} {} {} {}'.format(self.IR_errors[0], self.IR_errors[1], self.IR_errors[2], self.IR_errors[3]),
                                           self.switch,
                                           )
        with open(self.telemetry_file, 'a') as telemetryFO:
            self.logger.debug("Telemetry: '{}'".format(telemetry_line))
            telemetryFO.write(telemetry_line + '\n')


    def make_safety_decision(self):
        '''
        Method makes decision whether conditions are safe or unsafe.
        '''
        self.safe = 'UNSAFE'




if __name__ == '__main__':
    AAG = AAGCloudSensor(serial_address='/dev/ttyS0')
    AAG.get_wind_speed()
    
