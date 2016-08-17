import os
import subprocess

from astropy.io import fits
from pprint import pprint
from warnings import warn

from pocs.utils import current_time
from pocs.utils import error
from pocs.version import version

from .calculations import get_solve_field
from .io import read_exif
from .io import read_pgm
from .metadata import *


def process_cr2(cr2_fname, to_fits=True, fits_headers={}, solve=False, make_pretty=False, **kwargs):
    """ Process a Canon CR2 file

    This will do basic processing on CR2 file, including making a pretty image, FITS conversion, and plate-solving.

    Note:
        If `solve` is set to `True` then `to_fits` will also be set to `True`

    Arguments:
        cr2_fname {str} -- Filename of the CR2 image to be processed
        **kwargs {dict} -- Additional params to pass along to the various functions

    Keyword Arguments:
        to_fits {bool} -- A bool indicating if CR2 should be converted to FITS (default: {True})
        fits_headers {dict} -- A dict of header information to be stored with FITS file (default: {{}})
        solve {bool} -- A bool indicating if FITS file should be plate-solved (default: {True})
        make_pretty {bool} -- A bool indicating if a pretty image should be created (default: {False})

    Returns:
        dict -- A list of the FITS header values, which can contain solve information

    """
    assert os.path.exists(cr2_fname), warn("File must exist: {}".format(cr2_fname))

    verbose = kwargs.get('verbose', False)

    processed_info = {}

    try:
        if verbose:
            print("Processing image")

        if make_pretty:
            # If we have the object name, pass it to pretty image
            if 'title' in fits_headers:
                kwargs['title'] = "{}".format(fits_headers.get('title'))

            pretty_image = make_pretty_image(cr2_fname, **kwargs)
            processed_info['pretty_image'] = pretty_image

        if to_fits or solve:
            fits_fname = cr2_to_fits(cr2_fname, fits_headers=fits_headers, **kwargs)

        if solve:
            try:
                solve_info = get_solve_field(fits_fname, fits_headers=fits_headers, **kwargs)
                if verbose:
                    print("Solve info:")
                    pprint(solve_info)

                processed_info.update(solve_info)
            except error.PanError as e:
                warn("Timeout while solving: {}".format(e))
            except Exception as e:
                raise error.PanError("Can't solve field: {}".format(e))
    except Exception as e:
        warn("Problem in processing: {}".format(e))

    if verbose:
        print("Processed info:")
        pprint(processed_info)

    return processed_info

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


