import os
import socket
import time
import yaml

from astropy import units as u
from astropy.coordinates import SkyCoord
from string import Template

from ..utils import current_time
from ..utils import error

from .mount import AbstractMount


class BisqueMount(AbstractMount):

    def __init__(self, host='localhost', has_dome=True, port=3040, *args, **kwargs):
        """"""
        super(BisqueMount, self).__init__(*args, **kwargs)

        self._host = host
        self._port = port

        self.has_dome = has_dome

        self._template_dir = kwargs.get('template_dir', None)

        self._socket = None

    @property
    def template_dir(self):
        if self._template_dir is None:
            self._template_dir = '{}/bisque_software'.format(self.config['directories']['resources'])

        return self._template_dir

##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """ Connects to the mount via the serial port (`self._port`)

        Returns:
            bool:   Returns the self.is_connected property which checks the actual serial connection.
        """
        self.logger.debug('Connecting to mount')

        self._connect()

        self._is_initialized = True
        if self.query('connect_mount'):
            self._is_connected = True
            self.logger.info('Mount connected: {}'.format(self.is_connected))
        else:
            self._is_initialized = False

        return self.is_connected

    def initialize(self, *args, **kwargs):
        """ Initialize the connection with the mount and setup for location.

        If the mount is successfully initialized, the `_setup_location_for_mount` method
        is also called.

        Returns:
            bool:   Returns the value from `self.is_initialized`.
        """
        if not self.is_connected:
            self.connect()

        if self.is_connected and not self.is_initialized:
            self.logger.info('Initializing {} mount'.format(__name__))

            # We trick the mount into thinking it's initialized while we
            # initialize otherwise the `serial_query` method will test
            # to see if initialized and be put into loop.
            self._is_initialized = True

            self._setup_location_for_mount()

            # Connect and couple dome
            if self.has_dome:
                self.query('connect_dome')

        self.logger.info('Mount initialized: {}'.format(self.is_initialized))

        return self.is_initialized

    def _update_status(self):
        """ """
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

            self._at_mount_park = 'Park' in self._state
            self._is_home = 'Stopped - Zero Position' in self._state
            self._is_tracking = 'Tracking' in self._state
            self._is_slewing = 'Slewing' in self._state

            self.guide_rate = int(self.serial_query('get_guide_rate'))

        status['timestamp'] = self.serial_query('get_local_time')
        status['tracking_rate_ra'] = self.tracking_rate

        return status


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

            params = {}
            response = self.query('slew_to_target', params)

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

        while not self._at_mount_park:
            self.status()
            time.sleep(2)

        # The mount is currently not parking in correct position so we manually move it there.
        self.unpark()
        self.move_direction(direction='south', seconds=11.0)

        self._is_parked = True

        return response

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
# Communication Methods
##################################################################################################

    def write(self, value):
        assert type(value) is str
        self.socket.sendall(value.encode())

    def read(self, timeout=5):
        self.socket.settimeout(timeout)
        response = None
        try:
            response, err = self.socket.recv(4096).decode().split('|')
        except socket.timeout:
            pass

        return response


##################################################################################################
# Private Methods
##################################################################################################

    def _connect(self):
        """ Sets up serial connection """
        self.logger.debug('Making TheSkyX connection for mount at {}:{}'.format(self._host, self._port))

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self._host, self._port))
        except ConnectionRefusedError:
            raise error.PanError('Cannot create connection to TheSkyX')

        self.logger.debug('Mount connected via TheSkyX')

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
                    except Exception:
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

    def _get_command(self, cmd, params=None):
        """ Looks up appropriate command for telescope """

        cmd_info = self.commands.get(cmd)

        filename = cmd_info['file']

        if filename.startswith('/') is False:
            filename = os.path.join(self.template_dir, filename)

        template = ''
        try:
            with open(filename, 'r') as f:
                template = Template(f.read())
        except Exception as e:
            self.logger.warning("Problem reading TheSkyX template {}: {}".format(filename, e))

        if params is None:
            params = {}

        params.setdefault('async', 'false')

        return template.safe_substitute(params)

    def _setup_location_for_mount(self):
        pass

    def _mount_coord_to_skycoord(self, mount_coords):
        """
        Converts between iOptron RA/Dec format and a SkyCoord

        Args:
            mount_coords (str): Coordinates as returned by mount

        Returns:
            astropy.SkyCoord:   Mount coordinates as astropy SkyCoord with
                EarthLocation included.
        """
        ra, dec = mount_coords.split(' ')
        ra = float(ra) * u.deg
        dec = float(dec) * u.deg

        coords = SkyCoord(ra, dec)

        return coords

    def _skycoord_to_mount_coord(self, coords):
        """
        Converts between SkyCoord and a iOptron RA/Dec format.

            `
            TTTTTTTT(T) 0.01 arc-seconds
            XXXXX(XXX) milliseconds

            Command: “:SrXXXXXXXX#”
            Defines the commanded right ascension, RA. Slew, calibrate and park commands operate on the
            most recently defined right ascension.

            Command: “:SdsTTTTTTTT#”
            Defines the commanded declination, Dec. Slew, calibrate and park commands operate on the most
            recently defined declination.
            `

        @param  coords  astropy.coordinates.SkyCoord

        @retval         A tuple of RA/Dec coordinates
        """

        # RA in milliseconds
        mount_ra = "{}".format(coords.ra.value)
        self.logger.debug("RA: {}".format(mount_ra))

        mount_dec = "{}".format(coords.dec.value)
        self.logger.debug("Dec: {}".format(mount_dec))

        mount_coords = (mount_ra, mount_dec)

        return mount_coords
