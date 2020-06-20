import serial
import time
from warnings import warn
from contextlib import suppress

import astropy.units as u

from panoptes.pocs.focuser import AbstractFocuser


class Focuser(AbstractFocuser):
    """
    Focuser class for control of telescope focusers using the Optec FocusLynx focus controller.

    This includes the Starlight Instruments Focus Boss II controller, which is "powered by Optec"

    Args:
        port (str): device node of the serial port the focuser controller is connected to, e.g.
            '/dev/ttyUSB0'
        name (str, optional): default 'FocusLynx Focuser'
        initial_position (int, optional): if given the focuser will drive to this encoder position
            following initialisation.
        focuser_number (int, optional): for focus controllers that support more than one focuser
            set this number to specify which focuser should be controlled by this object. Default 1
        min_position (int, optional): minimum allowed focuser position in encoder units, default 0
        max_position (int, optional): maximum allowed focuser position in encoder units. If not
            given the value will be taken from the focuser's internal config.

    Additional positional and keyword arguments are passed to the base class, AbstractFocuser. See
    that class for a complete list.
    """

    def __init__(self,
                 port,
                 name='FocusLynx Focuser',
                 initial_position=None,
                 focuser_number=1,
                 min_position=0,
                 max_position=None,
                 *args, **kwargs):
        super().__init__(port=port, name=name, *args, **kwargs)
        self.logger.debug('Initialising FocusLynx focuser')

        try:
            self.connect()
        except (serial.SerialException, serial.SerialTimeoutException) as err:
            message = 'Error connecting to {} on {}: {}'.format(self.name, port, err)
            self.logger.error(message)
            warn(message)
            return

        self._focuser_number = focuser_number
        self._initialise()

        if min_position >= 0:
            self._min_position = int(min_position)
        else:
            self._min_position = 0
            message = "Specified min_position {} less than zero, ignoring!".format(min_position)
            warn(message)

        if max_position is not None:
            if max_position <= self._max_position:
                if max_position > self._min_position:
                    self._max_position = int(max_position)
                else:
                    raise ValueError('Max position must be greater than min position!')
            else:
                self.logger.warning("Specified max_position {} greater than focuser max {}!",
                                    max_position, self._max_position)

        if initial_position is not None:
            self.position = initial_position

    def __del__(self):
        with suppress(AttributeError):
            self._serial_port.close()
            self.logger.debug('Closed serial port {}'.format(self._port))

    def __str__(self):
        return "{} {} ({}) on {}".format(self.name, self._focuser_number, self.uid, self.port)

##################################################################################################
# Properties
##################################################################################################

    @property
    def uid(self):
        """
        The user set 'nickname' of the focuser. Must be <= 16 characters
        """
        try:
            uid = self._focuser_config['Nickname']
        except AttributeError:
            uid = self.port

        return uid

    @uid.setter
    def uid(self, nickname):
        if len(nickname) > 16:
            self.logger.warning('Truncated nickname {} to {} (must be <= 16 characters)',
                                nickname, nickname[:16])
            nickname = nickname[:16]
        command_str = '<F{:1d}SCNN{}>'.format(self._focuser_number, nickname)
        self._send_command(command_str, expected_reply='SET')
        self._get_focuser_config()

    @property
    def is_connected(self):
        """
        Checks status of serial port to determine if connected.
        """
        connected = False
        if self._serial_port:
            connected = self._serial_port.isOpen()
        return connected

    @AbstractFocuser.position.getter
    def position(self):
        """
        Current focus position in encoder units
        """
        self._update_focuser_status()
        return self._position

    @property
    def min_position(self):
        """
        Position of close limit of focus travel, in encoder units
        """
        return self._min_position

    @property
    def max_position(self):
        """
        Position of far limit of focus travel, in encoder units
        """
        return self._max_position

    @property
    def firmware_version(self):
        """
        Firmware version of the focuser controller
        """
        return self._hub_info['Hub FVer']

    @property
    def hardware_version(self):
        """
        Device type code of the focuser
        """
        return self.model

    @property
    def temperature(self):
        """
        Current temperature of the focuser, in degrees Celsus, as an astropy.units.Quantity
        """
        self._update_focuser_status()
        return self._temperature * u.Celsius

    @property
    def is_moving(self):
        """
        True if the focuser is currently moving
        """
        self._update_focuser_status()
        return self._is_moving

