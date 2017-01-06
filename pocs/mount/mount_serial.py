import os
import time
import yaml

from ..utils import current_time
from ..utils import error
from ..utils import rs232

from .mount import AbstractMount


class AbstractSerialMount(AbstractMount):

    def __init__(self,
                 location,
                 commands=dict(),
                 *args, **kwargs
                 ):
        """
        """
        super(AbstractSerialMount, self).__init__(
            commands=commands,
            location=location,
            *args,
            **kwargs
        )

        # Setup our serial connection at the given port
        try:
            self._port = self.config['mount']['port']
        except KeyError:
            self.logger.error('No mount port specified, cannot create mount\n {}'.format(self.config['mount']))

        try:
            self.serial = rs232.SerialData(port=self._port)
        except Exception as err:
            self.serial = None
            raise error.MountNotFound(err)


##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """ Connects to the mount via the serial port (`self._port`)

        Returns:
            bool:   Returns the self.is_connected property which checks the actual serial connection.
        """
        self.logger.debug('Connecting to mount')

        if self.serial.ser and self.serial.ser.isOpen() is False:
            try:
                self._connect_serial()
            except OSError as err:
                self.logger.error("OS error: {0}".format(err))
            except error.BadSerialConnection as err:
                self.logger.warning('Could not create serial connection to mount.')
                self.logger.warning('NO MOUNT CONTROL AVAILABLE\n{}'.format(err))

        self._is_connected = True
        self.logger.info('Mount connected: {}'.format(self.is_connected))

        return self.is_connected

    def status(self):
        """
        Gets the system status

        Note:
            From the documentation (iOptron ® Mount RS-232 Command Language 2014 Version 2.0 August 8th, 2014)

            Command: “:GAS#”
            Response: “nnnnnn#”

            See `self._status_lookup` for more information.

        Returns:
            dict:   Translated output from the mount
        """
        status = super().status()
        status.update(self._update_status())

        return status

    def _update_status(self):
        """ """
        self._raw_status = self.serial_query('get_status')

        status = dict()

        status_match = self._status_format.fullmatch(self._raw_status)
        if status_match:
            status = status_match.groupdict()

            # Lookup the text values and replace in status dict
            for k, v in status.items():
                status[k] = self._status_lookup[k][v]

            self._state = status['state']
            self._movement_speed = status['movement_speed']

            self._is_parked = 'Parked' in self._state
            self._is_home = 'Stopped - Zero Position' in self._state
            self._is_tracking = 'Tracking' in self._state
            self._is_slewing = 'Slewing' in self._state

            self.guide_rate = int(self.serial_query('get_guide_rate')) / 1000

        status['timestamp'] = self.serial_query('get_local_time')
        status['tracking_rate_ra'] = self.tracking_rate

        return status

    def set_target_coordinates(self, coords):
        """ Sets the RA and Dec for the mount's current target.

        Args:
            coords (astropy.coordinates.SkyCoord): coordinates specifying target location

        Returns:
            bool:  Boolean indicating success
        """
        target_set = False

        # Save the skycoord coordinates
        self.logger.debug("Setting target coordinates: {}".format(coords))
        self._target_coordinates = coords

        # Get coordinate format from mount specific class
        mount_coords = self._skycoord_to_mount_coord(self._target_coordinates)

        # Send coordinates to mount
        try:
            self.serial_query('set_ra', mount_coords[0])
            self.serial_query('set_dec', mount_coords[1])
            target_set = True
        except:
            self.logger.warning("Problem setting mount coordinates")

        return target_set

    def get_current_coordinates(self):
        """ Reads out the current coordinates from the mount.

        Note:
            See `_mount_coord_to_skycoord` and `_skycoord_to_mount_coord` for translation of
            mount specific coordinates to astropy.coordinates.SkyCoord

        Returns:
            astropy.coordinates.SkyCoord
        """
        # self.logger.debug('Getting current mount coordinates')

        mount_coords = self.serial_query('get_coordinates')

        # Turn the mount coordinates into a SkyCoord
        self._current_coordinates = self._mount_coord_to_skycoord(mount_coords)

        return self._current_coordinates


##################################################################################################
# Movement methods
##################################################################################################

    def slew_to_target(self):
        """ Slews to the current _target_coordinates

        Args:
            on_finish(method):  A callback method to be executed when mount has
            arrived at destination

        Returns:
            bool: indicating success
        """
        response = 0

        if not self.is_parked:
            assert self._target_coordinates is not None, self.logger.warning(
                "Target Coordinates not set")

            response = self.serial_query('slew_to_target')

            self.logger.debug("Mount response: {}".format(response))
            if response:
                self.logger.debug('Slewing to target')

            else:
                self.logger.warning('Problem with slew_to_target')
        else:
            self.logger.info('Mount is parked')

        return response

    def slew_to_home(self):
        """ Slews the mount to the home position.

        Note:
            Home position and Park position are not the same thing

        Returns:
            bool: indicating success
        """
        response = 0

        if not self.is_parked:
            self._target_coordinates = None
            response = self.serial_query('goto_home')
        else:
            self.logger.info('Mount is parked')

        return response

    def park(self):
        """ Slews to the park position and parks the mount.

        Note:
            When mount is parked no movement commands will be accepted.

        Returns:
            bool: indicating success
        """

        self.set_park_coordinates()
        self.set_target_coordinates(self._park_coordinates)

        response = self.serial_query('park')

        if response:
            self.logger.debug('Slewing to park')
        else:
            self.logger.warning('Problem with slew_to_park')

        while not self.is_parked:
            time.sleep(2)

        # The mount is currently not parking in correct position so we manually move it there.
        self.unpark()
        self.move_direction(direction='south', seconds=11.0)

        self._is_parked = True

        return response

    def home_and_park(self):

        if not self.is_parked:
            self.slew_to_home()
            while self.is_slewing:
                time.sleep(5)
                self.logger.debug("Slewing to home, sleeping for 5 seconds")

            # Reinitialize from home seems to always do the trick of getting us to
            # correct side of pier for parking
            self._is_initialized = False
            self.initialize()
            self.park()

            while self.is_slewing:
                time.sleep(5)
                self.logger.debug("Slewing to park, sleeping for 5 seconds")

        self.logger.debug("Mount parked")

    def slew_to_zero(self):
        """ Calls `slew_to_home` in base class. Can be overridden.  """
        self.slew_to_home()

    def unpark(self):
        """ Unparks the mount. Does not do any movement commands but makes them available again.

        Returns:
            bool: indicating success
        """

        response = self.serial_query('unpark')

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

        move_command = 'move_{}'.format(direction)
        self.logger.debug("Move command: {}".format(move_command))

        try:
            now = current_time()
            self.logger.debug("Moving {} for {} seconds. ".format(direction, seconds))
            self.serial_query(move_command)

            time.sleep(seconds)

            self.logger.debug("{} seconds passed before stop".format((current_time() - now).sec))
            self.serial_query('stop_moving')
            self.logger.debug("{} seconds passed total".format((current_time() - now).sec))
        except KeyboardInterrupt:
            self.logger.warning("Keyboard interrupt, stopping movement.")
        except Exception as e:
            self.logger.warning("Problem moving command!! Make sure mount has stopped moving: {}".format(e))
        finally:
            # Note: We do this twice. That's fine.
            self.logger.debug("Stopping movement")
            self.serial_query('stop_moving')

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
        delta_str_f, delta_str_b = '{:+0.04f}'.format(delta).split('.')
        delta_str_f += '0'  # Add extra zero
        delta_str = '{}.{}'.format(delta_str_f, delta_str_b)

        self.logger.debug("Setting tracking rate to sidereal {}".format(delta_str))
        if self.serial_query('set_custom_tracking'):
            self.logger.debug("Custom tracking rate set")
            response = self.serial_query('set_custom_{}_tracking_rate'.format(direction), "{}".format(delta_str))
            self.logger.debug("Tracking response: {}".format(response))
            if response:
                self.tracking = 'Custom'
                self.tracking_rate = 1.0 + delta
                self.logger.debug("Custom tracking rate sent")


##################################################################################################
# Serial Methods
##################################################################################################

    def serial_query(self, cmd, *args):
        """ Sends a serial query and returns response.

        Performs a send and then returns response. Will do a translate on cmd first. This should
        be the major serial utility for commands. Accepts an additional args that is passed
        along with the command. Checks for and only accepts one args param.

        Args:
            cmd (str): A command to send to the mount. This should be one of the commands listed in the mount
                commands yaml file.
            *args: Parameters to be sent with command if required.

        Examples:
            >>> mount.serial_query('set_local_time', '101503')  #doctest: +SKIP
            '1'
            >>> mount.serial_query('get_local_time')            #doctest: +SKIP
            '101503'

        Returns:
            bool: indicating success
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')
        assert len(args) <= 1, self.logger.warning(
            'Ignoring additional arguments for {}'.format(cmd))

        params = args[0] if args else None

        # self.logger.debug('Mount Query & Params: {} {}'.format(cmd, params))

        self.serial.clear_buffer()

        full_command = self._get_command(cmd, params=params)

        self.serial_write(full_command)

        response = self.serial_read()

        return response

    def serial_write(self, cmd):
        """ Sends a string command to the mount via the serial port.

        First 'translates' the message into the form specific mount can understand using the mount configuration yaml
        file. This method is most often used from within `serial_query` and may become a private method in the future.

        Note:
            This command currently does not support the passing of parameters. See `serial_query` instead.

        Args:
            cmd (str): A command to send to the mount. This should be one of the commands listed in the mount
                commands yaml file.
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        # self.logger.debug("Mount Query: {}".format(cmd))
        self.serial.write(cmd)

    def serial_read(self):
        """ Reads from the serial connection

        Returns:
            str: Response from mount
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        response = ''

        response = self.serial.read()

        # self.logger.debug("Mount Read: {}".format(response))

        # Strip the line ending (#) and return
        response = response.rstrip('#')

        # If it is an integer, turn it into one
        if response == '0' or response == '1':
            try:
                response = int(response)
            except ValueError:
                pass

        return response


