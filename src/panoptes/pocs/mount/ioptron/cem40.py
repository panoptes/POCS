import re
import time
from contextlib import suppress
from enum import IntEnum

from astropy import units as u
from astropy.coordinates import SkyCoord
from panoptes.utils.time import current_time
from panoptes.utils import error as error
from panoptes.pocs.mount.serial import AbstractSerialMount


class MountGPS(IntEnum):
    OFF = 0
    ON = 1
    EXTRACTED = 2


class MountState(IntEnum):
    STOPPED = 0
    TRACKING = 1
    SLEWING = 2
    GUIDING = 3
    MERIDIAN_FLIPPING = 4
    TRACKING_PEC = 5
    PARKED = 6
    AT_HOME = 7
    UNKNOWN = 8


class MountTrackingState(IntEnum):
    SIDEREAL = 0
    LUNAR = 1
    SOLAR = 2
    KING = 3
    CUSTOM = 4


class MountMovementSpeed(IntEnum):
    SIDEREAL_1 = 1
    SIDEREAL_2 = 2
    SIDEREAL_8 = 3
    SIDEREAL_16 = 4
    SIDEREAL_64 = 5
    SIDEREAL_128 = 6
    SIDEREAL_256 = 7
    SIDEREAL_512 = 8
    SIDEREAL_MAX = 9


class MountTimeSource(IntEnum):
    RS232 = 1
    HAND_CONTROLLER = 2
    GPS = 3


class MountHemisphere(IntEnum):
    SOUTHERN = 0
    NORTHERN = 1