#################################################################################################
# Methods
##################################################################################################

    def connect(self):
        try:
            # Configure serial port.
            self._serial_port = serial.Serial(port=self.port,
                                              baudrate=115200,
                                              bytesize=serial.EIGHTBITS,
                                              parity=serial.PARITY_NONE,
                                              stopbits=serial.STOPBITS_ONE,
                                              timeout=1.0)

        except serial.SerialException as err:
            self._serial_port = None
            self.logger.critical('Could not open {}!'.format(self.port))
            raise err

        self.logger.debug('Established serial connection to {} on {}'.format(self.name, self.port))

    def move_to(self, position, blocking=True):
        """
        Moves focuser to a new position.

        Args:
            position (int): new focuser position, in encoder units. Must be between min_position
                and max_position.
            blocking (bool, optional): If True (default) will block until the move is complete,
                otherwise will return immediately.

        Returns:
            int: focuser position following the move. If blocking is True this will be the actual
                focuser position, if False it will be the target position.
        """
        position = int(position)
        if position < self._min_position:
            self.logger.error('Requested position {} less than min position, moving to {}!',
                              position, self._min_position)
            position = self._min_position
        elif position > self._max_position:
            self.logger.error('Requested position {} greater than max position, moving to {}!',
                              position, self._max_position)
            position = self._max_position

        self.logger.debug('Moving focuser {} to {}'.format(self.uid, position))
        command_str = '<F{:1d}MA{:06d}>'.format(self._focuser_number, position)
        self._send_command(command_str, expected_reply='M')

        # Focuser move commands are non-blocking. Only option is polling is_moving
        if blocking:
            while self.is_moving:
                time.sleep(1)
            if self.position != self._target_position:
                self.logger.warning("Focuser {} did not reach target position {}, now at {}!",
                                    self.uid, self._target_position, self._position)
            return self._position
        else:
            return position

    def move_by(self, increment, blocking=True):
        """
        Moves focuser by a given amount.

        Args:
            increment (int): distance to move the focuser, in encoder units. New position must be
                between min_position and max_position.
            blocking (bool, optional): If True (default) will block until the move is complete,
                otherwise will return immediately.

        Returns:
            int: focuser position following the move. If blocking is True this will be the actual
                focuser position, if False it will be the target position.
        """
        return self.move_to(self.position + increment)

    def halt(self):
        """
        Causes the focuser to immediately stop any movements
        """
        self._send_command(command_str='<F{:1d}HALT>'.format(self._focuser_number),
                           expected_reply='HALTED')
        message = ("Focuser {} halted".format(self.uid))
        self.logger.warning(message)
        warn(message)
        self._update_focuser_status()

##################################################################################################
# Private Methods
##################################################################################################

    def _initialise(self):
        self._get_hub_info()
        self._get_focuser_config()
        self._update_focuser_status()

        self.model = self._focuser_config['Dev Typ']
        self._max_position = int(self._focuser_config['Max Pos'])

        self.logger.info('{} initialised'.format(self))

    def _get_hub_info(self):
        self._hub_info = self._send_command(command_str='<FHGETHUBINFO>',
                                            expected_reply='HUB INFO')

    def _get_focuser_config(self):
        command_str = '<F{:1d}GETCONFIG>'.format(self._focuser_number)
        expected_reply = 'CONFIG{:1d}'.format(self._focuser_number)
        self._focuser_config = self._send_command(command_str, expected_reply)

    def _update_focuser_status(self):
        command_str = '<F{:1d}GETSTATUS>'.format(self._focuser_number)
        expected_reply = 'STATUS{:1d}'.format(self._focuser_number)
        self._focuser_status = self._send_command(command_str, expected_reply)

        self._position = int(self._focuser_status['Curr Pos'])
        self._target_position = int(self._focuser_status['Targ Pos'])
        self._is_moving = bool(int(self._focuser_status['IsMoving']))
        self._temperature = float(self._focuser_status['Temp(C)'])

    def _send_command(self, command_str, expected_reply):
        """
        Utility function that handles the common aspects of sending commands and
        parsing responses.
        """
        # Make sure we start with a clean slate
        self._serial_port.reset_output_buffer()
        self._serial_port.reset_input_buffer()
        # Send command
        self._serial_port.write(command_str.encode('ascii'))
        response = str(self._serial_port.readline(), encoding='ascii').strip()
        if not response:
            message = "No response to command '{}' from focuser {}".format(command_str, self.uid)
            self.logger.error(message)
            raise RuntimeError(message)

        # Should always get '!' back unless there's an error
        if response != '!':
            message = "Error sending command '{}' to focuser {}: {}".format(
                command_str, self.uid, response)
            self.logger.error(message)
            raise RuntimeError(message)

        # Next line identifies the command the focuser is replying to.
        command_echo = str(self._serial_port.readline(), encoding='ascii').strip()
        if command_echo != expected_reply:
            message = "Expected reply '{}' from {}, got '{}'".format(
                expected_reply, self.uid, command_echo)
            self.logger.error(message)
            raise RuntimeError(message)

        # For get info type commands then get several lines of key = value, then 'END'
        if expected_reply in ('HUB INFO',
                              'CONFIG1',
                              'CONFIG2',
                              'STATUS1',
                              'STATUS2'):
            info = {}
            response = str(self._serial_port.readline(), encoding='ascii').strip()
            while response != 'END':
                key, value = (item.strip() for item in response.split('='))
                info[key] = value
                response = str(self._serial_port.readline(), encoding='ascii').strip()
            return info

    def _add_fits_keywords(self, header):
        header = super()._add_fits_keywords(header)
        header.set('FOC-MOD', self.model, 'Focuser device type')
        header.set('FOC-ID', self.uid, 'Focuser nickname')
        header.set('FOC-HW', self.hardware_version, 'Focuser device type')
        header.set('FOC-FW', self.firmware_version, 'Focuser controller firmware version')
        header.set('FOC-TEMP', self.temperature.value, 'Focuser temperature (deg C)')
        return header