##################################################################################################
# Private Methods
##################################################################################################

    def _setup_commands(self, commands):
        """
        Does any setup for the commands needed for this mount. Mostly responsible for
        setting the pre- and post-commands. We could also do some basic checking here
        to make sure required commands are in fact available.
        """
        self.logger.debug('Setting up commands for mount')

        if len(commands) == 0:
            model = self.config['mount'].get('brand')
            if model is not None:
                mount_dir = self.config['directories']['mounts']
                conf_file = "{}/{}.yaml".format(mount_dir, model)

                if os.path.isfile(conf_file):
                    self.logger.info(
                        "Loading mount commands file: {}".format(conf_file))
                    try:
                        with open(conf_file, 'r') as f:
                            commands.update(yaml.load(f.read()))
                            self.logger.debug(
                                "Mount commands updated from {}".format(conf_file))
                    except OSError as err:
                        self.logger.warning(
                            'Cannot load commands config file: {} \n {}'.format(conf_file, err))
                    except:
                        self.logger.warning(
                            "Problem loading mount command file")
                else:
                    self.logger.warning(
                        "No such config file for mount commands: {}".format(conf_file))

        # Get the pre- and post- commands
        self._pre_cmd = commands.setdefault('cmd_pre', ':')
        self._post_cmd = commands.setdefault('cmd_post', '#')

        self.logger.debug('Mount commands set up')
        return commands

    def _connect_serial(self):
        """ Sets up serial connection """
        self.logger.debug('Making serial connection for mount at {}'.format(self._port))

        try:
            self.serial.connect()
        except:
            raise error.BadSerialConnection(
                'Cannot create serial connect for mount at port {}'.format(self._port))

        self.logger.debug('Mount connected via serial')

    def _get_command(self, cmd, params=''):
        """ Looks up appropriate command for telescope """

        # self.logger.debug('Mount Command Lookup: {}'.format(cmd))

        full_command = ''

        # Get the actual command
        cmd_info = self.commands.get(cmd)

        if cmd_info is not None:

            # Check if this command needs params
            if 'params' in cmd_info:
                if params is '':
                    raise error.InvalidMountCommand(
                        '{} expects params: {}'.format(cmd, cmd_info.get('params')))

                full_command = "{}{}{}{}".format(
                    self._pre_cmd, cmd_info.get('cmd'), params, self._post_cmd)
            else:
                full_command = "{}{}{}".format(
                    self._pre_cmd, cmd_info.get('cmd'), self._post_cmd)

            # self.logger.debug('Mount Full Command: {}'.format(full_command))
        else:
            self.logger.warning('No command for {}'.format(cmd))
            # raise error.InvalidMountCommand('No command for {}'.format(cmd))

        return full_command

    def _get_expected_response(self, cmd):
        """ Looks up appropriate response for command for telescope """
        # self.logger.debug('Mount Response Lookup: {}'.format(cmd))

        response = ''

        # Get the actual command
        cmd_info = self.commands.get(cmd)

        if cmd_info is not None:
            response = cmd_info.get('response')
            # self.logger.debug('Mount Command Response: {}'.format(response))
        else:
            raise error.InvalidMountCommand(
                'No result for command {}'.format(cmd))

        return response
