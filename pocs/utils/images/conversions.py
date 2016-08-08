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


def make_pretty_image(fname, timeout=15, **kwargs):
    """ Make a pretty image

    This calls out to an external script which will try to extract the JPG directly from the CR2 file,
    otherwise will do an actual conversion

    Notes:
        See `$POCS/scripts/cr2_to_jpg.sh`

    Arguments:
        fname {str} -- Name of CR2 file
        **kwargs {dict} -- Additional arguments to be passed to external script

    Keyword Arguments:
        timeout {number} -- Process timeout (default: {15})

    Returns:
        str -- Filename of image that was created

    """
    assert os.path.exists(fname), warn("File doesn't exist, can't make pretty: {}".format(fname))

    verbose = kwargs.get('verbose', False)

    title = '{} {}'.format(kwargs.get('title', ''), current_time().isot)

    solve_field = "{}/scripts/cr2_to_jpg.sh".format(os.getenv('POCS'), '/var/panoptes/POCS')
    cmd = [solve_field, fname, title]

    if kwargs.get('primary', False):
        cmd.append('link')

    if verbose:
        print(cmd)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if verbose:
            print(proc)
    except OSError as e:
        raise error.InvalidCommand("Can't send command to gphoto2. {} \t {}".format(e, run_cmd))
    except ValueError as e:
        raise error.InvalidCommand("Bad parameters to gphoto2. {} \t {}".format(e, run_cmd))
    except Exception as e:
        raise error.PanError("Timeout on plate solving: {}".format(e))

    return fname.replace('cr2', 'jpg')
