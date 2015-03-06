import os
import yaml
import ephem

from astropy import units as u
from astropy.coordinates import SkyCoord

import panoptes.utils.config as config
import panoptes.utils.logger as logger
import panoptes.utils.serial as serial
import panoptes.utils.error as error


@logger.has_logger
@config.has_config
class AbstractMount(object):

    def __init__(self,
                 config=dict(),
                 commands=dict(),
                 site=None,
                 ):
        """
        Abstract Base class for controlling a mount. This provides the basic functionality
        for the mounts. Sub-classes should override the `initialize` method for mount-specific
        issues as well as any helper methods specific mounts might need.

        Sets the following properies:

            - self.non_sidereal_available = False
            - self.PEC_available = False
            - self.is_initialized = False

        Args:
            config (dict): Custom configuration passed to base mount. This is usually
                read from the main system config.
            commands (dict): Commands for the telescope. These are read from a yaml file
                that maps the mount-specific commands to common commands.
            site (ephem.Observer): A pyephem Observer that contains site configuration items
                that are usually read from a config file.
        """

        # Create an object for just the mount config items
        self.mount_config = config if len(config) else dict()

        # Check the config for required items
        assert self.mount_config.get('port') is not None, self.logger.error(
            'No mount port specified, cannot create mount\n {}'.format(self.mount_config))

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

        self.site = site

        # Setup our serial connection at the given port
        self.port = self.mount_config.get('port')
        self.serial = serial.SerialData(port=self.port)

        # Set initial coordinates
        self._target_coordinates = None
        self._current_coordinates = None

    def connect(self):
        """
        Connects to the mount via the serial port (self.port).

        Returns:
            bool:   Returns the self.is_connected value which checks the actual
            serial connection.
        """
        self.logger.info('Connecting to mount')

        if self.serial.ser.isOpen() is False:
            try:
                self._connect_serial()
            except OSError as err:
                self.logger.error("OS error: {0}".format(err))
            except:
                self.logger.warning('Could not create serial connection to mount.')
                self.logger.warning('NO MOUNT CONTROL AVAILABLE')
                raise error.BadSerialConnection('Cannot create serial connect for mount at port {}'.format(self.port))

        self.logger.debug('Mount connected: {}'.format(self.is_connected()))

        return self.is_connected()

    @property
    def is_connected(self):
        """
        Checks the serial connection on the mount to determine if connection is open

        Returns:
            bool: True if there is a serial connection to the mount.
        """
        return self.serial.is_connected

    def get_target_coordinates(self):
        """
        Gets the RA and Dec for the mount's current target. This does NOT necessarily
        reflect the current position of the mount.

        @retval         astropy.coordinates.SkyCoord
        """

        if self._target_coordinates is None:
            self.logger.info("Target coordinates not set")
        else:
            self.logger.info('Mount target_coordinates: {}'.format(self._target_coordinates))

        return self._target_coordinates

    def set_target_coordinates(self, coords):
        """
        Sets the RA and Dec for the mount's current target. This does NOT necessarily
        reflect the current position of the mount.

        Args:
            coords (SkyCoord):  astropy SkyCoord coordinates

        Returns:
            target_set (bool):  Boolean indicating success
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
        """
        Reads out the current RA/Dec from the mount.

        @retval         astropy.coordinates.SkyCoord
        """
        self.logger.info('Mount current_coordinates')

        mount_coords = self.serial_query('get_coordinates')

        self._current_coordinates = self._mount_coord_to_skycoord(mount_coords)

        return self._current_coordinates

    def sync_coordinates(self):
        """
        Takes as input, the actual coordinates (J2000) of the mount and syncs the mount on them.
        Used after a plate solve.
        Once we have a mount model, we would use sync only initially,
        then subsequent plate solves would be used as input to the model.
        """
        raise NotImplementedError()

    ### Movement Methods ###

    def slew_to_coordinates(self, coords, ra_rate=None, dec_rate=None):
        """
        Inputs:
            RA and Dec
            RA tracking rate (in arcsec per second, use 15.0 in absence of tracking model).
            Dec tracking rate (in arcsec per second, use 0.0 in absence of tracking model).
        """
        assert isinstance(coords, tuple), self.logger.warning('slew_to_coordinates expects RA-Dec coords')

        # Check the existing guide rate
        # rate = self.serial_query('get_guide_rate')
        # self.logger.debug("slew_to_coordinates: coords: {} \t rate: {} {}".format(coords,ra_rate,dec_rate))

        # Set the coordinates
        if self.set_target_coordinates(coords):
            self.slew_to_target()
        else:
            self.logger.warning("Could not set target_coordinates")

    def slew_to_target(self):
        """
        Slews to the current _target_coordinates
        """
        assert self._target_coordinates is not None, self.logger.warning("_target_coordinates not set")

        if self.serial_query('slew_to_target'):
            self.logger.debug('Slewing to target')
        else:
            self.logger.warning('Problem with slew_to_target')

    def slew_to_park(self):
        """
            Slews to the park position, which is the current RA-Dec of the defined
            Alt-Az coordinates.
        """

        park_skycoord = self.set_target_coordinates(self._park_coordinates())

        response = self.serial_query('park')

        if response:
            self.logger.debug('Slewing to park')
        else:
            self.logger.warning('Problem with slew_to_park')

        return response

    def _park_coordinates(self):
        """
        Calculates the RA-Dec for the the park position, which is always at
        set AltAz. Alt is -70 degrees and Az is +250

        Returns:
            park_skycoord (SkyCoord):  A SkyCoord object representing current parking position
        """
        # Get the set Parking Alt and Az. If none, use defaults
        az = self.config.get('park_az', '250')
        el = self.config.get('park_alt', '-70')

        # Calculate the RA-Dec of given al and az
        ra_dec = self.site.radec_of(az, el)

        park_skycoord = SkyCoord(ra_dec[0] * u.radian, ra_dec[1] * u.radian)

        self.logger.debug("Park Coordinates RA-Dec: {}".format(park_skycoord))

        return park_skycoord

    def slew_to_home(self):
        """
        Slews the mount to the home position. Note that Home position and Park
        position are not the same thing
        """
        return self.serial_query('goto_home')

    ### Utility Methods ###
    def serial_query(self, cmd, *args):
        """
        Performs a send and then returns response. Will do a translate on cmd first. This should
        be the major serial utility for commands. Accepts an additional args that is passed
        along with the command. Checks for and only accepts one args param.
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')
        assert len(args) <= 1, self.logger.warning('Ignoring additional arguments for {}'.format(cmd))

        params = args[0] if args else None

        self.logger.debug('Mount Query & Params: {} {}'.format(cmd, params))

        self.serial.clear_buffer()

        full_command = self._get_command(cmd, params=params)

        self.serial_write(full_command)

        return self.serial_read()

    def serial_write(self, string_command):
        """
            Sends a string command to the mount via the serial port. First 'translates'
            the message into the form specific mount can understand
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        self.logger.debug("Mount Send: {}".format(string_command))
        self.serial.write(string_command)

    def serial_read(self):
        """
        Reads from the serial connection.
        """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')

        response = ''

        # while response == '':
        response = self.serial.read()

        self.logger.debug("Mount Read: {}".format(response))

        # Strip the line ending (#) and return
        return response.rstrip('#')

    def check_coordinates(self):
        """
        Query the mount for the current position of the mount.
        This will be useful in comparing the position of the mount to the orientation
        indicated by the accelerometer or by an astrometric plate solve.
        """
        self.logger.info('Mount check_coordinates')

        coords = self.serial_query('get_coordinates')
        coords_altaz = self.serial_query('get_coordinates_altaz')

        self.logger.debug('Mount check_coordinates: \nRA/Dec: \t {}\nAlt/Az: {}'.format(coords, coords_altaz))

        return (coords)

    def ping(self):
        """ Pings the mount by returning time """
        return self.serial_query('get_local_time')

    def pier_position(self):
        """
        Gets the current pier position as either East or West
        """
        position = ('East', 'West')

        current_position = position[int(self.serial_query('pier_position'))]

        return current_position

    ### Private Methods ###

    def _setup_commands(self, commands):
        """
        Does any setup for the commands needed for this mount. Mostly responsible for
        setting the pre- and post-commands. We could also do some basic checking here
        to make sure required commands are in fact available.
        """
        self.logger.info('Setting up commands for mount')
        # If commands are not passed in, look for configuration file
        # self.logger.debug('commands: {}'.format(commands))

        if len(commands) == 0:
            model = self.mount_config.get('model')
            if model is not None:
                conf_file = "{}/{}/{}.yaml".format(self.config.get('base_dir', os.getcwd()), 'panoptes/mount/', model)

                self.logger.debug("Loading mount commands file: {}".format(conf_file))
                if os.path.isfile(conf_file):
                    try:
                        with open(conf_file, 'r') as f:
                            commands.update(yaml.load(f.read()))
                            self.logger.debug("Mount commands updated from {}".format(conf_file))
                    except OSError as err:
                        self.logger.warning(
                            'Cannot load commands config file: {} \n {}'.format(conf_file, err))
                    except:
                        self.logger.warning("Problem loading mount command file")

        # Get the pre- and post- commands
        self._pre_cmd = commands.setdefault('cmd_pre', ':')
        self._post_cmd = commands.setdefault('cmd_post', '#')

        # Commands to check
        # NOTE: We might want to slim this down and decide which ones fail
        # required_commands = [
        #     'cmd_post', 'cmd_pre', 'get_alt', 'get_az', 'get_dec', 'get_guide_rate', 'get_lat', 'get_local_date',
        #     'get_local_time', 'get_long', 'get_ra', 'goto_home', 'goto_park', 'is_home', 'is_parked', 'is_sidereal',
        #     'is_slewing', 'is_tracking', 'mount_info', 'set_alt', 'set_az', 'set_dec', 'set_guide_rate', 'set_lat',
        #     'set_local_date', 'set_local_time', 'set_long', 'set_ra', 'set_sidereal_rate', 'set_sidereal_tracking',
        #     'slew_to_target', 'start_tracking', 'stop_slewing', 'stop_tracking', 'unpark', 'version',
        # ]

        # Give a warning if command not available
        # for cmd in required_commands:
        #     assert commands.get(cmd) is not None, self.logger.warning(
        #         'No {} command available for mount'.format(cmd))

        self.logger.info('Mount commands set up')
        return commands

    def _connect_serial(self):
        """Gets up serial connection """
        self.logger.info('Making serial connection for mount at {}'.format(self.port))

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
                    raise error.InvalidMountCommand('{} expects params: {}'.format(cmd, cmd_info.get('params')))

                full_command = "{}{}{}{}".format(self._pre_cmd, cmd_info.get('cmd'), params, self._post_cmd)
            else:
                full_command = "{}{}{}".format(self._pre_cmd, cmd_info.get('cmd'), self._post_cmd)

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
            raise error.InvalidMountCommand('No result for command {}'.format(cmd))

        return response

    ### NotImplemented methods - should be implemented in child classes ###
    def setup_site(self, site=None):
        raise NotImplemented()

    def _mount_coord_to_skycoord(self):
        raise NotImplemented()

    def _skycoord_to_mount_coord(self):
        raise NotImplemented()

    def initialize(self):
        raise NotImplemented()

    def status(self):
        """ Gets the mount statys in various ways """
        raise NotImplemented()
