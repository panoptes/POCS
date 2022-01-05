from panoptes.utils.serial.device import find_serial_port
from panoptes.pocs.focuser.serial import AbstractSerialFocuser


class Focuser(AbstractSerialFocuser):
    """
    Focuser class for control of a Canon DSLR lens via an Astromechanics
    Engineering Canon EF/EF-S adapter.

    Min/max commands do not exist for the astromechanics controller, as well as
    other commands to get serial numbers and library/hardware versions. However,
    as they are marked with the decorator @abstractmethod, we have to override them.

    Astromechanics focuser are currently very slow to respond to position queries. When they do
    respond, they give the exact position that was requested by the last move_to command (i.e.
    there is no reported position error). We can therefore avoid such queries by storing the
    current position in memory.
    """

    def __init__(self, name='Astromechanics Focuser', model='Canon EF-232', vendor_id=0x0403,
                 product_id=0x6001, zero_position=-25000, baudrate=38400, *args, **kwargs):
        """
        Args:
            name (str, optional): default 'Astromechanics Focuser'
            model (str, optional): default 'Canon EF/EF-S'
            vendor_id (str, optional): idVendor of device, can be retrieved with lsusb -v from
                terminal.
            product_id (str, optional): idProduct of device, can be retrieved with lsusb -v from
                terminal.
            zero_position (int, optional): Position to use to calibrate the zero position of the
                focuser. This should be a negative number larger than the possible range of encoder
                values. Default: -25000.
            baudrate (int, optional): The baudrate of the serial device. Default: 38400.
        """
        self._position = None

        if vendor_id and product_id:
            port = find_serial_port(vendor_id, product_id)
            self._vendor_id = vendor_id
            self._product_id = product_id

        self._zero_position = zero_position

        super().__init__(name=name, model=model, baudrate=baudrate, port=port, *args, **kwargs)

    # Properties

    @AbstractSerialFocuser.position.getter
    def position(self):
        return self._position

    @property
    def min_position(self):
        """
        Returns position of close limit of focus travel, in encoder units.
        """
        return 0

    @property
    def max_position(self):
        """
        Returns position of far limit of focus travel, in encoder units.
        """
        return None

    # Public Methods

    def move_to(self, position):
        """ Moves focuser to a new position.
        Does not do any checking of the requested position but will warn if the lens reports
        hitting a stop.
        Args:
            position (int): new focuser position, in encoder units.
        Returns:
            int: focuser position following the move, in encoder units.
        """
        self._is_moving = True
        try:
            self._send_command(f'M{int(position):d}#')
            self._position = position
        finally:
            # Focuser move commands block until the move is finished, so if the command has
            # returned then the focuser is no longer moving.
            self._is_moving = False

        self.logger.debug(f"Moved to encoder position {self.position}")
        return self.position

    def move_by(self, increment):
        """ Move focuser by a given amount.
        Does not do any checking of the requested increment but will warn if the lens reports
        hitting a stop.
        Args:
            increment (int): distance to move the focuser, in encoder units.
        Returns:
            int: focuser position following the move, in encoder units.
        """
        new_pos = self.position + increment
        return self.move_to(new_pos)

    # Private Methods

    def _initialize(self):
        # Initialise the aperture motor. This also has the side effect of fully opening the iris.
        self._initialise_aperture()

        # Calibrate near stop of the astromechanics focuser.
        self._move_zero()

    def _send_command(self, command, pre_cmd='', post_cmd='#'):
        """
        Sends a command to the focuser adaptor and retrieves the response.
        Args:
            command (string): command string to send (without newline), e.g. 'P#'.
            pre_cmd (string): Prefix for the command, default empty string.
            post_cmd (string): Post for the command, default '#' for astromechs.
        Returns:
            string:  containing the '\r' terminated lines of the response from the adaptor.
        """
        if not self.is_connected:
            self.logger.critical(f"Attempt to send command to {self} when not connected!")
            return

        # Clear the input buffer in case there's anything left over in there.
        self._serial.reset_input_buffer()

        # Send command
        self._serial.write(f'{pre_cmd}{command}{post_cmd}\r')

        return self._serial.read()

    def _initialise_aperture(self):
        """ Initialise the aperture motor. """
        self.logger.debug('Initialising aperture motor')
        self._is_moving = True
        try:
            self._send_command('A00')
            self.logger.debug('Aperture initialised')
        finally:
            self._is_moving = False

    def _move_zero(self):
        """ Move the focuser to its zero position and set the current position to zero. """
        self.logger.debug(f"Setting focus encoder zero point at position={self._zero_position}")
        self._is_moving = True
        try:
            # Move to a negative position that is larger than the movement range of the lens.
            self.move_to(self._zero_position)

            # Set the current position as 0
            self._position = 0
            self.logger.debug(f"Zero point of focuser has been calibrated at {self._zero_position}")
        finally:
            self._is_moving = False
