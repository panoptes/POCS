import os
import re
import shutil
import subprocess
import warnings

from astropy import units as u
from astropy.coordinates import SkyCoord

from .calculations import *
from .conversions import *


def get_wcsinfo(fits_fname, verbose=False):
    """Returns the WCS information for a FITS file.

    Uses the `wcsinfo` astrometry.net utility script to get the WCS information from a plate-solved file

    Parameters
    ----------
    fits_fname : {str}
        Name of a FITS file that contains a WCS.
    verbose : {bool}, optional
        Verbose (the default is False)

    Returns
    -------
    dict
        Output as returned from `wcsinfo`
    """
    assert os.path.exists(fits_fname), warnings.warn("No file exists at: {}".format(fits_fname))

    wcsinfo = shutil.which('wcsinfo')
    if wcsinfo is None:
        wcsinfo = '{}/astrometry/bin/wcsinfo'.format(os.getenv('PANDIR', default='/var/panoptes'))

    run_cmd = [wcsinfo, fits_fname]

    if verbose:
        print("wcsinfo command: {}".format(run_cmd))

    proc = subprocess.Popen(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    try:
        output, errs = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        output, errs = proc.communicate()

    unit_lookup = {
        'crpix0': u.pixel,
        'crpix1': u.pixel,
        'crval0': u.degree,
        'crval1': u.degree,
        'cd11': (u.deg / u.pixel),
        'cd12': (u.deg / u.pixel),
        'cd21': (u.deg / u.pixel),
        'cd22': (u.deg / u.pixel),
        'imagew': u.pixel,
        'imageh': u.pixel,
        'pixscale': (u.arcsec / u.pixel),
        'orientation': u.degree,
        'ra_center': u.degree,
        'dec_center': u.degree,
        'orientation_center': u.degree,
        'ra_center_h': u.hourangle,
        'ra_center_m': u.minute,
        'ra_center_s': u.second,
        'dec_center_d': u.degree,
        'dec_center_m': u.minute,
        'dec_center_s': u.second,
        'fieldarea': (u.degree * u.degree),
        'fieldw': u.degree,
        'fieldh': u.degree,
        'decmin': u.degree,
        'decmax': u.degree,
        'ramin': u.degree,
        'ramax': u.degree,
        'ra_min_merc': u.degree,
        'ra_max_merc': u.degree,
        'dec_min_merc': u.degree,
        'dec_max_merc': u.degree,
        'merc_diff': u.degree,
    }

    wcs_info = {}
    for line in output.split('\n'):
        try:
            k, v = line.split(' ')
            try:
                v = float(v)
            except:
                pass

            wcs_info[k] = float(v) * unit_lookup.get(k, 1)
        except ValueError:
            pass
            # print("Error on line: {}".format(line))

    wcs_info['wcs_file'] = fits_fname

    return wcs_info


def get_target_position(target, wcs_file, verbose=False):
    assert os.path.exists(wcs_file), warnings.warn("No WCS file: {}".format(wcs_file))
    assert isinstance(target, SkyCoord), warnings.warn("Must pass a SkyCoord")

    wcsinfo = shutil.which('wcs-rd2xy')
    if wcsinfo is None:
        wcsinfo = '{}/astrometry/bin/wcs-rd2xy'.format(os.getenv('PANDIR', default='/var/panoptes'))

    run_cmd = [wcsinfo, '-w', wcs_file, '-r', str(target.ra.value), '-d', str(target.dec.value)]

    if verbose:
        print("wcsinfo command: {}".format(run_cmd))

    result = subprocess.check_output(run_cmd)
    lines = result.decode('utf-8').split('\n')
    if verbose:
        print("Result: {}".format(result))
        print("Lines: {}".format(lines))

    target_center = None

    for line in lines:
        center_match = re.match('.*pixel \((.*)\).*', line)
        if center_match:
            ra, dec = center_match.group(1).split(', ')
            if verbose:
                print(center_match)
                print(ra, dec)
            target_center = (float(dec), float(ra))

    if verbose:
        print("Target center: {}".format(target_center))
    return target_center
