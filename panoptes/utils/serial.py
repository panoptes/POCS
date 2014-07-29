import panoptes.utils.logger as logger
import panoptes.utils.error as error

import logging
from threading import Thread
import serial
import time

@logger.has_logger
class SerialData():

    """
    Main serial class
    """

    def __init__(self, port=None):

        try:
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = 9600

            self.ser.bytesize = serial.EIGHTBITS
            self.ser.parity = serial.PARITY_NONE
            self.ser.stopbits = serial.STOPBITS_ONE
            self.ser.timeout = 0.1
            self.ser.xonxoff = 0
            self.ser.rtscts = 0
            self.ser.interCharTimeout = None

            self.logger.debug(
                'Serial connection set up to mount, sleeping for two seconds')
            time.sleep(2)

        except:
            self.ser = None
            self.logger.critical('Could not set up serial port')

        self.logger.info('SerialData created')

    @property
    def is_connected(self):
        """
        Checks the serial connection on the mount to determine if connection is open
        """
        return self.ser.isOpen()

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

    def write(self, value):
        """
            For now just pass the value along to serial object
        """
        assert self.ser
        assert self.ser.isOpen()

        self.logger.debug('Serial write: {}'.format(value))
        return self.ser.write(value.encode())

    def read(self):
        """ 
        Reads value using readline 
        If no response is given, delay and then try to read again. Fail after 10 attempts
        """
        assert self.ser
        assert self.ser.isOpen()

        retry_limit = 7
        delay = 0.5

        i = 0
        while True:
            response_string = self.ser.readline().decode()
            if response_string > '' or i > retry_limit: break
            time.sleep(delay)
            i += 1

        self.logger.debug('Serial read: {}'.format(response_string))

        return response_string

    def clear_buffer(self):
        """ Clear Response Buffer """
        count = 0
        while self.ser.inWaiting() > 0:
            count += 1
            contents = self.ser.read(1)

        self.logger.debug('Cleared {} bytes from buffer'.format(count))

    def __del__(self):
        if self.ser:
            self.ser.close()
