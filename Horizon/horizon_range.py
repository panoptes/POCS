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

    def max_min_ra_dec(self, time=current_time(), location=pocs.observatory.observer.location,
                       n_steps=100, range_az=[], alt=pocs.observatory.location['horizon']):

        max_min_ra_dec = {'max_ra': np.nan, 'min_ra': np.nan,
                          'max_dec': np.nan, 'min_dec': np.nan}

        if len(range_az) < 1:
            range_az = np.arange(n_steps)*360.0/n_steps * u.deg

        ras = []
        decs = []

        for az in range_az:
            try:
                alt_az = AltAz(az, alt=alt, obstime=time, location=location)

                ras.append(alt_az.transform_to(FK5).ra)
                decs.append(alt_az.transform_to(FK5).dec)
            except:
                print('Incorrent time/location input!')
                return max_min_ra_dec

        max_min_ra_dec['max_ra'] = max(ras)
        max_min_ra_dec['min_ra'] = min(ras)
        max_min_ra_dec['max_dec'] = max(decs)
        max_min_ra_dec['min_dec'] = min(decs)

        return max_min_ra_dec

    def nesw_ra_dec(self, time=current_time(), location=pocs.observatory.observer.location,
                    alt=pocs.observatory.location['horizon']):

        nesw = {'north:': 0 * u.deg, 'east': 90 * u.deg, 'south': 180 * u.deg, 'west': 270 * u.deg}

        nesw_ra_dec = {}

        for az in nesw:
            try:
                alt_az = AltAz(nesw[az], alt=alt, obstime=time, location=location)

                nesw_ra_dec[az] = alt_az.transform_to(FK5)

            except:
                print('Incorrent time/location input!')
                return nesw_ra_dec

        return nesw_ra_dec

    def check_time(self, time, location=pocs.observatory.observer.location):

        







