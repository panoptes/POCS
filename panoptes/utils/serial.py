import panoptes.utils.logger as logger
import panoptes.utils.error as error

import logging
from threading import Thread
import serial
import time

last_received = ''

@logger.set_log_level('debug')
@logger.has_logger
class SerialData():

    """
    Listen to serial, return most recent numeric values
    Lots of help from here:
    http://stackoverflow.com/questions/1093598/pyserial-how-to-read-last-line-sent-from-serial-device
    """

    def __init__(self,
                 port=None,
                 ):


        try:
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = 9600

            self.ser.bytesize=serial.EIGHTBITS
            self.ser.parity=serial.PARITY_NONE
            self.ser.stopbits=serial.STOPBITS_ONE
            self.ser.timeout=0.1
            self.ser.xonxoff=0
            self.ser.rtscts=0
            self.ser.interCharTimeout=None

            self.logger.debug('Serial connection set up to mount, sleeping for two seconds')
            time.sleep(2)

        except:
            self.ser = None
            self.logger.critical('Could not set up serial port')

        # try:
        #     Thread(target=self.serial_receiving, args=(self.ser,)).start()
        # except:
        #     self.logger.critical('Problem setting up Thread for Serial')
        #     raise error.BadSerialConnection(msg='Problem setting up Thread for Serial')

        self.logger.info('SerialData created')

    def connect(self):
        """ Actually set up the Thrad and connect to serial """

        self.logger.info('Serial connect called')
        if not self.ser.isOpen():
            try:
                self.ser.open()
            except serial.serialutil.SerialException as err:
                raise error.BadSerialConnection(msg=err)

        if type(self.ser) == 'panoptes.utils.serial.SerialData':
            Thread(target=serial_receiving, args=(self.ser,)).start()

        if not self.ser.isOpen():
            raise error.BadSerialConnection

        self.logger.info('Serial connection established to mount')
        return self.ser.isOpen()

    def next(self):
        assert self.ser
        assert self.ser.isOpen()
        
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
        assert self.ser
        assert self.ser.isOpen()

        return self.ser.write(value.encode())

    def read(self):
        """ Reads value """
        assert self.ser
        assert self.ser.isOpen()

        response_string = self.ser.readline().decode()
        self.logger.debug('response_string: {}'.format(response_string))
        
        return response_string

    def __del__(self):
        if self.ser:
            self.ser.close()

    def clear_buffer(self):
        """ Clear Response Buffer """
        count = 0
        while self.ser.inWaiting() > 0:
            count += 1
            contents = self.ser.read(1)
        self.logger.debug('Cleared {} bytes from buffer'.format(count))

    def serial_receiving(self,ser):
        """
        A callback that is attached to a Thread for the SerialData class
        """
        self.logger.info('serial_receiving called')
        buffer = ''
        while True:
            buffer = buffer + self.ser.read().decode('utf-8')
            self.logger.debug('buffer: {}'.format(buffer))
            if '\n' in buffer:
                lines = buffer.split('\n')  # Guaranteed to have at least 2 entries
                last_received = lines[-2]
                # If the Arduino sends lots of empty lines, you'll lose the
                # last filled line, so you could make the above statement conditional
                # like so: if lines[-2]: last_received = lines[-2]
                buffer = lines[-1]