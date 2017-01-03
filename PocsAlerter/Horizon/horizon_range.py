#!/usr/bin/env python
import sys
from pocs import POCS
from astropy.coordinates import SkyCoord, AltAz
from pocs.utils import current_time
from astropy import units as u
from astropy.coordinates import FK5
import numpy as np
from astroplan import Observer

pocs = POCS(simulator=['all'])

class Horizon():

    def __init__(self, location=pocs.observatory.observer.location,
                 az=[0, 90, 180, 270], time = current_time(),
                 altitude = pocs.observatory.location['horizon']):

        self.location = location
        self.azimuthal = az
        self.altitude = altitude
        self.time = time

################################
# Working Methods #
################################

    def horizon_range(self, zenith=[], altitude=40 * u.deg):

        '''Returns the range of RA and DEC in degrees for which the sky is observable, given the altitude.'''

        horizon_range={'max_ra': np.nan, 'min_ra': np.nan,
                          'max_dec': np.nan, 'min_dec': np.nan}

        range_ra_dec = 90 * u.deg - altitude

        try:
            horizon_range['max_ra'] = np.mod(zenith['ra'] + range_ra_dec, 360 * u.deg)
            horizon_range['min_ra'] = np.mod(zenith['ra'] - range_ra_dec, 360 * u.deg)
            horizon_range['max_dec'] = np.mod(zenith['dec'] + range_ra_dec, 90 * u.deg)
            horizon_range['min_dec'] = np.mod(zenith['dec'] - range_ra_dec, 90 * u.deg)
        except Exception as e:
            print('Could not parse input(s). Error: ', e)

        return horizon_range


    def zenith_ra_dec(self, time=current_time(), location=pocs.observatory.observer.location,
                       alt=pocs.observatory.location['horizon']):

        zen_ra_dec = {'max_ra': np.nan, 'min_ra': np.nan,
                          'max_dec': np.nan, 'min_dec': np.nan}

        ra_zen = np.nan
        dec_zen = np.nan

        try:
            alt_az = AltAz(0 * u.deg, alt=90 * u.deg, obstime=time, location=location)

            ra_zen = alt_az.transform_to(FK5).ra
            dec_zen = alt_az.transform_to(FK5).dec

        except Exception as e:
            print('Incorrent time/location input! Error: ', e)

        zen_ra_dec['ra'] = ra_zen
        zen_ra_dec['dec'] = dec_zen

        return zen_ra_dec

    def nesw_ra_dec(self, time=current_time(), location=pocs.observatory.observer.location,
                    alt=pocs.observatory.location['horizon']):

        nesw = {'north:': 0 * u.deg, 'east': 90 * u.deg, 'south': 180 * u.deg, 'west': 270 * u.deg}

        nesw_ra_dec = {}

        for az in nesw:
            try:
                alt_az = AltAz(nesw[az], alt=alt, obstime=time, location=location)

                nesw_ra_dec[az] = alt_az.transform_to(FK5)

            except Exception as e:
                print('Incorrent time/location input! Error: ', e)

        return nesw_ra_dec

    def start_time(self, time=current_time(), location=pocs.observatory.observer.location):

        '''Used to find the start time of the VO evnt from the observatory's perspective.

         Params: time - in astropy.Time format, the given start of a VO event. Default: current time at location
                 location - in astropy.coordinates Earth Location format. Default: current POCS location.

        This method will be used to determine when the observatory can start observing a VO event. If the 
        supplied time of the event is before sunset, for example, it will set the start_time to whichever 
        is the greatest: sunset time or current time.'''

        pocs.observatory.observer.location = location

        night_start = pocs.observatory.observer.tonight()[0]
        now_time = current_time()

        start_time = max([time, now_time, night_start])

        return start_time

    def time_now(self):
        return current_time()

    def sun_rise_set(self):
        return pocs.observatory.observer.tonight()


