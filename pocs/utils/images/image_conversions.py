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

from .image_calculations import *
from .image_metadata import *

# Plot support
sb.set()
quantity_support()

solve_re = [
    re.compile('RA,Dec = \((?P<center_ra>.*),(?P<center_dec>.*)\)'),
    re.compile('pixel scale (?P<pixel_scale>.*) arcsec/pix'),
    re.compile('Field rotation angle: up is (?P<rotation>.*) degrees E of N'),
]


def make_pretty_image(fname, timeout=15, verbose=False, **kwargs):
    """ Make a pretty picture

    Args:
        fname(str, required):       Filename to solve in either .cr2 or .fits extension.
        timeout(int, optional):     Timeout for the solve-field command, defaults to 60 seconds.
        verbose(bool, optional):    Show output, defaults to False.
    """
    assert os.path.exists(fname), warnings.warn("File doesn't exist, can't make pretty: {}".format(fname))
    title = '{} {}'.format(kwargs.get('title', ''), current_time().isot)

    solve_field = "{}/scripts/cr2_to_jpg.sh".format(os.getenv('POCS'), '/var/panoptes/POCS')
    cmd = [solve_field, fname, title]

    if kwargs.get('primary', False):
        cmd.append('link')

    if verbose:
        print(cmd)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if verbose:
            print(proc)
    except OSError as e:
        raise error.InvalidCommand("Can't send command to gphoto2. {} \t {}".format(e, run_cmd))
    except ValueError as e:
        raise error.InvalidCommand("Bad parameters to gphoto2. {} \t {}".format(e, run_cmd))
    except Exception as e:
        raise error.PanError("Timeout on plate solving: {}".format(e))

    return fname.replace('cr2', 'jpg')

def cr2_to_fits(cr2_fname, fits_fname=None, clobber=True, fits_headers={}, remove_cr2=False, **kwargs):
    """ Convert a Canon CR2 file into FITS, saving keywords

    Args:
        cr2_fname(str):     Filename of CR2 to be converted to FITS
        fits_fname(str, optional): Name of FITS output file, defaults to same name as `cr2_fname`
            but with '.fits' extension
        clobber(bool):      Clobber existing FITS or not, defaults to False
        fits_headers(dict): Key/value pairs to be put into FITS header.
        remove_cr2(bool):   Bool indiciating if original file should be removed after conversion,
            defaults to False.

    Returns:
        fits.PrimaryHDU:   FITS file
    """

    verbose = kwargs.get('verbose', False)

    if fits_fname is None:
        fits_fname = cr2_fname.replace('.cr2', '.fits')

    if verbose:
        print("Converting CR2 to PGM: {}".format(cr2_fname))

    pgm = read_pgm(cr2_to_pgm(cr2_fname), remove_after=True)
    exif = read_exif(cr2_fname)

    hdu = fits.PrimaryHDU(pgm)

    hdu.header.set('APERTURE', exif.get('Aperture', ''))
    hdu.header.set('CAM-MULT', exif.get('Camera multipliers', ''))
    hdu.header.set('CAM-NAME', exif.get('Camera', ''))
    hdu.header.set('CREATOR', exif.get('Owner', '').replace('"', ''))
    hdu.header.set('DATE-OBS', date_parser.parse(exif.get('Timestamp', '')).isoformat())
    hdu.header.set('DAY-MULT', exif.get('Daylight multipliers', ''))
    hdu.header.set('EXPTIME', exif.get('Shutter', '').split(' ')[0])
    hdu.header.set('FILENAME', '/'.join(cr2_fname.split('/')[-1:]))
    hdu.header.set('FILTER', exif.get('Filter pattern', ''))
    hdu.header.set('ISO', exif.get('ISO speed', ''))
    hdu.header.set('MULTIPLY', exif.get('Daylight multipliers', ''))

    if verbose:
        print("Reading FITS header")
    for key, value in fits_headers.items():
        try:
            hdu.header.set(key.upper()[0: 8], "{}".format(value))
        except:
            pass

    try:
        if verbose:
            print("Saving fits file to: {}".format(fits_fname))
        hdu.writeto(fits_fname, output_verify='silentfix', clobber=clobber)
    except Exception as e:
        warnings.warn("Problem writing FITS file: {}".format(e))
    else:
        if remove_cr2:
            os.unlink(cr2_fname)

    return fits_fname


def cr2_to_pgm(cr2_fname, pgm_fname=None, dcraw='/usr/bin/dcraw', clobber=True, logger=None):
    """ Converts CR2 to PGM using dcraw

    Args:
        cr2_fname(str):     Filename of CR2 to be converted
        pgm_fname(str, optional): Name of PGM output file. Optional. If nothing is provided
            then the PGM will have the same name as the input file but with the .pgm extension
        dcraw(str):         dcraw binary
        clobber(bool):      Clobber existing PGM or not, defaults to True
        logger(obj):        Object that can support standard logging methods, defaults to None.

    Returns:
        str:   PGM file name
    """
    assert os.path.exists(dcraw), "dcraw does not exist at location {}".format(dcraw)
    assert os.path.exists(cr2_fname), "cr2 file does not exist at location {}".format(cr2_fname)

    if pgm_fname is None:
        pgm_fname = cr2_fname.replace('.cr2', '.pgm')
    else:
        pgm_fname = pgm_fname

    if os.path.exists(pgm_fname) and not clobber:
        if logger:
            logger.debug("PGM file exists and clobber=False, returning existing file: {}".format(pgm_fname))
    else:
        try:
            # Build the command for this file
            command = '{} -t 0 -D -4 {}'.format(dcraw, cr2_fname)
            cmd_list = command.split()
            if logger:
                logger.debug("PGM Conversion command: \n {}".format(cmd_list))

            # Run the command
            if subprocess.check_call(cmd_list) == 0:
                if logger:
                    logger.debug("PGM Conversion command successful")

        except subprocess.CalledProcessError as err:
            raise InvalidSystemCommand(msg="File: {} \n err: {}".format(cr2_fname, err))

    return pgm_fname