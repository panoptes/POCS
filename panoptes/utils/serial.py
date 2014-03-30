import panoptes.utils.logger as logger

from threading import Thread
import serial

# Global variable
last_received = ''

def serial_receiving(ser):
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

@logger.has_logger
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
            Thread(target=serial_receiving, args=(self.ser,)).start()

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
