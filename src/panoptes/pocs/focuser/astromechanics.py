from panoptes.utils import error
from panoptes.utils.serial.device import find_serial_port
from panoptes.pocs.focuser.serial import AbstractSerialFocuser


class Focuser(AbstractSerialFocuser):
    """
    Focuser class for control of a Canon DSLR lens via an Astromechanics
    Engineering Canon EF/EF-S adapter.

    Args:
        name (str, optional): default 'Astromechanics Focuser'
        model (str, optional): default 'Canon EF/EF-S'
        vendor_id (str, optional): idVendor of device, can be retrieved with lsusb -v from terminal.
        product_id (str, optional): idProduct of device, can be retrieved with lsusb -v from terminal.

    Additional positonal and keyword arguments are passed to the base class,
    AbstractSerialFocuser. See that base class documentation for a complete list.

    Min/max commands do not exist for the astromechanics controller, as well as
    other commands to get serial numbers and library/hardware versions. However,
    as they are marked with the decorator @abstractmethod, we have to override them.
    """

    def __init__(self, name='Astromechanics Focuser', model='Canon EF-232', vendor_id=None,
                 product_id=None, *args, **kwargs):
        # Check if have device, raise error.NotFound if unable to find.
        self._serial_number = find_serial_port(vendor_id, product_id)
        self._vendor_id = vendor_id
        self._product_id = product_id

        super().__init__(name=name, model=model, *args, **kwargs)
        self.logger.debug(f'Initializing {name}')

    ################################################################################################
    # Properties
    ################################################################################################

    @AbstractSerialFocuser.position.getter
    def position(self):
        """
        Returns current focus position in the lens focus encoder units.
        """
        response = self._send_command("P").rstrip("#")
        return int(response)

    @property
    def min_position(self):
        """
        Returns position of close limit of focus travel, in encoder units.
        """
        return self._min_position

    @property
    def max_position(self):
        """
        Returns position of far limit of focus travel, in encoder units.
        """
        return None

    ################################################################################################
    # Public Methods
    ################################################################################################

    def connect(self, port):
        self._connect(port)

        return self._serial_number

    def move_to(self, new_position):
        """
        Moves focuser to a new position.

        Args:
            new_position (int): new focuser position, in encoder units

        Returns:
            int: focuser position following the move, in encoder units.

        Does not do any checking of the requested position but will warn if the lens reports
        hitting a stop.
        """
        self._is_moving = True
        try:
            self._send_command(f'M{int(new_position):d}')
        finally:
            # Focuser move commands block until the move is finished, so if the command has
            # returned then the focuser is no longer moving.
            self._is_moving = False

        self.logger.debug(f"Moved to encoder position {self.position}")
        return self.position

    def move_by(self, increment):
        """
        Move focuser by a given amount.

        Args:
            increment (int): distance to move the focuser, in encoder units.

        Returns:
            int: distance moved, in encoder units.
        """
        self._is_moving = True
        try:
            new_pos = self.position + increment
            self._send_command(f'M{int(new_pos):d}')
        finally:
            # Focuser move commands block until the move is finished, so if the command has
            # returned then the focuser is no longer moving.
            self._is_moving = False

        self.logger.debug(f"Moved by {increment} encoder units. Current position is {new_pos}")
        return new_pos

    ################################################################################################
    # Private Methods
    ################################################################################################

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
        self._serial_port.reset_input_buffer()

        # Send command
        self._serial_io.write(f'{pre_cmd}{command}{post_cmd}\r')

        return self._serial_io.readline(self._serial_port.in_waiting)

    def _initialise(self):
        # Initialise the aperture motor. This also has the side effect of fully opening the iris.
        self._initialise_aperture()

        # Initalise focus. First move the focus to the close stop.
        self._move_zero()
        self._min_position = 0

        self.logger.info(f'{self} initialised')

    def _initialise_aperture(self):
        self.logger.debug('Initialising aperture motor')
        self._is_moving = True
        try:
            self._send_command('A00')
            self.logger.debug('Aperture initialised')
        finally:
            self._is_moving = False

    def _move_zero(self):
        self.logger.debug('Setting focus encoder zero point')
        if self.position != 0:
            self._is_moving = True
            try:
                # Set focuser to 0 position
                self._send_command('M0')
                self.logger.debug('Focuser has been set to encoder position 0')
            finally:
                self._is_moving = False
        else:
            self.logger.debug('Focuser already at encoder position 0')