class Mount(AbstractSerialMount):
    """
        Mount class for iOptron mounts. Overrides the base `initialize` method
        and providers some helper methods to convert coordinates.
    """

    def __init__(self, location, mount_version='0040', *args, **kwargs):
        self._mount_version = mount_version
        super(Mount, self).__init__(location, *args, **kwargs)
        self.logger.info('Creating iOptron CEM40 mount')

        # Regexp to match the iOptron RA/Dec format
        self._ra_format = r'(?P<ra_millisecond>\d{8})'
        self._dec_format = r'(?P<dec_sign>[\+\-])(?P<dec_arcsec>\d{8})'
        self._coords_format = re.compile(self._dec_format + self._ra_format)

        self._state = MountState.UNKNOWN

        self._raw_status = None
        self._status_format = re.compile(
            r'(?P<longitude>[+\-]\d{6})' +
            r'(?P<latitude>\d{6})' +
            r'(?P<gps>[0-2])' +
            r'(?P<state>[0-7])' +
            r'(?P<tracking>[0-4])' +
            r'(?P<movement_speed>[1-9])' +
            r'(?P<time_source>[1-3])' +
            r'(?P<hemisphere>[01])'
        )

        self.logger.success('iOptron CEM40 mount created')

    def initialize(self, set_rates=True, unpark=False, *arg, **kwargs):
        """ Initialize the connection with the mount and setup for location.

        iOptron mounts are initialized by sending the following two commands
        to the mount:

        * MountInfo

        If the mount is successfully initialized, the `_setup_location_for_mount` method
        is also called.

        Returns:
            bool:   Returns the value from `self.is_initialized`.
        """
        if not self.is_connected:
            self.logger.info(f'Connecting to mount {__name__}')
            self.connect()

        if self.is_connected and not self.is_initialized:
            self.logger.info(f'Initializing {__name__} mount')

            # We trick the mount into thinking it's initialized while we
            # initialize otherwise the `query` method will test
            # to see if initialized and be put into loop.
            self._is_initialized = True

            actual_mount_info = self.query('mount_info')

            expected_mount_info = self.commands.get('mount_info').get('response')
            self._is_initialized = False

            # Test our init procedure for iOptron
            if actual_mount_info != expected_mount_info:
                self.logger.debug(f'{actual_mount_info} != {expected_mount_info}')
                raise error.MountNotFound('Problem initializing mount')
            else:
                self._is_initialized = True
                self._setup_location_for_mount()
                if set_rates:
                    self._set_initial_rates()

        self.logger.info(f'Mount initialized: {self.is_initialized}')

        return self.is_initialized

    def park(self, park_direction=None, park_seconds=None, *args, **kwargs):
        """Slews to the park position and parks the mount.

        This still uses a custom park command because the mount will not allow
        the Declination axis to move below 0 degrees.

        Note:
            When mount is parked no movement commands will be accepted.

        Args:
            park_direction (str or None): The direction to move the Declination axis. If
                not provided (the default), then look at config setting, otherwise 'north'.
            park_seconds (str or None): The number of seconds to move the Declination axis at
                maximum move speed. If not provided (the default), then look at config setting,
                otherwise 11 seconds.

        Returns:
            bool: indicating success
        """
        if self.at_mount_park:
            self.logger.success("Mount is already parked")
            return self.at_mount_park

        # Get the direction and timing
        park_direction = park_direction or self.get_config('mount.settings.park_direction', 'north')
        park_seconds = park_seconds or self.get_config('mount.settings.park_seconds', 11)

        self.logger.debug(f'Parking mount: {park_direction=} {park_seconds=}')

        self.unpark()
        self.query('park')
        while self.status.get('state') != MountState.PARKED:
            self.logger.trace(f'Moving to park')
            time.sleep(1)
        self.unpark()
        self.query('set_button_moving_rate', 9)
        self.move_direction(direction=park_direction, seconds=park_seconds)

        self._at_mount_park = True
        self.logger.success('Mount successfully parked.')
        return self.at_mount_park

    def search_for_home(self):
        """Search for the home position.

        This method uses the internal homing pin on the CEM40 mount to return the
        mount to the home (or zero) position.
        """
        self.logger.info('Searching for the home position.')
        self.query('search_for_home')

    def _set_initial_rates(self, alt_limit='+00', meridian_treatment='100'):
        # Make sure we start at sidereal
        self.set_tracking_rate()

        self.logger.debug(f'Setting altitude limit to {alt_limit}')
        self.query('set_altitude_limit', alt_limit)

        self.logger.debug(f'Setting {meridian_treatment=}')
        self.query('set_meridian_treatment', meridian_treatment)

        self.logger.debug('Setting manual moving rate to max')
        self.query('set_button_moving_rate', 9)

        self.logger.debug(f"Mount guide rate: {self.query('get_guide_rate')}")

    def _setup_location_for_mount(self):
        """
        Sets the mount up to the current location. Mount must be initialized first.

        This uses mount.location (an astropy.coords.EarthLocation) to set
        most of the params and the rest is read from a config file.  Users
        should not call this directly.

        Includes:
        * Latitude set_long
        * Longitude set_lat
        * Daylight Savings disable_daylight_savings
        * Universal Time Offset set_gmt_offset
        * Current Date set_local_date
        * Current Time set_local_time

        """
        if not self.location:
            self.logger.warning('Please set a location before attempting setup')

        if not self.is_initialized:
            self.logger.warning('Mount has not been initialized')
            return

        self.logger.debug('Setting up CEM40 for location')

        # Location
        # Adjust the lat/long for format expected by iOptron
        lat = '{:+07.0f}'.format(self.location.lat.to(u.arcsecond).value)
        lon = '{:+07.0f}'.format(self.location.lon.to(u.arcsecond).value)

        self.query('set_long', lon)
        self.query('set_lat', lat)

        # Set time.
        self.query('disable_daylight_savings')  # TODO param?
        gmt_offset = self.get_config('location.gmt_offset', default=0)
        self.query('set_gmt_offset', gmt_offset)

        now = current_time() + gmt_offset * u.minute

        self.query('set_local_time', now.datetime.strftime("%H%M%S"))
        self.query('set_local_date', now.datetime.strftime("%y%m%d"))

    def _mount_coord_to_skycoord(self, mount_coords):
        """
        Converts between iOptron RA/Dec format and a SkyCoord

        Args:
            mount_coords (str): Coordinates as returned by mount

        Returns:
            astropy.SkyCoord:   Mount coordinates as astropy SkyCoord with
                EarthLocation included.
        """
        coords_match = self._coords_format.fullmatch(mount_coords)

        coords = None

        self.logger.trace(f'Mount coordinates: {coords_match}')

        if coords_match is not None:
            ra = (coords_match.group('ra_millisecond') * u.millisecond).to(u.hour)
            dec = (coords_match.group('dec_arcsec') * u.centiarcsecond).to(u.arcsec)

            dec_sign = coords_match.group('dec_sign')
            if dec_sign == '-':
                dec = dec * -1

            coords = SkyCoord(ra=ra, dec=dec, frame='icrs', unit=(u.hour, u.arcsecond))
        else:
            self.logger.warning('Cannot create SkyCoord from mount coordinates')

        return coords

    def _skycoord_to_mount_coord(self, coords):
        """
        Converts between SkyCoord and a iOptron RA/Dec format.

            `
            TTTTTTTT(T) 0.01 arc-seconds
            XXXXX(XXX) milliseconds

            Command: “:SrXXXXXXXX#”
            Defines the commanded right ascension, RA. Slew, calibrate and
            park commands operate on the most recently defined right ascension.

            Command: “:SdsTTTTTTTT#”
            Defines the commanded declination, Dec. Slew, calibrate and
            park commands operate on the most recently defined declination.
            `

        @param  coords  astropy.coordinates.SkyCoord

        @retval         A tuple of RA/Dec coordinates
        """

        # RA in milliseconds
        ra_ms = (coords.ra.hour * u.hour).to(u.millisecond)
        mount_ra = f'{ra_ms.value:08.0f}'
        self.logger.debug(f'RA (ms): {ra_ms}')

        dec_dms = (coords.dec.degree * u.degree).to(u.centiarcsecond)
        self.logger.debug(f'Dec (centiarcsec): {dec_dms}')
        mount_dec = f'{dec_dms.value:=+08.0f}'

        mount_coords = (mount_ra, mount_dec)

        return mount_coords

    def _set_zero_position(self):
        """ Sets the current position as the zero position.

        The iOptron allows you to set the current position directly, so
        we simply call the iOptron command.
        """
        self.logger.info("Setting zero position")
        return self.query('set_zero_position')

    def _update_status(self):
        self._raw_status = self.query('get_status')

        status = dict()

        status_match = self._status_format.fullmatch(self._raw_status)
        if status_match:
            status_dict = status_match.groupdict()

            self._state = MountState(int(status_dict['state']))
            status['state'] = self.state
            status['parked_software'] = self.is_parked

            status['longitude'] = float(status_dict['longitude']) * u.arcsec
            # Longitude has +90° so no negatives. Subtract for original.
            status['latitude'] = (float(status_dict['latitude']) - 90) * u.arcsec

            status['gps'] = MountGPS(int(status_dict['gps']))
            status['tracking'] = MountTrackingState(int(status_dict['tracking']))

            self._movement_speed = MountMovementSpeed(int(status_dict['movement_speed']))
            status['movement_speed'] = self._movement_speed

            status['time_source'] = MountTimeSource(int(status_dict['time_source']))
            status['hemisphere'] = MountHemisphere(int(status_dict['hemisphere']))

            self._at_mount_park = self.state == MountState.PARKED
            self._is_home = self.state == MountState.AT_HOME
            self._is_tracking = self.state == MountState.TRACKING or \
                                self.state == MountState.TRACKING_PEC
            self._is_slewing = self.state == MountState.SLEWING

        status['timestamp'] = self.query('get_local_time')
        status['tracking_rate_ra'] = self.tracking_rate

        return status

    def _setup_commands(self, commands):
        super()._setup_commands(commands)

        # Update the `MountInfo` response if one has been set on the class.
        with suppress(AttributeError, KeyError):
            self.commands['mount_info']['response'] = self._mount_version
