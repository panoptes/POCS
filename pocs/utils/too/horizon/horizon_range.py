#!/usr/bin/env python
from astropy.coordinates import SkyCoord, AltAz
from ....utils import current_time
from astropy import units as u
from warnings import warn

from astropy.coordinates import FK5
import numpy as np
from astroplan import Observer
from astropy.coordinates import EarthLocation


class Horizon(object):

    def __init__(self, observer, altitude, time=current_time(), *args, **kwargs):
        '''Contains methods to work out the RA and DEC coordinates for the observable range from the set observer.

        Attribs:
            - observer (astroplan Observer Object): Required in the init.
            - altitude (float): the altitude (in degrees) below which we do not want to observe.
            - time (astropy.time.Time Object): time at which we want to observe.'''

        self.observer = observer
        self.altitude = altitude

        self.time = time


################################
# Working Methods #
################################

    def modulus(self, value, min_val, max_val):
        '''Ensures a value is between the maximum and minimum value.

        Used to ensure coordinates wrap-around.

        Args:
            - value (float): value we want to check/ modify.
            - min_val (float): minimum value.
            - max_val (float): maximum value.
        Returns:
            - val (float): value if value is between the minimum and
            maximum. Modified so that this is the case, if at first it isn't.'''

        val = value

        if value < min_val:
            val = max_val - abs(value - min_val)
        elif value > max_val:
            val = min_val + abs(value - max_val)

        return val

    def horizon_range(self, zenith={}, altitude=40 * u.deg):
        '''Finds the observable range from an Observer and within an altitude in RA and DEC.

        Args:
            - zenith (python dict): dict returned by zenith_ra_dec method.
            - altitude (float in astropy.units.deg): the altitude below which we don't want to observe.
        Returns:
            - horizon_range (python dict): Example: {'min_ra': (float), 'min_dec': (float), 'max_ra': (float),
                                                     'max_dec': (float)}
                The range on the sky which we can see at time given to zenith_ra_dec.'''

        horizon_range = {'max_ra': np.nan, 'min_ra': np.nan,
                         'max_dec': np.nan, 'min_dec': np.nan}

        range_ra_dec = 90 * u.deg - altitude

        max_ra = 0
        min_ra = 0
        max_dec = 0
        min_dec = 0

        try:
            max_ra = zenith['ra'] + range_ra_dec
            min_ra = zenith['ra'] - range_ra_dec
            max_dec = zenith['dec'] + range_ra_dec
            min_dec = zenith['dec'] - range_ra_dec
        except Exception as e:
            warn('Could not parse input(s).')
            raise e

        horizon_range['max_ra'] = self.modulus(max_ra, 0.0 * u.deg, 360.0 * u.deg)
        horizon_range['min_ra'] = self.modulus(min_ra, 0.0 * u.deg, 360.0 * u.deg)
        horizon_range['max_dec'] = self.modulus(max_dec, -90.0 * u.deg, 90.0 * u.deg)
        horizon_range['min_dec'] = self.modulus(min_dec, -90.0 * u.deg, 90.0 * u.deg)

        return horizon_range

    def zenith_ra_dec(self, time=current_time(), location=None):
        '''Gets the coordinates in RA and DEC of the zenith above ovserver at given time.

        Args:
            - time (astropy.time.Time Object): Default is current time. The time at which we want to observe.
            - loaction (astropy.coordinates.EarthLocation Object): Default is location of initalized observer.

        Returns:
            zenith_ra_dec (python dict): Example: {'ra': (float), 'dec': (float)}. Both values are nan if
                they cannot be determined.'''

        zen_ra_dec = {}

        ra_zen = np.nan
        dec_zen = np.nan

        if location is None:
            location = self.observer.location

        try:
            alt_az = AltAz(0 * u.deg, alt=90 * u.deg, obstime=time, location=location)

            ra_zen = alt_az.transform_to(FK5).ra
            dec_zen = alt_az.transform_to(FK5).dec

        except Exception as e:
            warn('Incorrent time/location input!')
            raise e

        zen_ra_dec['ra'] = ra_zen
        zen_ra_dec['dec'] = dec_zen

        return zen_ra_dec

    def nesw_ra_dec(self, time=current_time(), location=None, alt=None):
        '''Returns NSEW coordinates in RA and DEC for given location and time.

        Args:
            - time (astropy.time.Time Object): time at which we're observing.
            - location (astropy.coordinates.EarthLocation Object): current loaction by default, but can be set.
            - alt (float in astropy.units.deg): altitude below which we don't want to observe.
                Set to 0.0 for true horizon.

        Returns:
            - nesw_ra_dec (python dict): key-value pairs, where keys are lower-case 'north', 'east', 'south',
                'west' and values are objects containing both ra and dec. To access the particular value, do:
                        value.ra or value.dec.'''

        nesw = {'north:': 0 * u.deg, 'east': 90 * u.deg, 'south': 180 * u.deg, 'west': 270 * u.deg}

        if alt is None:
            alt = self.altitude
        if location is None:
            location = self.observer.location

        nesw_ra_dec = {}

        for az in nesw:
            try:
                alt_az = AltAz(nesw[az], alt=alt, obstime=time, location=location)

                nesw_ra_dec[az] = alt_az.transform_to(FK5)

            except Exception as e:
                warn('Incorrent time/location input!')
                raise e

        return nesw_ra_dec

    def start_time(self, time=current_time()):
        '''Used to find the start time of the VO evnt from the observatory's perspective.

        Args:
            - time (astropy.time.Time Object): the given start of a VO event. Default: current time.
        Returns:
            - start_time (astropy.time.Time Object): either the time of sunset if given time is less than
            sunset time or given time if it is greater than sunset time.'''

        night_start = self.observer.tonight()[0]

        start_time = max([time, night_start])

        return start_time
