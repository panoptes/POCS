import time
from abc import ABC
from pathlib import Path
from typing import Optional

from panoptes.utils import error
from panoptes.utils import rs232
from panoptes.pocs.mount import AbstractMount, constants
from panoptes.utils.serializers import from_yaml
from panoptes.utils.time import current_time, CountdownTimer


class AbstractSerialMount(AbstractMount, ABC):

    def __init__(self, *args, **kwargs):
        """Initialize an AbstractSerialMount for the port defined in the config.

        Opens a connection to the serial device, if it is valid.
        """
        super(AbstractSerialMount, self).__init__(*args, **kwargs)

        # Setup our serial connection at the given port
        try:
            serial_config = self.get_config('mount.serial')
            self.serial = rs232.SerialData(**serial_config)
            if self.serial.is_connected is False:
                raise error.MountNotFound("Can't open mount")
        except KeyError:
            self.logger.critical(f'No config, cannot create mount: {self.get_config("mount")}')

    @property
    def port(self):
        return self.serial.ser.port

    def initialize(self, init_commands=None, set_rates=True, *arg, **kwargs):
        """ Initialize the connection with the mount and setup for location.

        iOptron mounts are initialized by sending the following two commands
        to the mount:

        * Version
        * MountInfo

        If the mount is successfully initialized, the `_setup_location_for_mount` method
        is also called.

        Returns:
            bool:   Returns the value from `self.is_initialized`.
        """
        init_commands = init_commands or ['version', 'mount_info']

        if not self.is_connected:
            self.logger.info(f'Connecting to mount {__name__}')
            self.connect()

        if self.is_connected and not self.is_initialized:
            self.logger.info(f'Initializing {__name__} mount')

            # We trick the mount into thinking it's initialized while we
            # initialize otherwise the `query` method will test
            # to see if initialized and be put into loop.
            self._is_initialized = True

            for init_cmd in init_commands:
                response = self.query(init_cmd)
                expected = self.commands.get(init_cmd).get('response')
                if response != expected:
                    self._is_initialized = False
                    raise error.MountNotFound(f'Problem initializing: {response} != {expected}')

            self._is_initialized = True
            self._setup_location_for_mount()
            if set_rates:
                self._set_initial_rates()

        self.logger.info(f'Mount initialized: {self.is_initialized}')

        return self.is_initialized

    def connect(self):
        """Connects to the mount via the serial port (`self.port`)

        Returns:
            Returns the self.is_connected property (bool) which checks
            the actual serial connection.
        """
        self.logger.debug('Connecting to mount')

        if not self.serial.is_connected:
            self.serial.connect()

        self._is_connected = True
        self.logger.info(f'Mount connected: {self.is_connected}')

        return self.is_connected

    def disconnect(self, should_park=True):
        super(AbstractSerialMount, self).disconnect(should_park=should_park)

        if self.serial:
            self.logger.debug("Closing serial port for mount")
            self.serial.disconnect()

        self._is_connected = self.serial.is_connected

    def set_tracking_rate(self, direction='ra', delta=0.0):
        """Set the tracking rate for the mount.

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
            self.logger.debug('Custom tracking rate set')
            response = self.query(f'set_custom_{direction}_tracking_rate', delta_str)
            self.logger.debug(f'Tracking response: {response}')
            if response:
                self.tracking_mode = constants.TrackingStatus.CUSTOM
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
        if self.is_initialized is False:
            raise AssertionError('Mount has not been initialized')

        self.serial.write(cmd)

    def read(self):
        """ Reads from the serial connection.

        Returns:
            str: Response from mount
        """
        if self.is_initialized is False:
            raise AssertionError('Mount has not been initialized')

        # Strip the line ending (#) and return
        response = self.serial.read().rstrip('#')
        return response

    def set_target_coordinates(self, coords):
        """ Sets the RA and Dec for the mount's current target.

        Args:
            coords (astropy.coordinates.SkyCoord): coordinates specifying target location

        Returns:
            bool:  Boolean indicating success
        """
        target_set = False

        # Save the skycoord coordinates
        self.logger.debug(f'Setting target coordinates: {coords}')
        self.target_coordinates = coords

        # Get coordinate format from mount specific class
        mount_coords = self._skycoord_to_mount_coord(self.target_coordinates)

        # Send coordinates to mount
        try:
            self.query('set_ra', mount_coords[0])
            self.query('set_dec', mount_coords[1])
            target_set = True
        except Exception as e:
            self.logger.warning(f'Problem setting mount coordinates: {mount_coords} {e!r}')

        self.logger.debug(f'Mount simulator set target coordinates: {target_set}')
        return target_set

    def get_current_coordinates(self):
        """ Reads out the current coordinates from the mount.

        Note:
            See `_mount_coord_to_skycoord` and `_skycoord_to_mount_coord` for translation of
            mount specific coordinates to astropy.coordinates.SkyCoord

        Returns:
            astropy.coordinates.SkyCoord
        """
        mount_coords = self.query('get_coordinates')

        # Turn the mount coordinates into a SkyCoord
        self.current_coordinates = self._mount_coord_to_skycoord(mount_coords)

        return self.current_coordinates

    def slew_to_target(self, blocking=False, timeout=180):
        """Slews to the currently assigned target coordinates.

        Slews the mount to the coordinates that have been assigned by `set_target_coordinates`.
        If no coordinates have been set, do nothing and return `False`, otherwise
        return response from the mount.

        If `blocking=True` then wait for up to `timeout` seconds for the mount
        to reach the `is_tracking` state. If a timeout occurs, raise a `pocs.error.Timeout`
        exception.

        Args:
            blocking (bool, optional): If command should block while slewing to
                home, default False.
            timeout (int, optional): Maximum time spent slewing to home, default
                180 seconds.

        Returns:
            bool: indicating success
        """
        success = False

        if self.is_parked:
            self.logger.info('Mount is parked')
        elif not self.has_target:
            self.logger.info('Target Coordinates not set')
        else:
            self.logger.debug('Slewing to target')
            success = self.query('slew_to_target')

            self.logger.debug(f"Mount response: {success}")
            if success:
                if blocking:
                    # Set up the timeout timer
                    self.logger.debug(f'Setting slew timeout timer for {timeout} sec')
                    timeout_timer = CountdownTimer(timeout)
                    block_time = 1  # seconds

                    while self.is_tracking is False:
                        if timeout_timer.expired():
                            self.logger.warning(f'slew_to_target timout: {timeout} seconds')
                            raise error.Timeout('Problem slewing to target')

                        self.logger.trace(f'Slewing to target, sleeping for {block_time} seconds')
                        timeout_timer.sleep(max_sleep=block_time)

                    self.logger.debug(f'Done with slew_to_target block')
            else:
                self.logger.warning('Problem with slew_to_target')

        return success

    def park(self, timeout=60, *args, **kwargs):
        """ Slews to the park position and parks the mount.

        Note:
            When mount is parked no movement commands will be accepted.

        Returns:
            bool: indicating success
        """

        self.set_park_coordinates()
        self.set_target_coordinates(self._park_coordinates)

        response = self.query('park')

        if response:
            self.logger.debug('Slewing to park')
        else:
            self.logger.warning('Problem with slew_to_park')

        movement_timer = CountdownTimer(timeout)
        while not self.at_mount_park:
            if movement_timer.expired():
                raise error.Timeout(f'Parking mount timout: {timeout} seconds')
            else:
                self._update_status()
                movement_timer.sleep(max_sleep=1)

        self._is_parked = True

        return response

    def unpark(self):
        """Unparks the mount.

        Does not do any movement commands but makes them available again.

        Returns:
            bool: indicating success
        """

        response = self.query('unpark')

        if response:
            self._is_parked = False
            self.logger.debug('Mount unparked')
        else:
            self.logger.warning('Problem with unpark')

        return response

    def move_direction(self, direction='north', seconds=1.0):
        """ Move mount in specified `direction` for given amount of `seconds`

        """
        seconds = float(seconds)
        assert direction in ['north', 'south', 'east', 'west']

        move_command = f'move_{direction}'
        self.logger.debug(f'Move command: {move_command}')

        try:
            now = current_time()
            self.logger.debug(f'Moving {direction} for {seconds} seconds. ')
            self.query(move_command)

            time.sleep(seconds)

            self.logger.debug(f'{(current_time() - now).sec} seconds passed before stop')
            self.query('stop_moving')
            self.logger.debug(f'{(current_time() - now).sec} seconds passed total')
        except KeyboardInterrupt:
            self.logger.warning('Keyboard interrupt, stopping movement.')
        except Exception as e:
            self.logger.warning(f'Problem moving! Make sure mount has stopped moving: {e!r}')
        finally:
            # Note: We do this twice. That's fine.
            self.logger.debug("Stopping movement")
            self.query('stop_moving')

    def slew_to_home(self, blocking=False, timeout=180):
        """Slews the mount to the home position.

        Note:
            Home position and Park position are not the same thing

        Args:
            blocking (bool, optional): If command should block while slewing to
                home, default False.
            timeout (int, optional): Maximum time spent slewing to home, default 180 seconds.

        Returns:
            bool: indicating success

        Args:
            blocking (bool, optional): If command should block while slewing to
                home, default False.
        """
        response = 0

        # Set up the timeout timer
        timeout_timer = CountdownTimer(timeout)
        block_time = 1  # seconds

        if not self.is_parked:
            # Reset target coordinates
            self._target_coordinates = None
            # Start the slew
            response = self.query('slew_to_home')
            if response and blocking:
                while self.is_home is False:
                    if timeout_timer.expired():
                        self.logger.warning(f'slew_to_home timout: {timeout} seconds')
                        response = 0
                        break
                    self.logger.trace(f'Slewing to home, sleeping for {block_time} seconds')
                    timeout_timer.sleep(max_sleep=block_time)
        else:
            self.logger.info('Mount is parked')

        return response

    def correct_tracking(self, correction_info, axis_timeout=30.):
        """ Make tracking adjustment corrections.

        Args:
            correction_info (dict[tuple]): Correction info to be applied, see
                `get_tracking_correction`.
            axis_timeout (float, optional): Timeout for adjustment in each axis,
                default 30 seconds.

        Raises:
            `error.Timeout`: Timeout error.
        """
        for axis, corrections in correction_info.items():
            if not axis or not corrections:
                continue

            offset = corrections[0]
            offset_ms = corrections[1]
            delta_direction = corrections[2]

            self.logger.info(f'{axis}: {delta_direction} {offset_ms:0.2f} ms {offset:0.2f}')
            self.query(f'move_ms_{delta_direction}', f'{offset_ms:05.0f}')

            # Adjust tracking for `axis_timeout` seconds then fail if not done.
            start_tracking_time = current_time()
            while self.is_tracking is False:
                if (current_time() - start_tracking_time).sec > axis_timeout:
                    raise error.Timeout(f'Tracking adjustment timeout: {axis}')

                self.logger.debug(f'Waiting for {axis} tracking adjustment')
                time.sleep(0.5)

    def _get_command(self, cmd, params=None):
        """Looks up appropriate command for mount."""
        full_command = ''

        # Get the actual command.
        cmd_info = self.commands.get(cmd)

        if cmd_info is not None:
            cmd = cmd_info.get('cmd')
            # Check if this command needs params.
            if 'params' in cmd_info:
                if params is None:
                    raise error.InvalidMountCommand(f'{cmd} expects: {cmd_info.get("params")!r}')
                cmd = f'{cmd}{params}'

            full_command = f'{self._pre_cmd}{cmd}{self._post_cmd}'
        else:
            self.logger.warning(f'No command for {cmd!r}')

        return full_command

    def _update_status(self):
        self._raw_status = self.query('get_status')
        self.logger.info(f'Raw status: {self._raw_status}')

        status = dict()

        # status_match = self._status_format.fullmatch(str(self._raw_status))
        # if status_match:
        #     status = status_match.groupdict()
        #
        #     # Lookup the text values and replace in status dict
        #     for k, v in status.items():
        #         status[k] = self._status_lookup[k][v]
        #
        #     self._state = status['state']
        #     self._movement_speed = status['movement_speed']
        #
        #     self._at_mount_park = 'Park' in self.state
        #     self._is_home = 'Stopped - Zero Position' in self.state
        #     self._is_tracking = 'Tracking' in self.state
        #     self._is_slewing = 'Slewing' in self.state
        #
        #     guide_rate = self.query('get_guide_rate')
        #     self.ra_guide_rate = int(guide_rate[0:2]) / 100
        #     self.dec_guide_rate = int(guide_rate[2:]) / 100
        #
        # status['timestamp'] = str(self.query('get_local_time'))
        # status['tracking_rate_ra'] = self.tracking_rate

        return status

    def _setup_commands(self, commands: Optional[dict] = None):
        """Setup the mount commands.

        Does any setup for the commands needed for this mount. Mostly responsible for
        setting the pre- and post-commands. We could also do some basic checking here
        to make sure required commands are in fact available.
        """
        self.logger.debug(f'Setting up commands for {self}')

        if commands is not None and len(commands) == 0:
            brand = self.get_config('mount.brand')
            model = self.get_config('mount.model')
            mount_dir = self.get_config('directories.mounts')

            commands_file = Path(mount_dir) / brand / f'{model}.yaml'

            try:
                self.logger.info(f'Loading mount commands file: {commands_file}')
                with commands_file.open() as f:
                    commands.update(from_yaml(f.read(), parse=False))
                    self.logger.debug(f'Mount commands updated from {commands_file}')
            except Exception as err:
                self.logger.warning(f'Error loading {commands_file=} {err!r}')

        # Get the pre- and post- commands
        self._pre_cmd = commands.setdefault('cmd_pre', ':')
        self._post_cmd = commands.setdefault('cmd_post', '#')

        self.logger.debug('Mount commands set up')
        return commands

    def _set_zero_position(self):
        """Sets the current position as the zero position. """
        self.logger.info('Setting zero position')
        return self.query('set_zero_position')

    def query(self, cmd, params=None):
        """Sends a query to the mount and returns response.

        Performs a send and then returns response. Will do a translate on cmd first. This should
        be the major serial utility for commands. Accepts an additional args that is passed
        along with the command. Checks for and only accepts one args param.

        Args:
            cmd (str): A command to send to the mount. This should be one of the
                commands listed in the mount commands yaml file.
            params (str, optional): Params to pass to serial connection

        Returns:
            bool: indicating success

        Deleted Parameters:
            *args: Parameters to be sent with command if required.
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        full_command = self._get_command(cmd, params=params)
        self.write(full_command)

        response = self.read()
        expected_response = self._get_expected_response(cmd)
        if str(response) != str(expected_response):
            self.logger.warning(f'Expected: {expected_response} Got: {response}')

        return response

    def _get_expected_response(self, cmd):
        """ Looks up appropriate response for command for telescope."""
        # Get the actual command
        cmd_info = self.commands.get(cmd)

        try:
            response = cmd_info.get('response')
            return response
        except (AttributeError, ValueError):
            raise error.InvalidMountCommand(f'No result for command {cmd}')
