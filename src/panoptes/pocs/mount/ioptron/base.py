import re
from contextlib import suppress

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.coordinates.earth import EarthLocation
from astropy.time import Time
from panoptes.utils.time import current_time

from panoptes.pocs.mount.ioptron import MountGPS, MountState, MountTrackingState, MountMovementSpeed, MountTimeSource, \
    MountHemisphere
from panoptes.pocs.mount.serial import AbstractSerialMount
from panoptes.utils import error as error


class Mount(AbstractSerialMount):
    """Mount class for iOptron mounts."""

    def __init__(self, location, mount_version=None, *args, **kwargs):
        self._mount_version = mount_version or self._mount_version
        super(Mount, self).__init__(location, *args, **kwargs)

        self._raw_status = None

        self._latitude_format = self.commands.get('latitude_format', '{:.0f}')
        self._longitude_format = self.commands.get('longitude_format', '{:.0f}')
        self._status_format = re.compile(self.commands.get('status_format', ''), flags=re.VERBOSE)
        self._coords_format = re.compile(self.commands.get('coords_format', ''), flags=re.VERBOSE)

        self._state = MountState.UNKNOWN

    @property
    def is_home(self):
        """ bool: Mount home status. """
        self._is_home = self.status.get('state') == MountState.AT_HOME
        return self._is_home

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

            # See if we are using old command set.
            command_set = self.get_config('commands_file')
            if command_set == 'ioptron/v140':
                actual_version_info = self.query('version')
                expected_version_info = self.commands.get('version').get('response')
                if actual_version_info != expected_version_info:
                    raise error.MountNotFound('Problem initializing mount - version numbers do not match')

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

    def park(self,
             ra_direction=None, ra_seconds=None,
             dec_direction=None, dec_seconds=None,
             *args, **kwargs):
        """Slews to the park position and parks the mount.

        This still uses a custom park command because the mount will not allow
        the Declination axis to move below 0 degrees.

        Note:
            When mount is parked no movement commands will be accepted.

        Args:
            ra_direction (str or None): The direction to move the RA axis. If
                not provided (the default), then look at config setting, otherwise 'west'.
            ra_seconds (str or None): The number of seconds to move the RA axis at
                maximum move speed. If not provided (the default), then look at config setting,
                otherwise 15 seconds.
            dec_direction (str or None): The direction to move the Declination axis. If
                not provided (the default), then look at config setting, otherwise 'north'.
            dec_seconds (str or None): The number of seconds to move the Declination axis at
                maximum move speed. If not provided (the default), then look at config setting,
                otherwise 15 seconds.

        Returns:
            bool: indicating success
        """
        if self.at_mount_park or self.is_parked:
            self.logger.success("Mount is already parked")
            return self.at_mount_park

        # Get the direction and timing
        ra_direction = ra_direction or self.get_config('mount.settings.park.ra_direction', 'west')
        ra_seconds = ra_seconds or self.get_config('mount.settings.park.ra_seconds', 15)
        dec_direction = dec_direction or self.get_config('mount.settings.park.dec_direction', 'north')
        dec_seconds = dec_seconds or self.get_config('mount.settings.park.dec_seconds', 15)

        self.unpark()
        self.query('set_button_moving_rate', 9)

        self.logger.debug(f'Moving mount to home before parking.')
        if self.slew_to_home(blocking=True):
            self.logger.debug(f'Parking mount: RA: {ra_direction} {ra_seconds} seconds, '
                              f'Dec: {dec_direction} {dec_seconds} seconds')
            self.move_direction(direction=dec_direction, seconds=dec_seconds)
            self.move_direction(direction=ra_direction, seconds=ra_seconds)

            self._at_mount_park = True
            self._is_parked = True
            self.logger.success('Mount successfully parked.')

        return self.at_mount_park

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
        if not isinstance(self.location, EarthLocation):
            self.logger.warning('Please set a location before attempting setup')

        if not self.is_initialized:
            self.logger.warning('Mount has not been initialized')
            return

        self.logger.info('Setting up mount for location')

        # Location
        # Adjust the lat/long for format expected by iOptron.
        lat = self._latitude_format.format(self.location.lat.to(u.arcsecond).value)
        lon = self._longitude_format.format(self.location.lon.to(u.arcsecond).value)

        self.query('set_long', lon)
        self.query('set_lat', lat)

        # Daylight savings and GMT offset.
        self.query('disable_daylight_savings')
        gmt_offset = self.get_config('location.gmt_offset', default=0)
        self.query('set_gmt_offset', gmt_offset)

        # Set the date and time.
        # Newer firmware has the `set_utc_time` method which sets both the date and time.
        # Older firmware has `set_local_date` and `set_local_time` which must be called separately.
        now = current_time() + gmt_offset * u.minute
        if 'set_utc_time' in self.commands:
            j2000 = Time(2000, format='jyear')
            offset_time = (now - j2000).to(u.ms)
            self.query('set_utc_time', f'{offset_time:0>13.0f}')
        else:
            self.query('set_local_time', now.datetime.strftime("%H%M%S"))
            self.query('set_local_date', now.datetime.strftime("%y%m%d"))

    def _set_initial_rates(self, alt_limit='+30', meridian_treatment='015'):
        # Make sure we start at sidereal.
        self.query('set_sidereal_tracking')

        self.logger.debug(f'Setting altitude limit to {alt_limit}')
        self.query('set_altitude_limit', alt_limit)

        self.logger.debug(f'Setting {meridian_treatment=}')
        self.query('set_meridian_treatment', meridian_treatment)

        self.logger.debug('Setting manual moving rate to max')
        self.query('set_button_moving_rate', 9)

        self.logger.debug(f"Mount guide rate: {self.query('get_guide_rate')}")

    def _set_zero_position(self):
        """ Sets the current position as the zero position.

        The iOptron allows you to set the current position directly, so
        we simply call the iOptron command.
        """
        self.logger.info("Setting zero position")
        return self.query('set_zero_position')

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

    def _update_status(self):
        self._raw_status = self.query('get_status')

        status = dict()

        status_match = self._status_format.fullmatch(self._raw_status)
        if status_match:
            status_dict = status_match.groupdict()

            self._state = MountState(int(status_dict['state']))
            status['state'] = self.state
            status['parked_software'] = self.is_parked

            status['longitude'] = float(status_dict['longitude']) * u.milliarcsecond
            # Longitude has +90° so no negatives. Subtract for original.
            status['latitude'] = (float(status_dict['latitude']) - 90) * u.milliarcsecond

            status['gps'] = MountGPS(int(status_dict['gps']))
            status['tracking'] = MountTrackingState(int(status_dict['tracking']))

            self._movement_speed = MountMovementSpeed(int(status_dict['movement_speed']))
            status['movement_speed'] = self._movement_speed

            status['time_source'] = MountTimeSource(int(status_dict['time_source']))
            status['hemisphere'] = MountHemisphere(int(status_dict['hemisphere']))

            self._at_mount_park = self.state == MountState.PARKED
            self._is_home = self.state == MountState.AT_HOME
            self._is_tracking = self.state == MountState.TRACKING or self.state == MountState.TRACKING_PEC
            self._is_slewing = self.state == MountState.SLEWING

        status['tracking_rate_ra'] = self.tracking_rate

        ts = self.query('get_timestamp')
        offset = int(ts[:4]) * u.minute
        daylight_savings = bool(int(ts[4]))
        status['timestamp'] = ts
        status['time_offset'] = offset
        status['time_daylight_savings'] = daylight_savings

        if self.commands.get('command_version', 0) == 2.5:
            year = int(ts[5:7])
            month = int(ts[7:9])
            day = int(ts[9:11])
            hour = int(ts[11:13])
            minute = int(ts[13:15])
            second = int(ts[15:17])
            status['time_local'] = Time(f'20{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}').iso
        elif self.commands.get('command_version', 0) >= 3.10:
            with suppress(Exception):
                now = int(ts[5:]) * u.ms
                j2000 = Time(2000, format='jyear')
                t0 = j2000 + now + offset

                status['time_local'] = t0.iso

        return status

    def _setup_commands(self, commands):
        super()._setup_commands(commands)

        # Update the `MountInfo` response if one has been set on the class.
        with suppress(AttributeError, KeyError):
            self.commands['mount_info']['response'] = self._mount_version
