import os
import yaml

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

from ..utils import *


@has_logger
class AbstractMount(object):

    def __init__(self,
                 config=dict(),
                 commands=dict(),
                 location=None,
                 ):
        """
        Abstract Base class for controlling a mount. This provides the basic functionality
        for the mounts. Sub-classes should override the `initialize` method for mount-specific
        issues as well as any helper methods specific mounts might need. See "NotImplemented Methods"
        section of this module.

        Sets the following properies:

            - self.non_sidereal_available = False
            - self.PEC_available = False
            - self.is_initialized = False

        Args:
            config (dict):              Custom configuration passed to base mount. This is usually
                                        read from the main system config.

            commands (dict):            Commands for the telescope. These are read from a yaml file
                                        that maps the mount-specific commands to common commands.

            location (EarthLocation):   An astropy.coordinates.EarthLocation that contains location information.
        """

        # Create an object for just the mount config items
        self.mount_config = config.get('mount', {})

        # Check the config for required items
        assert self.mount_config.get('port') is not None, self.logger.error(
            'No mount port specified, cannot create mount\n {}'.format(self.mount_config))

        self.config = config

        # setup commands for mount
        self.commands = self._setup_commands(commands)

        # We set some initial mount properties. May come from config
        self.non_sidereal_available = self.mount_config.setdefault('non_sidereal_available', False)
        self.PEC_available = self.mount_config.setdefault('PEC_available', False)

        # Initial states
        self.is_initialized = False
        self._is_slewing = False
        self._is_parked = False
        self._is_tracking = False

        # Set the initial location
        self._location = location

        # Setup our serial connection at the given port
        self._port = self.mount_config.get('port')
        try:
            self.serial = SerialData(port=self._port)
        except err:
            self.serial = None
            self.logger.warning(err)

        # Set initial coordinates
        self._target_coordinates = None
        self._current_coordinates = None
        self._park_coordinates = None

##################################################################################################
# Properties
##################################################################################################

    @property
    def location(self):
        """ astropy.coordinates.SkyCoord: The location details for the mount.

        When a new location is set,`_setup_location_for_mount` is called, which will update the mount
        with the current location. It is anticipated the mount won't change locations while observing
        so this should only be done upon mount initialization.

        """
        return self._location

    @location.setter
    def location(self, location):
        self._location = location
        # If the location changes we need to update the mount
        self._setup_location_for_mount()

    @property
    def is_connected(self):
        """ bool: Checks the serial connection on the mount to determine if connection is open """
        return self.serial.is_connected

    @property
    def is_parked(self):
        """ bool: Mount park status. Set each time the `status` method is called """
        return self._is_parked

    @is_parked.setter
    def is_parked(self, parked):
        self._is_parked = parked

    @property
    def is_tracking(self):
        """ bool: Mount tracking status. Set each time the `status` method is called """
        return self._is_tracking

    @is_tracking.setter
    def is_tracking(self, tracking):
        self._is_tracking = tracking

    @property
    def is_slewing(self):
        """ bool: Mount slewing status. Set each time the `status` method is called """
        raise NotImplementedError

