import glob
import os
import re
import shutil
import subprocess
import warnings

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.table import Table as Table
from astropy.time import Time
from skimage.feature import register_translation

import matplotlib as mpl

from dateutil import parser as date_parser
mpl.use('Agg')
from matplotlib import pyplot as plt

import numpy as np
import pandas as pd
import seaborn as sb

from astropy.visualization import quantity_support

from scipy.optimize import curve_fit

from pocs.utils import current_time
from pocs.utils import error
from pocs.utils.error import *

from .calculations import *
from .conversions import *

# Plot support
sb.set()
quantity_support()

solve_re = [
    re.compile('RA,Dec = \((?P<center_ra>.*),(?P<center_dec>.*)\)'),
    re.compile('pixel scale (?P<pixel_scale>.*) arcsec/pix'),
    re.compile('Field rotation angle: up is (?P<rotation>.*) degrees E of N'),
]

def read_exif(fname, dcraw='/usr/bin/dcraw'):
    """ Read a raw image file and return the EXIF information

    Args:
        fname(str):     Raw file to read
        dcraw(str):         dcraw binary

    Returns:
        dict:           EXIF information
    """
    assert fname is not None
    exif = {}

    try:
        # Build the command for this file
        command = '{} -i -v {}'.format(dcraw, fname)
        cmd_list = command.split()

        # Run the command
        raw_exif = subprocess.check_output(cmd_list).decode('utf-8').split('\n')[1: -1]
    except subprocess.CalledProcessError as err:
        raise InvalidSystemCommand(msg="File: {} \n err: {}".format(fname, err))

    if raw_exif:
        for line in raw_exif:
            key, value = line.split(': ')
            exif[key] = value

    return exif


def read_pgm(fname, byteorder='>', remove_after=False):
    """Return image data from a raw PGM file as numpy array.

    Note:
        Format Spec: http://netpbm.sourceforge.net/doc/pgm.html
        Source: http://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm

    Args:
        fname(str):         Filename of PGM to be converted
        byteorder(str):     Big endian, see Note.
        remove_after(bool):   Delete fname file after reading, defaults to False.
        clobber(bool):      Clobber existing PGM or not, defaults to True

    Returns:
        numpy.array:        The raw data from the PGMx

    """

    with open(fname, 'rb') as f:
        buffer = f.read()

    try:
        header, width, height, maxval = re.search(
            b"(^P5\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n]\s)*)", buffer).groups()
    except AttributeError:
        raise ValueError("Not a raw PGM file: '{}'".format(fname))
    else:
        if remove_after:
            os.remove(fname)

    data = np.frombuffer(buffer,
                         dtype='u1' if int(maxval) < 256 else byteorder + 'u2',
                         count=int(width) * int(height),
                         offset=len(header)
                         ).reshape((int(height), int(width)))

    return data


def read_image_data(fname):
    """ Read an image and return the data.

    Convenience function to open any kind of data we use

    Args:
        fname(str):    Filename of image

    Returns:
        np.array:   Image data
    """
    assert os.path.exists(fname), warnings.warn("File must exist to read: {}".format(fname))

    method_lookup = {
        'cr2': lambda fn: read_pgm(cr2_to_pgm(fn), remove_after=True),
        'fits': lambda fn: fits.open(fn)[0].data,
        'new': lambda fn: fits.open(fn)[0].data,
        'pgm': lambda fn: read_pgm(fn),
    }

    file_type = fname.split('.')[-1]
    method = method_lookup.get(file_type, None)

    d = np.array([])
    if method is not None:
        d = method(fname)

    return d

def crop_data(data, box_width=200, center=None, verbose=False):
    """ Return a cropped portion of the image

    Shape is a box centered around the middle of the data

    Args:
        data(np.array):     The original data, e.g. an image.
        box_width(int):     Size of box width in pixels, defaults to 200px
        center(tuple(int)): Crop around set of coords, defaults to image center.

    Returns:
        np.array:           A clipped (thumbnailed) version of the data
    """
    assert data.shape[0] >= box_width, "Can't clip data, it's smaller than {} ({})".format(box_width, data.shape)
    # Get the center
    if verbose:
        print("Data to crop: {}".format(data.shape))

    if center is None:
        x_len, y_len = data.shape
        x_center = int(x_len / 2)
        y_center = int(y_len / 2)
    else:
        x_center = int(center[0])
        y_center = int(center[1])
        if verbose:
            print("Using center: {} {}".format(x_center, y_center))

    box_width = int(box_width / 2)
    if verbose:
        print("Box width: {}".format(box_width))

    center = data[x_center - box_width: x_center + box_width, y_center - box_width: y_center + box_width]

    return center


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