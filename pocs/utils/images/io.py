import os
import re
import subprocess
import warnings

from astropy.io import fits

import numpy as np

from .calculations import *
from .conversions import *


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
