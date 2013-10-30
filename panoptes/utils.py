"""
Listen to serial, return most recent numeric values
Lots of help from here:
http://stackoverflow.com/questions/1093598/pyserial-how-to-read-last-line-sent-from-serial-device
"""
from threading import Thread
import time
import serial
import logging


class Logger():

    """
        Sets up the logger for our program
    """


    def __init__(self):

        self.logger = logging.getLogger('PanoptesLogger')
        self.logger.setLevel(logging.DEBUG)

        self.log_format = logging.Formatter('%(asctime)23s %(levelname)8s: %(message)s')

        # Set up file output
        self.file_name = 'panoptes.log'
        self.log_fh = logging.FileHandler(self.file_name)
        self.log_fh.setLevel(logging.DEBUG)
        self.log_fh.setFormatter(self.log_format)
        self.logger.addHandler(self.log_fh)

    def debug(self, msg):
        """ Send a debug message """

        self.logger.debug(msg)


last_received = ''
def receiving(ser):
    global last_received
    buffer = ''
    while True:
        buffer = buffer + ser.read(ser.inWaiting()).decode()
        if '\n' in buffer:
            lines = buffer.split('\n') # Guaranteed to have at least 2 entries
            last_received = lines[-2]
            # If the Arduino sends lots of empty lines, you'll lose the
            # last filled line, so you could make the above statement conditional
            # like so: if lines[-2]: last_received = lines[-2]
            buffer = lines[-1]

class SerialData(object):
    """
       Serial class
    """
    def __init__(self, init=50):
        try:
            self.ser = serial.Serial(
                port = '/dev/ttyACM0',
                baudrate = 115200,
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

    def __del__(self):
        if self.ser:
            self.ser.close()
