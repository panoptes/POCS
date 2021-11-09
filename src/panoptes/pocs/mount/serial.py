import re
from abc import ABC

from panoptes.utils import error
from panoptes.utils import rs232
from panoptes.pocs.mount import AbstractMount


class AbstractSerialMount(AbstractMount, ABC):

    def __init__(self, location, *args, **kwargs):
        """Initialize an AbstractSerialMount for the port defined in the config.

        Opens a connection to the serial device, if it is valid.
        """
        super().__init__(location, *args, **kwargs)

        # This should be overridden by derived classes.
        self._status_format = re.compile('.*')

        # Setup our serial connection at the given port
        try:
            serial_config = self.get_config('mount.serial')
            self.serial = rs232.SerialData(**serial_config)
            if self.serial.is_connected is False:
                raise error.MountNotFound("Can't open mount")
        except KeyError:
            self.logger.critical("No serial config specified, cannot create mount: "
                                 f"{self.get_config('mount')}")
        except Exception as e:
            self.logger.critical(e)

    @property
    def _port(self):
        return self.serial.ser.port

    def connect(self):
        """Connects to the mount via the serial port (`self._port`)

        Returns:
            Returns the self.is_connected property (bool) which checks
            the actual serial connection.
        """
        self.logger.debug('Connecting to mount')

        if self.serial and not self.serial.is_connected:
            try:
                self._connect()
            except OSError as err:
                self.logger.error(f"{err!r}")
            except error.BadSerialConnection as err:
                self.logger.warning('Could not create serial connection to mount.')
                self.logger.warning(f'NO MOUNT CONTROL AVAILABLE {err!r}')

        self._is_connected = True
        self.logger.info(f'Mount connected: {self.is_connected}')

        return self.is_connected

    def disconnect(self):
        self.logger.debug("Closing serial port for mount")
        if self.serial:
            self.serial.disconnect()
        self._is_connected = self.serial.is_connected

    def set_tracking_rate(self, direction='ra', delta=0.0):
        """Set the tracking rate for the mount
        Args:
            direction (str, optional): Either `ra` or `dec`
            delta (float, optional): Offset multiple of sidereal rate, defaults to 0.0
        """
        delta = round(float(delta), 4)

        # Restrict range
        if delta > 0.01:
            delta = 0.01
        elif delta < -0.01:
            delta = -0.01

        # Dumb hack work-around for beginning 0
        delta_str_f, delta_str_b = f'{delta:+0.04f}'.split('.')
        delta_str_f += '0'  # Add extra zero
        delta_str = f'{delta_str_f}.{delta_str_b}'

        self.logger.debug(f'Setting tracking rate to sidereal {delta_str}')
        if self.query('set_custom_tracking'):
            self.logger.debug("Custom tracking rate set")
            response = self.query(f'set_custom_{direction}_tracking_rate', f'{delta_str}')
            self.logger.debug(f'Tracking response: {response}')
            if response:
                self.tracking = 'Custom'
                self.tracking_rate = 1.0 + delta
                self.logger.debug('Custom tracking rate sent')

    def write(self, cmd):
        """ Sends a string command to the mount via the serial port.

        First 'translates' the message into the form specific mount can understand using the
        mount configuration yaml file. This method is most often used from within `query` and
        may become a private method in the future.

        Note:
            This command currently does not support the passing of parameters. See `query` instead.

        Args:
            cmd (str): A command to send to the mount. This should be one of the commands listed
                in the mount commands yaml file.
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        # self.serial.reset_input_buffer()

        # self.logger.debug("Mount Query: {}".format(cmd))
        self.serial.write(cmd)

    def read(self, *args):
        """ Reads from the serial connection

        Returns:
            str: Response from mount
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        response = ''

        response = self.serial.read()

        self.logger.trace(f'Mount Read: {response}')

        # Strip the line ending (#) and return
        response = response.rstrip('#')

        # If it is an integer, turn it into one
        if response == '0' or response == '1':
            try:
                response = int(response)
            except ValueError:
                pass

        return response

    def _connect(self):
        """ Sets up serial connection """
        self.logger.debug(f'Making serial connection for mount at {self._port}')

        try:
            self.serial.connect()
        except Exception:
            raise error.BadSerialConnection(
                f'Cannot create serial connect for mount at port {self._port}')

        self.logger.debug('Mount connected via serial')

    def _get_command(self, cmd, params=None):
        """ Looks up appropriate command for telescope """
        full_command = ''

        # Get the actual command
        cmd_info = self.commands.get(cmd)

        if cmd_info is not None:
            # Check if this command needs params
            if 'params' in cmd_info:
                if params is None:
                    raise error.InvalidMountCommand(
                        f'{cmd} expects params: {cmd_info.get("params")}')
                full_command = f"{self._pre_cmd}{cmd_info.get('cmd')}{params}{self._post_cmd}"
            else:
                full_command = f"{self._pre_cmd}{cmd_info.get('cmd')}{self._post_cmd}"

            self.logger.trace(f'Mount Full Command: {full_command}')
        else:
            self.logger.warning(f'No command for {cmd}')

        return full_command

    def _update_status(self):
        self._raw_status = self.query('get_status')

        status = dict()

        status_match = self._status_format.fullmatch(self._raw_status)
        if status_match:
            status = status_match.groupdict()

            # Lookup the text values and replace in status dict
            for k, v in status.items():
                status[k] = self._status_lookup[k][v]

            self._state = status['state']
            self._movement_speed = status['movement_speed']

            self._at_mount_park = 'Park' in self.state
            self._is_home = 'Stopped - Zero Position' in self.state
            self._is_tracking = 'Tracking' in self.state
            self._is_slewing = 'Slewing' in self.state

            guide_rate = self.query('get_guide_rate')
            self.ra_guide_rate = int(guide_rate[0:2]) / 100
            self.dec_guide_rate = int(guide_rate[2:]) / 100

        status['timestamp'] = self.query('get_local_time')
        status['tracking_rate_ra'] = self.tracking_rate

        return status