##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """ Connects to the mount via the serial port (`self._port`)

        Returns:
            bool:   Returns the self.is_connected property which checks the actual serial connection.
        """
        self.logger.info('Connecting to mount')

        if self.serial.ser and self.serial.ser.isOpen() is False:
            try:
                self._connect_serial()
            except OSError as err:
                self.logger.error("OS error: {0}".format(err))
            except:
                self.logger.warning('Could not create serial connection to mount.')
                self.logger.warning('NO MOUNT CONTROL AVAILABLE')
                raise error.BadSerialConnection(
                    'Cannot create serial connect for mount at port {}'.format(self._port))

        self.logger.info('Mount connected: {}'.format(self.is_connected))

        return self.is_connected


    def initialize(self):
        raise NotImplementedError

    def status(self):
        """ Gets the mount statys in various ways """
        raise NotImplementedError

    def get_target_coordinates(self):
        """ Gets the RA and Dec for the mount's current target. This does NOT necessarily
        reflect the current position of the mount, see `get_current_coordinates`.

        Returns:
            astropy.coordinates.SkyCoord:
        """

        if self._target_coordinates is None:
            self.logger.info("Target coordinates not set")
        else:
            self.logger.info('Mount target_coordinates: {}'.format(self._target_coordinates))

        return self._target_coordinates

    def set_target_coordinates(self, coords):
        """ Sets the RA and Dec for the mount's current target.

        Args:
            coords (astropy.coordinates.SkyCoord): coordinates specifying target location

        Returns:
            bool:  Boolean indicating success
        """
        target_set = False

        # Save the skycoord coordinates
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
        self.logger.debug('Getting current mount coordinates')

        mount_coords = self.serial_query('get_coordinates')

        # Turn the mount coordinates into a SkyCoord
        self._current_coordinates = self._mount_coord_to_skycoord(mount_coords)

        return self._current_coordinates

    def set_park_coordinates(self, ha=-170 * u.degree, dec=-10 * u.degree):
        """ Calculates the RA-Dec for the the park position.

        This method returns a location that points the optics of the unit down toward the ground.

        The RA is calculated from subtracting the desired hourangle from the local sidereal time. This requires
        a proper location be set.

        Note:
            Mounts usually don't like to track or slew below the horizon so this will most likely require a
            configuration item be set on the mount itself.

        Args:
            ha (Optional[astropy.units.degree]): Hourangle of desired parking position. Defaults to -165 degrees
            dec (Optional[astropy.units.degree]): Declination of desired parking position. Defaults to -165 degrees

        Returns:
            park_skycoord (astropy.coordinates.SkyCoord): A SkyCoord object representing current parking position.
        """
        self.logger.debug('Setting park position')

        park_time = Time.now()
        park_time.location = self.location

        lst = park_time.sidereal_time('apparent')
        self.logger.debug("LST: {}".format(lst))
        self.logger.debug("HA: {}".format(ha))

        ra = lst - ha
        self.logger.debug("RA: {}".format(ra))
        self.logger.debug("Dec: {}".format(dec))

        self._park_coordinates = SkyCoord(ra, dec)

        self.logger.info("Park Coordinates RA-Dec: {}".format(self._park_coordinates))

##################################################################################################
# Movement methods
##################################################################################################

    def slew_to_coordinates(self, coords, ra_rate=15.0, dec_rate=0.0):
        """ Slews to given coordinates.

        Note:
            Slew rates are not implemented yet.

        Args:
            coords (astropy.SkyCoord): Coordinates to slew to
            ra_rate (Optional[float]): Slew speed - RA tracking rate in arcsecond per second. Defaults to 15.0
            dec_rate (Optional[float]): Slew speed - Dec tracking rate in arcsec per second. Defaults to 0.0

        Returns:
            bool: indicating success
        """
        assert isinstance(coords, tuple), self.logger.warning(
            'slew_to_coordinates expects RA-Dec coords')

        response = 0

        if not self.is_parked:
            # Set the coordinates
            if self.set_target_coordinates(coords):
                response = self.slew_to_target()
            else:
                self.logger.warning("Could not set target_coordinates")

        return response

    def slew_to_target(self):
        """ Slews to the current _target_coordinates

        Returns:
            bool: indicating success
        """
        response = 0

        if not self.is_parked:
            assert self._target_coordinates is not None, self.logger.warning( "Target Coordinates not set")

            response = self.serial_query('slew_to_target')
            self.logger.info("Mount response: {}".format(response))
            if response:
                self.logger.info('Slewing to target')
            else:
                self.logger.info('Problem with slew_to_target')
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
            response = self.serial_query('goto_home')

        return response

    def slew_to_zero(self):
        """ Calls `slew_to_home` in base class. Can be overridden.  """
        self.slew_to_home()

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
            self.is_parked = True
            self.logger.debug('Slewing to park')
        else:
            self.logger.warning('Problem with slew_to_park')

        return response

    def unpark(self):
        """ Unparks the mount. Does not do any movement commands but makes them available again.

        Returns:
            bool: indicating success
        """

        self.is_parked = False
        response = self.serial_query('unpark')

        if response:
            self.logger.info('Mount unparked')
        else:
            self.logger.warning('Problem with unpark')

        return response

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
        assert self.is_initialized, self.logger.warning( 'Mount has not been initialized')
        assert len(args) <= 1, self.logger.warning( 'Ignoring additional arguments for {}'.format(cmd))

        params = args[0] if args else None

        self.logger.debug('Mount Query & Params: {} {}'.format(cmd, params))

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
        assert self.is_initialized, self.logger.warning( 'Mount has not been initialized')

        self.logger.debug("Mount Query: {}".format(cmd))
        self.serial.write(cmd)

    def serial_read(self):
        """ Reads from the serial connection

        Returns:
            str: Response from mount
        """
        assert self.is_initialized, self.logger.warning( 'Mount has not been initialized')

        response = ''

        response = self.serial.read()

        self.logger.debug("Mount Read: {}".format(response))

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
# Utility Methods
##################################################################################################

    def get_coords_for_ha_dec(self, ha=None, dec=None):
        """ Get RA/Dec coordinates for given HA/Dec

        Args:
            ha (Optional[astropy.units.degree]): Hourangle of desired position. Defaults to None
            dec (Optional[astropy.units.degree]): Declination of desired position. Defaults to None

        Returns:
            park_skycoord (astropy.coordinates.SkyCoord): A SkyCoord object representing HA/Dec position.
        """
        assert ha is not None, self.logger.warning("Must specify ha")
        assert dec is not None, self.logger.warning("Must specify dec")

        assert ha is u.degree, self.logger.warning("HA must be in degree units")
        assert dec is u.degree, self.logger.warning("Dec must be in degree units")


##################################################################################################
# Private Methods
##################################################################################################

    def _setup_commands(self, commands):
        """
        Does any setup for the commands needed for this mount. Mostly responsible for
        setting the pre- and post-commands. We could also do some basic checking here
        to make sure required commands are in fact available.
        """
        self.logger.info('Setting up commands for mount')

        if len(commands) == 0:
            model = self.mount_config.get('model')
            if model is not None:
                conf_file = "{}/conf_files/{}/{}.yaml".format(
                    self.config.get('resources_dir'),
                    'mounts',
                    model
                )

                if os.path.isfile(conf_file):
                    self.logger.info(
                        "Loading mount commands file: {}".format(conf_file))
                    try:
                        with open(conf_file, 'r') as f:
                            commands.update(yaml.load(f.read()))
                            self.logger.info(
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

        self.logger.info('Mount commands set up')
        return commands

    def _connect_serial(self):
        """ Sets up serial connection """
        self.logger.info( 'Making serial connection for mount at {}'.format(self._port))

        self.serial.connect()

        self.logger.info('Mount connected via serial')

    def _get_command(self, cmd, params=''):
        """ Looks up appropriate command for telescope """

        self.logger.debug('Mount Command Lookup: {}'.format(cmd))

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

            self.logger.debug('Mount Full Command: {}'.format(full_command))
        else:
            self.logger.warning('No command for {}'.format(cmd))
            # raise error.InvalidMountCommand('No command for {}'.format(cmd))

        return full_command

    def _get_expected_response(self, cmd):
        """ Looks up appropriate response for command for telescope """
        self.logger.debug('Mount Response Lookup: {}'.format(cmd))

        response = ''

        # Get the actual command
        cmd_info = self.commands.get(cmd)

        if cmd_info is not None:
            response = cmd_info.get('response')
            self.logger.debug('Mount Command Response: {}'.format(response))
        else:
            raise error.InvalidMountCommand(
                'No result for command {}'.format(cmd))

        return response

##################################################################################################
# NotImplemented Methods - child class
##################################################################################################

    def _setup_location_for_mount(self):
        """ Sets the current location details for the mount. """
        raise NotImplementedError

    def _set_zero_position(self):
        """ Sets the current position as the zero (home) position. """
        raise NotImplementedError

    def _mount_coord_to_skycoord(self):
        raise NotImplementedError

    def _skycoord_to_mount_coord(self):
        raise NotImplementedError
