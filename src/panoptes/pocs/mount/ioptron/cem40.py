import re
import time
from typing import Tuple, Optional, Dict, Union

from astropy import units as u
from astropy.coordinates import SkyCoord
from panoptes.pocs.images import OffsetError
from panoptes.utils.time import current_time
from panoptes.pocs.mount.serial import AbstractSerialMount
from panoptes.pocs.mount import constants


class Mount(AbstractSerialMount):
    """Mount class for the iOptron CEM40."""

    def __init__(self, *args, **kwargs):
        super(Mount, self).__init__(*args, **kwargs)
        self.logger.info('Creating iOptron mount')

        # Regexp to match the iOptron RA/Dec format.
        self._coords_format = re.compile(
            constants.SerialParams.RA_ARCSEC + constants.SerialParams.DEC_ARCSEC)

        self.logger.success('CEM40 created')

    def initialize(self, *arg, **kwargs):
        """ Initialize the connection with the mount and setup for location.

        Returns:
            bool:   Returns the value from `self.is_initialized`.
        """
        super(Mount, self).initialize(init_commands=['mount_info'])
        return self.is_initialized

    def park(self,
             ra_direction='west',
             ra_seconds=11.,
             dec_direction='south',
             dec_seconds=15.,
             *args, **kwargs):
        """Slews to the park position and parks the mount.

        Returns:
            bool: indicating success
        """
        raise NotImplementedError

    def get_tracking_correction(self,
                                offset_info: Union[Tuple[float, float], OffsetError],
                                pointing_ha: float,
                                thresholds: Optional[Tuple[int, int]] = None
                                ) -> Dict[str, Tuple[float, float, str]]:
        raise NotImplementedError

    def _set_initial_rates(self):
        # Make sure we start at sidereal.
        self.set_tracking_rate()

        self.logger.debug('Setting manual moving rate to max')
        self.query('set_button_moving_rate', 9)
        self.logger.debug(f"Mount guide rate: {self.query('get_guide_rate')}")
        self.query('set_guide_rate', '9090')
        guide_rate = self.query('get_guide_rate')
        self.ra_guide_rate = int(guide_rate[0:2]) / 100
        self.dec_guide_rate = int(guide_rate[2:]) / 100
        self.logger.debug(f"Mount guide rate: {self.ra_guide_rate} {self.dec_guide_rate}")

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
            raise AssertionError('Please set a location before attempting setup')

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
        """

        # RA in milliseconds
        ra_ms = (coords.ra.hour * u.hour).to(u.millisecond)
        dec_dms = (coords.dec.degree * u.degree).to(u.centiarcsecond)

        mount_ra = f"{ra_ms.value:08.0f}"
        mount_dec = f"{dec_dms.value:=+08.0f}"

        self.logger.debug(f"RA (ms): {ra_ms}")
        self.logger.debug(f"Dec (centiarcsec): {dec_dms}")

        mount_coords = (mount_ra, mount_dec)

        return mount_coords
