import astropy.units as u
import astropy.coordinates as coords
from astropy.time import Time
import ephem

from threading import Thread
import serial

import logging

class Convert():

    """
        Convert convenience functions
    """

    def __init__(self):
        pass

    def HA_to_Dec(self, J2000_coordinate, site):
        """
            HA to Dec
        """
        assert type(J2000_coordinate) == coords.FK5
        assert J2000_coordinate.equinox.value == 'J2000.000'

        # Coordinate precessed to Jnow (as an astropy coordinate object)
        Jnow_coordinate = J2000_coordinate.precess_to(Time.now())

        # Coordinate as a pyephem coordinate (J2000)
        RA_string, Dec_string = J2000_coordinate.to_string(
            precision=2, sep=':').split(' ')
        ephem_coordinate = ephem.FixedBody(
            RA_string, Dec_string, epoch=ephem.J2000)
        ephem_coordinate = ephem.readdb(
            'Polaris,f|M|F7,{},{},2.02,2000'.format(RA_string, Dec_string))
        ephem_coordinate.compute(site)

        HourAngle = ephem_coordinate.ra - site.sidereal_time()

        self.logger.info('Astropy J2000: {}'.format(
            J2000_coordinate.to_string(precision=2, sep=':')))
        self.logger.info(
            'pyephem Jnow:  {} {}'.format(ephem_coordinate.ra, ephem_coordinate.dec))
        self.logger.info('RA decimal = {:f}'.format(ephem_coordinate.ra))
        self.logger.info('LST decimal = {:f}'.format(site.sidereal_time()))
        self.logger.info('HA decimal = {:f}'.format(HourAngle))

        return HourAngleimport

log_levels = {
    'debug': logging.DEBUG,
    'warn': logging.WARN,
    'info': logging.INFO,
}


class Logger():

    """
        Sets up the logger for our program
    """

    def __init__(self,
                 log_file='panoptes.log',
                 profile='PanoptesLogger',
                 log_level='debug',
                 log_format='%(asctime)23s %(levelname)8s: %(message)s',
                 ):

        self.logger = logging.getLogger(profile)
        self.file_name = log_file

        self.logger.setLevel(log_levels[log_level])

        self.log_format = logging.Formatter(log_format)

        # Set up file output
        self.log_fh = logging.FileHandler(self.file_name)
        self.log_fh.setLevel(log_levels[log_level])
        self.log_fh.setFormatter(self.log_format)
        self.logger.addHandler(self.log_fh)

    def debug(self, msg):
        """ Send a debug message """

        self.logger.debug(msg)

    def info(self, msg):
        """ Send an info message """

        self.logger.info(msg)

    def error(self, msg):
        """ Send an error message """

        self.logger.error(msg)

    def warning(self, msg):
        """ Send an warning message """

        self.logger.warning(msg)

    def critical(self, msg):
        """ Send an critical message """

        self.logger.critical(msg)

    def exception(self, msg):
        """ Send an exception message """

        self.logger.exception(msg)


# Global variable
last_received = ''


def receiving(ser):
    """
    A callback that is attached to a Thread for the SerialData class
    """

    global last_received
    buffer = ''
    while True:
        buffer = buffer + ser.read(ser.inWaiting()).decode()
        if '\n' in buffer:
            lines = buffer.split('\n')  # Guaranteed to have at least 2 entries
            last_received = lines[-2]
            # If the Arduino sends lots of empty lines, you'll lose the
            # last filled line, so you could make the above statement conditional
            # like so: if lines[-2]: last_received = lines[-2]
            buffer = lines[-1]


class SerialData():

    """
    Listen to serial, return most recent numeric values
    Lots of help from here:
    http://stackoverflow.com/questions/1093598/pyserial-how-to-read-last-line-sent-from-serial-device
    """

    def __init__(self,
                 port="/dev/ttyACM0",
                 ):

        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=115200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                xonxoff=0,
                rtscts=0,
                interCharTimeout=None
            )
            time.sleep(2)

        except serial.serialutil.SerialException:
            self.ser = None
            self.logger.critical('Could not connect to serial port')
        else:
            Thread(target=receiving, args=(self.ser,)).start()

    def next(self):
        if not self.ser:
            return 0
        # return a float value or try a few times until we get one
        for i in range(40):
            raw_line = last_received
            try:
                return float(raw_line.strip())
            except ValueError:
                time.sleep(.005)
        return 0.

    def write(self, value):
        """
            For now just pass the value along to serial object
        """

        if not self.ser:
            return 0

        return self.ser.write(value)

    def read(self):
        """ Reads value """

        if not self.ser:
            return 0

        return self.ser.read()

    def __del__(self):
        if self.ser:
            self.ser.close()
