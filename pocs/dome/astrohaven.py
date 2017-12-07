from pocs.dome import abstract_serial_dome


class Protocol:
    # Response codes
    BOTH_CLOSED = '0'
    BOTH_OPEN = '3'

    # TODO(jamessynge): Confirm and clarify meaning of '1' and '2'
    A_IS_OPEN = '1'
    B_IS_OPEN = '2'

    A_OPEN_LIMIT = 'x'  # Response to asking for A to open, and being at open limit
    A_CLOSE_LIMIT = 'X'  # Response to asking for A to close, and being at close limit

    B_OPEN_LIMIT = 'y'  # Response to asking for B to open, and being at open limit
    B_CLOSE_LIMIT = 'Y'  # Response to asking for B to close, and being at close limit

    # Action codes, echoed while happening
    CLOSE_A = 'A'
    OPEN_A = 'a'

    CLOSE_B = 'B'
    OPEN_B = 'b'

    OPEN_BOTH = 'O'
    CLOSE_BOTH = 'C'
    RESET = 'R'


class Dome(abstract_serial_dome.AbstractSerialDome):
    """Interface to an Astrohaven clamshell dome."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state = None

    @property
    def is_open(self):
        if self.is_connected:
            return TODO
        else:
            return False
        return self.state == 'Open'

    @property
    def is_closed(self):
        if self.is_connected:
            return TODO
        else:
            return False
        return self.state == 'Closed'

    @property
    def state(self):
        return self._state

    def disconnect(self):
        super().disconnect()
        self._state = 'Disconnected'

    def open(self):
        self._state = 'Open'
        return self.is_open

    def close(self):
        self._state = 'Closed'
        return self.is_closed

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def readLatestState(self):
        """Read the latest output from the Astrohaven dome controller, a Vision 130 PLC.
        
        Check dome open/close status.  Once a second while idle, dome sends 
        '0' for both sides closed, '1' and '2' for half open/half closed, and '3' 
	for both sides open."""

        self.ser.flushInput()
        startime = time.time()
        while (True):
            fback = self.ser.read()
            if (fback):
                self.laststate = int(fback)
                return fback
            elif (time.time() > (startime + Astrohaven.listen_timeout)):
                self.laststate = 0
                return None

            #verifyConnected

        self.verifyConnected()


"""Communicates with an Astrohaven observatory dome through a serial port.
Serial port must be passed in at instance creation."""

import serial
import time


class Astrohaven:

    listen_timeout = 3  # Max number of seconds to wait for a response
    move_timeout = 10  # Max number of seconds to run the door motors

    def __init__(self, comport=None):
        self.ready = False
        if comport is not None:
            self.openconn(comport)

    def openconn(self, comport):
        """Open a serial connection on port comport.  Listens for heartbeat from
        dome to verify connection."""
        self.ready = False
        try:
            self.ser = serial.Serial(comport, 9600, timeout=0.1)
            self.ready = True
        except:
            print('Failed to open serial port ', comport)
            self.ready = False
        if self.ready:
            # Listen for heartbeat
            if self.state() is None:
                print('Dome is not responding.')
                self.ready = False
            self.ser.flush()

    def state(self):
        """Check dome open/close status.  Once a second while idle, dome sends 
        '0' for both sides closed, '1' and '2' for half open/half closed, and '3' 
	for both sides open."""

        self.ser.flushInput()
        startime = time.time()
        while (True):
            fback = self.ser.read()
            if (fback):
                self.laststate = int(fback)
                return fback
            elif (time.time() > (startime + Astrohaven.listen_timeout)):
                self.laststate = 0
                return None

    def statetxt(self):
        """Return a text string describing dome's current status."""
        currstate = self.state()
        if (currstate == b'0'):
            return ("Both sides closed")
        elif (currstate == b'1'):
            return ('Side B open, side A closed')
        elif (currstate == b'2'):
            return ('Side A open, side B closed')
        elif (currstate == b'3'):
            return ('Both sides open')
        else:
            return ('Unexpected response from dome:' + currstate)

    def closeconn(self):
        if hasattr(self, 'ser'):
            self.ser.close()
        self.ready = False

    def nudgeshutter(self, side, direction):
        """Nudge one side of a dome open or closed.  "side" should be either 'A' or 'B';
        "direction" should be either 'open' or 'close'."""
        """ Returns True if movement occurred; False if clamshell has reached its limit."""
        if (direction.capitalize()[0] == 'O'):
            action = 'opening'
            acmd = b'a'
            bcmd = b'b'
            aresp = b'x'
            bresp = b'y'
        else:
            action = 'closing'
            acmd = b'A'
            bcmd = b'B'
            aresp = b'X'
            bresp = b'Y'
        if (side.capitalize()[0] == 'A'):
            self.ser.flushInput()
            self.ser.write(acmd)
            time.sleep(0.1)
            feedback = self.ser.read()
            return (feedback != aresp)
        else:
            self.ser.flushInput()
            self.ser.write(bcmd)
            time.sleep(0.1)
            feedback = self.ser.read()
            return (feedback != bresp)

    def fullmove(self, side, direction):
        # Open or close a clamshell all the way
        startime = time.time()
        while (self.nudgeshutter(side, direction)):
            if (time.time() > (startime + Astrohaven.move_timeout)):
                print('Timed out!  Check for hardware or communications problem.')
                break
            self.ser.flushInput()

    def fullopen(self):
        # Open both sides of the dome
        self.fullmove('A', 'Open')
        self.fullmove('B', 'Open')

    def fullclose(self):
        # Close both sides of the dome
        self.fullmove('A', 'Close')
        self.fullmove('B', 'Close')
