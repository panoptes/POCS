import json
import os
import time
import yaml

from astropy import units as u
from astropy.coordinates import SkyCoord
from string import Template

from ..utils import error
from ..utils import theskyx

from .mount import AbstractMount


class Mount(AbstractMount):

    def __init__(self, *args, **kwargs):
        """"""
        super(Mount, self).__init__(*args, **kwargs)
        self.theskyx = theskyx.TheSkyX()

        template_dir = self.config['mount']['template_dir']
        if template_dir.startswith('/') is False:
            template_dir = os.path.join(os.environ['POCS'], template_dir)

        assert os.path.exists(template_dir), self.logger.warning("Bisque Mounts required a template directory")

        self.template_dir = template_dir


##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """ Connects to the mount via the serial port (`self._port`)

        Returns:
            bool:   Returns the self.is_connected property which checks the actual serial connection.
        """
        self.logger.info('Connecting to mount')

        self.write(self._get_command('connect'))
        response = self.read()

        self._is_connected = response["success"]
        self.logger.info(response["msg"])

        return self.is_connected

    def disconnect(self):
        self.logger.debug("Disconnecting mount from TheSkyX")
        self.query('disconnect')
        self._is_connected = False
        return not self.is_connected

    def initialize(self, unpark=False, *args, **kwargs):
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

            if unpark:
                self.unpark()

        self.logger.info('Mount initialized: {}'.format(self.is_initialized))

        return self.is_initialized

    def _update_status(self):
        """ """
        status = self.query('get_status')

        try:
            self._at_mount_park = status['parked']
            self._is_parked = status['parked']
            self._is_tracking = status['tracking']
            self._is_slewing = status['slewing']
        except KeyError:
            self.logger.warning("Problem with status, key not found")

        if not self.is_parked:
            status.update(self.query('get_coordinates'))

        return status

    def set_target_coordinates(self, coords):
        """ Sets the RA and Dec for the mount's current target.

        Args:
            coords (astropy.coordinates.SkyCoord): coordinates specifying target location

        Returns:
            bool:  Boolean indicating success
        """
        # Reset current target
        self._target_coordinates = None

        target_set = False

        if self.is_parked:
            self.logger.warning("Mount is parked")
        else:
            # Save the skycoord coordinates
            self.logger.debug("Setting target coordinates: {}".format(coords))

            # Get coordinate format from mount specific class
            mount_coords = self._skycoord_to_mount_coord(coords)

            # Send coordinates to mount
            try:
                response = self.query('set_target_coordinates', {
                    'ra': mount_coords[0],
                    'dec': mount_coords[1],
                })
                target_set = response['success']

                if target_set:
                    self._target_coordinates = coords
                    self.logger.debug(response['msg'])
                else:
                    self.logger.warning(response['msg'])
            except Exception as e:
                self.logger.warning("Problem setting mount coordinates: {}".format(mount_coords))
                self.logger.warning(e)

        return target_set

    def set_park_position(self):
        self.query('set_park_position')
        self.logger.info("Mount park position set: {}".format(self._park_coordinates))


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
        success = False

        if self.is_parked:
            self.logger.warning("Mount is parked")
        elif self._target_coordinates is None:
            self.logger.warning("Target Coordinates not set")
        else:
            # Get coordinate format from mount specific class
            mount_coords = self._skycoord_to_mount_coord(self._target_coordinates)

            # Send coordinates to mount
            try:
                response = self.query('slew_to_coordinates', {
                    'ra': mount_coords[0],
                    'dec': mount_coords[1],
                })
                success = response['success']

            except Exception as e:
                self.logger.warning("Problem slewing to mount coordinates: {} {}".format(mount_coords, e))

            if success:
                if not self.query('start_tracking')['success']:
                    self.logger.warning("Tracking not turned on for target")
                    self._is_tracking = True

        return success

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
            response = self.query('goto_home')
        else:
            self.logger.info('Mount is parked')

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
        self.logger.debug('Parking mount')
        response = self.query('park')

        if response['success']:
            while not self.is_parked:
                self.status()
                time.sleep(2)

        return self.is_parked

    def unpark(self):
        """ Unparks the mount. Does not do any movement commands but makes them available again.

        Returns:
            bool: indicating success
        """

        response = self.query('unpark')

        if response['success']:
            self._is_parked = False
            self.logger.debug('Mount unparked')
        else:
            self.logger.warning('Problem with unpark of mount')

        return response['success']

    def move_direction(self, direction='north', seconds=1.0, arcmin=None, rate=None):
        """ Move mount in specified `direction` for given amount of `seconds`

        """
        seconds = float(seconds)
        assert direction in ['north', 'south', 'east', 'west', 'left', 'right', 'up', 'down']

        move_command = 'move_{}'.format(direction)
        self.logger.debug("Move command: {}".format(move_command))

        if rate is None:
            rate = 15.04  # (u.arcsec / u.second)

        if arcmin is None:
            arcmin = (rate * seconds) / 60.

        try:
            self.logger.debug("Moving {} for {} arcmins. ".format(direction, arcmin))
            self.query(move_command, params={'direction': direction.upper()[0], 'arcmin': arcmin})
        except KeyboardInterrupt:
            self.logger.warning("Keyboard interrupt, stopping movement.")
        except Exception as e:
            self.logger.warning("Problem moving command!! Make sure mount has stopped moving: {}".format(e))
        finally:
            # Note: We do this twice. That's fine.
            self.logger.debug("Stopping movement")
            self.query('stop_moving')


##################################################################################################
# Communication Methods
##################################################################################################

    def write(self, value):
        return self.theskyx.write(value)

    def read(self, timeout=5):
        while True:
            response = self.theskyx.read()
            if response is not None or timeout == 0:
                break
            else:
                time.sleep(1)
                timeout -= 1

        try:
            response_obj = json.loads(response)
        except TypeError as e:
            self.logger.warning("Error: {}".format(e, response))
        except json.JSONDecodeError as e:
            # self.logger.warning("Can't decode JSON response from mount")
            # self.logger.warning(e)
            # self.logger.warning(response)
            response_obj = {
                "response": response,
                "success": False,
            }

        return response_obj


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
                    self.logger.debug(
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

        try:
            filename = cmd_info['file']
        except KeyError:
            raise error.InvalidMountCommand("Command not found")

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
        self.logger.warning("TheSkyX requires location to be set in the application")

    def _mount_coord_to_skycoord(self, mount_coords):
        """
        Converts between iOptron RA/Dec format and a SkyCoord

        Args:
            mount_coords (str): Coordinates as returned by mount

        Returns:
            astropy.SkyCoord:   Mount coordinates as astropy SkyCoord with
                EarthLocation included.
        """
        if isinstance(mount_coords, dict):
            ra = mount_coords['ra']
            dec = mount_coords['dec']
        else:
            ra, dec = mount_coords.split(' ')

        ra = (float(ra) * u.hourangle).to(u.degree)
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

        ra = coords.ra.to(u.hourangle).to_string()
        dec = coords.dec.to_string()

        self.logger.debug("RA: {} \t Dec: {}".format(ra, dec))

        mount_coords = (ra, dec)

        return mount_coords
