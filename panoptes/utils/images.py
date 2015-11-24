import subprocess
import os
import re
import datetime

from astropy.utils.data import get_file_contents
from astropy.stats import sigma_clipped_stats

import numpy as np
from astropy.stats import sigma_clipped_stats
from photutils import find_peaks

from .error import InvalidSystemCommand, PanError
from . import listify, PrintLog


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


def cr2_to_pgm(cr2, pgm=None, dcraw='/usr/bin/dcraw', clobber=True, logger=PrintLog(verbose=False)):
    """ Converts CR2 to PGM using dcraw

    Args:
        cr2(str):           Filename of CR2 to be converted
        pgm(str, optional): Name of PGM output file. Optional. If nothing is provided
            then the PGM will have the same name as the input file but with the .pgm extension
        dcraw(str):         dcraw binary
        clobber(bool):      Clobber existing PGM or not. Defaults to True
        logger(obj):        Object that can support standard logging methods. Defaults to None.

    Returns:
        str:   PGM file name
    """
    assert os.path.exists(dcraw), "dcraw does not exist at location {}".format(dcraw)
    assert os.path.exists(cr2), "cr2 file does not exist at location {}".format(cr2)

    if pgm is None:
        pgm_fname = cr2.replace('.cr2', '.pgm')
    else:
        pgm_fname = pgm

    if os.path.exists(pgm_fname) and not clobber:
        logger.debug("PGM file exists and clobber=False, returning existing file: {}".format(pgm_fname))
    else:
        try:
            # Build the command for this file
            command = '{} -t 0 -D -4 {}'.format(dcraw, cr2)
            cmd_list = command.split()
            logger.debug("PGM Conversion command: \n {}".format(cmd_list))

            # Run the command
            if subprocess.check_call(cmd_list) == 0:
                logger.debug("PGM Conversion command successful")

        except subprocess.CalledProcessError as err:
            raise InvalidSystemCommand(msg="File: {} \n err: {}".format(cr2, err))

    return pgm_fname


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


def measure_offset(d0, d1, method='nearby', crop=True):
    """ Measures the offset of two images.

    Assumes the data is already clipped to an appropriate size. See `clip_image`

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

    peaks_01 = get_peaks(d0)
    peaks_02 = get_peaks(d1)

    method_lookup = {
        'nearby': nearby
    }

    same_target = method_lookup[method](peaks_01, peaks_02)

    if len(same_target):
        y_mean = same_target[:, 1].mean()
        x_mean = same_target[:, 0].mean()
    else:
        x_mean = 0
        y_mean = 0

    return (x_mean, y_mean)


def get_peaks(data, threshold=None, sigma=5.0, min_separation=10):
    """ Gets the local peaks for the array provided

    Args:
        data(numpy.array):      Array of data.
        threshold(float):       Threshold above which to look for peaks. Defaults to None in
            which case the `median + (10.0 * std)`` is used.
        sigma(float):           For computing data stats. Defaults to 5.0
        min_separation(int):    Minimum separation for the peaks. Defaults to 10 pixels.

    Returns:
        numpy.array:        See `photutils.find_peaks` for details.
    """
    mean, median, std = sigma_clipped_stats(data, sigma=sigma)

    if threshold is None:
        threshold = median + (10.0 * std)

    peaks = find_peaks(data, threshold=threshold, min_separation=min_separation, exclude_border=True)

    return peaks


def nearby(test_list_0, test_list_1, delta=3):
    """ Get data points that are nearby other ones.

    Note:
        This is not a very smart method and should be replaced by real cross-correlation.

    """
    same_target = list()

    for x0, y0 in test_list_0:
        for x1, y1 in test_list_1:
            if abs(x0 - x1) < delta:
                if abs(y0 - y1) < delta:
                    same_target.append((x0 - x1, y0 - y1))

    return np.array(same_target)


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


def compare_files(f0, f1, compare=False):
    pgm_00 = f0.replace('.cr2', '.pgm')
    pgm_01 = f1.replace('.cr2', '.pgm')

    # if not os.path.exists(pgm_00):
    pgm_00 = cr2_to_pgm(f0)
    # else:
    #    print("Path exists, using {}".format(pgm_00))

    # if not os.path.exists(pgm_01):
    pgm_01 = cr2_to_pgm(f1)
    # else:
    #    print("Path exists, using {}".format(pgm_01))

#    exif_00 = read_exif(pgm_00)
    exif_01 = read_exif(f1)

    raw_data_00 = crop_data(read_pgm(pgm_00))
    raw_data_01 = crop_data(read_pgm(pgm_01))

    x0, y0 = measure_offset(raw_data_00, raw_data_01)

    fmt = '%a %b %d %H:%M:%S %Y'
    t = datetime.datetime.strptime(exif_01.get('Timestamp'), fmt)

    if compare:
        cmd_list = '/var/panoptes/bin/measure_offset $f0 $f1'
        output = subprocess.check_output(cmd_list).decode('utf-8').split('\n')[1:-1]

        print(output)

        x1 = float(get_file_contents('xcent.txt'))
        y1 = float(get_file_contents('ycent.txt'))

        vals = (x0, y0, x1, y1, t)

    else:
        vals = (x0, y0, t)

    return vals
