import numpy as np
import os

from warnings import warn

from astropy.io import fits

from .conversions import cr2_to_pgm
from .io import read_pgm


def read_image_data(fname):
    """ Read an image and return the data.

    Convenience function to open any kind of data we use

    Args:
        fname(str):    Filename of image

    Returns:
        np.array:   Image data
    """
    assert os.path.exists(fname), warn("File must exist to read: {}".format(fname))

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
