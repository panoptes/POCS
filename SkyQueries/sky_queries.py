#!/usr/bin/env python

from astropy import coordinates
import astropy.units as u

import math as m

from astroquery.simbad import Simbad

mps = u.meter / u.second

c = 3*10^8 * mps

def find_candidates(coords, error_rad):

     cands = []

     tbl = Simbad.query_region(coords, error_rad)

     length = len(tbl)

     for j in xrange(length - 1):
          
          name = str(tbl[j]['MAIN_ID'])
          coords = str(tbl[j]['RA_s_ICRS']) + ' ' + str(tbl[j]['DEC_s_ICRS'])
          v = float(tbl[j]['RV_VALUE']) * mps
          obs_wavelength = str(tbl[j]['GALDIM_WAVELENGTH'])
          typ = str(tbl[j]['OTYPE'])

          if v != m.nan:
               redshift = m.sqrt((1 + v/c)/(1-v/c))
          else:
               redshift = m.inf

          cands.append({'name': name,
                        'coords': coords,
                        'redshift': redshift,
                        'obs_wavelength': obs_wavelength,
                        'type': typ})

     return cands

