import subprocess
import os
import re

from skimage.feature import register_translation
from astropy.utils.data import get_file_contents
from astropy.io import fits

import dateutil
import numpy as np
from photutils import find_peaks

from .error import InvalidSystemCommand
from . import listify, PrintLog


def cr2_to_fits(cr2_fname, fits_fname=None, clobber=False):
    """ Convert a Canon CR2 file into FITS, saving keywords

    Args:
        cr2_fname(str):     Filename of CR2 to be converted to FITS
        fits_fname(str, optional): Name of FITS output file, defaults to same name as `cr2_fname`
            but with '.fits' extension
        clobber(bool):      Clobber existing FITS or not, defaults to False

    Returns:
        fits.PrimaryHDU:   FITS file
    """

    if fits_fname is None:
        fits_fname = cr2_fname.replace('.cr2', '.fits')

    pgm = read_pgm(cr2_to_pgm(cr2_fname))
    exif = read_exif(cr2_fname)

    hdu = fits.PrimaryHDU(pgm)

    hdu.header.set('ISO', exif['ISO speed'])
    hdu.header.set('FILTER', exif['Filter pattern'])
    hdu.header.set('CAM-MULT', exif['Camera multipliers'])
    hdu.header.set('DAY-MULT', exif['Daylight multipliers'])
    hdu.header.set('CAM-NAME', exif['Camera'])
    hdu.header.set('EXPTIME', exif['Shutter'].split(' ')[0])
    hdu.header.set('MULTIPLY', exif['Daylight multipliers'])
    hdu.header.set('DATE-OBS', dateutil.parser.parse(exif['Timestamp']).isoformat())

    hdu.writeto(fits_fname, clobber=clobber)

    return hdu


def cr2_to_pgm(cr2_fname, pgm=None, dcraw='/usr/bin/dcraw', clobber=True, logger=PrintLog(verbose=False)):
    """ Converts CR2 to PGM using dcraw

    Args:
        cr2_fname(str):     Filename of CR2 to be converted
        pgm(str, optional): Name of PGM output file. Optional. If nothing is provided
            then the PGM will have the same name as the input file but with the .pgm extension
        dcraw(str):         dcraw binary
        clobber(bool):      Clobber existing PGM or not, defaults to True
        logger(obj):        Object that can support standard logging methods, defaults to None.

    Returns:
        str:   PGM file name
    """
    assert os.path.exists(dcraw), "dcraw does not exist at location {}".format(dcraw)
    assert os.path.exists(cr2_fname), "cr2 file does not exist at location {}".format(cr2_fname)

    if pgm is None:
        pgm_fname = cr2_fname.replace('.cr2', '.pgm')
    else:
        pgm_fname = pgm

    if os.path.exists(pgm_fname) and not clobber:
        logger.debug("PGM file exists and clobber=False, returning existing file: {}".format(pgm_fname))
    else:
        try:
            # Build the command for this file
            command = '{} -t 0 -D -4 {}'.format(dcraw, cr2_fname)
            cmd_list = command.split()
            logger.debug("PGM Conversion command: \n {}".format(cmd_list))

            # Run the command
            if subprocess.check_call(cmd_list) == 0:
                logger.debug("PGM Conversion command successful")

        except subprocess.CalledProcessError as err:
            raise InvalidSystemCommand(msg="File: {} \n err: {}".format(cr2_fname, err))

    return pgm_fname


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
        raw_exif = subprocess.check_output(cmd_list).decode('utf-8').split('\n')[1:-1]
    except subprocess.CalledProcessError as err:
        raise InvalidSystemCommand(msg="File: {} \n err: {}".format(fname, err))

    if raw_exif:
        for line in raw_exif:
            key, value = line.split(': ')
            exif[key] = value

    return exif


def read_pgm(pgm, byteorder='>', logger=PrintLog(verbose=False)):
    """Return image data from a raw PGM file as numpy array.

    Note:
        Format Spec: http://netpbm.sourceforge.net/doc/pgm.html
        Source: http://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm

    Args:
        pgm(str):           Filename of PGM to be converted
        byteorder(str):     Big endian. See Note.
        clobber(bool):      Clobber existing PGM or not. Defaults to True
        logger(obj):        Object that can support standard logging methods. Defaults to PrintLog()

    Returns:
        numpy.array:        The raw data from the PGMx

    """

    with open(pgm, 'rb') as f:
        buffer = f.read()
    try:
        header, width, height, maxval = re.search(
            b"(^P5\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n])*"
            b"(\d+)\s(?:\s*#.*[\r\n]\s)*)", buffer).groups()
    except AttributeError:
        raise ValueError("Not a raw PGM file: '{}'".format(pgm))
    return np.frombuffer(buffer,
                         dtype='u1' if int(maxval) < 256 else byteorder + 'u2',
                         count=int(width) * int(height),
                         offset=len(header)
                         ).reshape((int(height), int(width)))


def measure_offset(d0, d1, crop=True, pixel_factor=100):
    """ Measures the offset of two images.

    This is a small wrapper around `scimage.feature.register_translation`. For now just
    crops the data to be the center image.

    Note:
        This method will automatically crop_data data sets that are large. To prevent
        this, set crop_data=False.

    Args:
        d0(numpy.array):    Array representing PGM data for first file
        d1(numpy.array):    Array representing PGM data for second file
    """

    assert d0.shape == d1.shape, 'Data sets must be same size to measure offset'

    if crop_data and d0.shape[0] > 500:
        d0 = crop_data(d0)
        d1 = crop_data(d1)

    shift, error, diffphase = register_translation(d0, d1, pixel_factor)

    return shift, error, diffphase


def crop_data(data, box_width=200):
    """ Return a cropped portion of the image

    Shape is a box centered around the middle of the data

    Args:
        data(np.array):     The original data, e.g. an image.
        box_width(int):     Size of box width in pixels, defaults to 200px

    Returns:
        np.array:           A clipped (thumbnailed) version of the data
    """
    assert data.shape[0] > box_width, "Can't clip data, it's smaller than {}".format(box_width)
    # Get the center
    x_len, y_len = data.shape
    x_center = int(x_len / 2)
    y_center = int(y_len / 2)

    box_width = int(box_width / 2)

    center = data[x_center - box_width:x_center + box_width, y_center - box_width:y_center + box_width]

    return center
