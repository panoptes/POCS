#!/usr/bin/env python
from astropy.coordinates import SkyCoord, AltAz
from pocs.utils import current_time
from astropy import units as u
from warnings import warn

from astropy.coordinates import FK5
import numpy as np
from astroplan import Observer
from astropy.coordinates import EarthLocation


class Horizon():

    def __init__(self, observer, altitude, time=current_time(), *args, **kwargs):

        self.observer = observer
        self.altitude = altitude

        self.time = time


################################
# Working Methods #
################################

    def location(self):
        return self.observer.location

    def modulus(self, value, min_val, max_val):
        '''takes a vale, and the min and max values and returns the value within the min and max range'''
        val = value

        if value < min_val:
            val = max_val - abs(value - min_val)
        elif value > max_val:
            val = min_val + abs(value - max_val)

        return val

    def horizon_range(self, zenith=[], altitude=40 * u.deg):
        '''Returns the range of RA and DEC in degrees for which the sky is observable, given the altitude.'''

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
            warn('Could not parse input(s). Error: ', e)
            return

        horizon_range['max_ra'] = self.modulus(max_ra, 0.0 * u.deg, 360.0 * u.deg)
        horizon_range['min_ra'] = self.modulus(min_ra, 0.0 * u.deg, 360.0 * u.deg)
        horizon_range['max_dec'] = self.modulus(max_dec, -90.0 * u.deg, 90.0 * u.deg)
        horizon_range['min_dec'] = self.modulus(min_dec, -90.0 * u.deg, 90.0 * u.deg)

        return horizon_range

    def zenith_ra_dec(self, time=current_time(), location=''):

        zen_ra_dec = {}

        ra_zen = np.nan
        dec_zen = np.nan

        if location == '':
            location = self.observer.location

        try:
            alt_az = AltAz(0 * u.deg, alt=90 * u.deg, obstime=time, location=location)

            ra_zen = alt_az.transform_to(FK5).ra
            dec_zen = alt_az.transform_to(FK5).dec

        except Exception as e:
            warn('Incorrent time/location input! Error: ', e)
            raise e

        zen_ra_dec['ra'] = ra_zen
        zen_ra_dec['dec'] = dec_zen

        return zen_ra_dec

    def nesw_ra_dec(self, time=current_time(), location='', alt=''):

        nesw = {'north:': 0 * u.deg, 'east': 90 * u.deg, 'south': 180 * u.deg, 'west': 270 * u.deg}

        if alt == '':
            alt = self.altitude
        if location == '':
            location = self.observer.location

        nesw_ra_dec = {}

        for az in nesw:
            try:
                alt_az = AltAz(nesw[az], alt=alt, obstime=time, location=location)

                nesw_ra_dec[az] = alt_az.transform_to(FK5)

            except Exception as e:
                warn('Incorrent time/location input! Error: ', e)
                raise e

        return nesw_ra_dec

    def start_time(self, time=current_time()):
        '''Used to find the start time of the VO evnt from the observatory's perspective.

         Params: time - in astropy.Time format, the given start of a VO event. Default: current time at location


        This method will be used to determine when the observatory can start observing a VO event. If the
        supplied time of the event is before sunset, for example, it will set the start_time to whichever
        is the greatest: sunset time or current time.'''

        night_start = self.observer.tonight()[0]

        start_time = max([time, night_start])

        return start_time
