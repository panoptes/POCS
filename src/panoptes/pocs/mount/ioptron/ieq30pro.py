import re
import time

from astropy.coordinates import SkyCoord
from astropy import units as u

from panoptes.pocs.mount.serial import AbstractSerialMount
from panoptes.utils.time import current_time


class Mount(AbstractSerialMount):
    """
        Mount class for iOptron mounts. Overrides the base `initialize` method
        and providers some helper methods to convert coordinates.
    """

    def __init__(self, *args, **kwargs):
        super(Mount, self).__init__(*args, **kwargs)
        self.logger.info('Creating iOptron mount')

        # Regexp to match the iOptron RA/Dec format
        self._ra_format = r'(?P<ra_millisecond>\d{8})'
        self._dec_format = r'(?P<dec_sign>[\+\-])(?P<dec_arcsec>\d{8})'
        self._coords_format = re.compile(self._dec_format + self._ra_format)

        self.logger.success('iEQ30Pro created')

    def park(self, ra_direction='west', ra_seconds=11., dec_direction='south', dec_seconds=15.,
             *args, **kwargs):
        """Slews to the park position and parks the mount.

        Args:
            ra_direction (str, optional): The direction to move the RA axis from
                the home position. Defaults to 'west' for northern hemisphere.
            ra_seconds (float, optional): The number of seconds at fastest move
                speed to move the RA axis from the home position.
            dec_direction (str, optional): The direction to move the Dec axis
                from the home position. Defaults to 'south' for northern hemisphere.
            dec_seconds (float, optional): The number of seconds at the fastest
                move speed to move the Dec axis from the home position.

        Returns:
            bool: indicating success
        """

        if self.is_parked:
            self.logger.info("Mount is parked")
            return self._is_parked

        if self.slew_to_home(blocking=True):
            # The mount is currently not parking in correct position so we manually move it there.
            self.query('set_button_moving_rate', 9)
            self.move_direction(direction=ra_direction, seconds=ra_seconds)
            while self.is_slewing:
                self.logger.debug("Slewing RA axis to park position...")
                time.sleep(3)
            self.move_direction(direction=dec_direction, seconds=dec_seconds)
            while self.is_slewing:
                self.logger.debug("Slewing Dec axis to park position...")
                time.sleep(3)

            self._is_parked = True
            self.logger.debug(f'Mount parked: {self.is_parked}')

        return self._is_parked

    def get_tracking_correction(self, offset_info, pointing_ha, thresholds=None):
        """Determine the needed tracking corrections from current position.

        This method will determine the direction and number of milliseconds to
        correct the mount for each axis in order to correct for any tracking
        drift. The Declination axis correction ('north' or 'south') depends on
        the movement of the camera box with respect to the pier, which can be
        determined from the Hour Angle (HA) of the pointing image in the sequence.

        Note:
            Correction values below 50ms will be skipped and values above 99999ms
            will be clipped.

        Args:
            offset_info (`OffsetError`): A named tuple describing the offset
                error. See `pocs.images.OffsetError`.
            pointing_ha (float): The Hour Angle (HA) of the mount at the
                beginning of the observation sequence in degrees. This affects
                the direction of the Dec adjustment.
            thresholds (Tuple[int, int], optional): Tracking correction min and
                max thresholds. If not provided, `min_tracking_threshold` and
                `max_tracking_threshold` are used.
        Returns:
            dict: Offset corrections for each axis as needed ::

                dict: {
                    # axis: (arcsec, millisecond, direction)
                    'ra': (float, float, str),
                    'dec': (float, float, str),
                }
        """
        pier_side = 'east'
        if 0 <= pointing_ha <= 12:
            pier_side = 'west'

        self.logger.debug(f'Mount pier side: {pier_side} {pointing_ha:.02f}')

        if thresholds is None:
            min_tracking_threshold = self.min_tracking_threshold
            max_tracking_threshold = self.max_tracking_threshold
        else:
            min_tracking_threshold = thresholds[0]
            max_tracking_threshold = thresholds[1]

        axis_corrections = {
            'dec': None,
            'ra': None,
        }

        for axis in axis_corrections.keys():
            # find the number of ms and direction for Dec axis
            offset = getattr(offset_info, f'delta_{axis}')
            offset_ms = self.get_ms_offset(offset, axis=axis)

            if axis == 'dec':
                # Determine which direction to move based on direction mount
                # is moving (i.e. what side it started on).
                if pier_side == 'east':
                    if offset_ms >= 0:
                        delta_direction = 'north'
                    else:
                        delta_direction = 'south'
                else:
                    if offset_ms >= 0:
                        delta_direction = 'south'
                    else:
                        delta_direction = 'north'
            else:
                if offset_ms >= 0:
                    delta_direction = 'west'
                else:
                    delta_direction = 'east'

            offset_ms = abs(offset_ms.value)
            self.logger.debug(f'Tracking offset: {offset_ms} ms')

            # Skip short corrections
            if offset_ms <= min_tracking_threshold:
                self.logger.debug(f'Min tracking threshold: {min_tracking_threshold} ms')
                self.logger.debug(f'Requested tracking lower than threshold, skipping correction')
                continue

            # Correct long offset
            if offset_ms > max_tracking_threshold:
                self.logger.debug(f'Max tracking threshold: {max_tracking_threshold} ms')
                self.logger.debug(f'Requested tracking higher than threshold, setting to threshold')
                offset_ms = max_tracking_threshold

            self.logger.debug(f'{axis}: {delta_direction} {offset_ms:.02f} ms')
            axis_corrections[axis] = (offset, offset_ms, delta_direction)

        return axis_corrections

    def _set_initial_rates(self):
        # Make sure we start at sidereal
        self.set_tracking_rate()

        self.logger.debug('Setting manual moving rate to max')
        self.query('set_button_moving_rate', 9)
        self.logger.debug(f"Mount guide rate: {self.query('get_guide_rate')}")
        self.query('set_guide_rate', '9090')
        guide_rate = self.query('get_guide_rate')
        self.ra_guide_rate = int(guide_rate[0:2]) / 100
        self.dec_guide_rate = int(guide_rate[2:]) / 100
        self.logger.debug(f'Mount guide rate: {self.ra_guide_rate} {self.dec_guide_rate}')

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
        """ Converts between SkyCoord and a iOptron RA/Dec format.

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
        """
        ra_ms = (coords.ra.hour * u.hour).to(u.millisecond)
        dec_dms = (coords.dec.degree * u.degree).to(u.centiarcsecond)

        mount_ra = f"{ra_ms.value:08.0f}"
        mount_dec = f"{dec_dms.value:=+08.0f}"

        self.logger.debug(f"RA (ms): {ra_ms}")
        self.logger.debug(f'Dec (centiarcsec): {dec_dms}')

        mount_coords = (mount_ra, mount_dec)

        return mount_coords

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
        if self.is_initialized is False:
            raise AssertionError('Mount has not been initialized')
        if self.location is None:
            raise ValueError('Please set a location before attempting setup')

        self.logger.info('Setting up mount for location')

        # Location
        # Adjust the lat/long for format expected by iOptron
        self.query('set_long', f'{self.location.lon.to(u.arcsecond).value:+07.0f}')
        self.query('set_lat', f'{self.location.lat.to(u.arcsecond).value:+07.0f}')

        # Time
        self.query('disable_daylight_savings')

        gmt_offset = self.get_config('location.gmt_offset', default=0)
        self.query('set_gmt_offset', gmt_offset)

        now = current_time() + gmt_offset * u.minute

        self.query('set_local_time', now.datetime.strftime("%H%M%S"))
        self.query('set_local_date', now.datetime.strftime("%y%m%d"))
