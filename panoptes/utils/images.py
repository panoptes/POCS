import os
import re
import warnings
import subprocess
import shutil
import glob

from skimage.feature import register_translation
from astropy.io import fits
from astropy import units as u
from astropy.time import Time
from astropy.table import Table as Table
from astropy.coordinates import SkyCoord

from dateutil import parser as date_parser
import matplotlib as mpl
mpl.use('Agg')
from matplotlib import pyplot as plt

import numpy as np
import pandas as pd
import seaborn as sb

from astropy.visualization import quantity_support

from scipy.optimize import curve_fit

from .error import *
from . import PrintLog
from . import error
from . import current_time

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


def solve_field(fname, timeout=15, solve_opts=[], verbose=False, **kwargs):
    """ Plate solves an image.

    Args:
        fname(str, required):       Filename to solve in either .cr2 or .fits extension.
        timeout(int, optional):     Timeout for the solve-field command, defaults to 60 seconds.
        solve_opts(list, optional): List of options for solve-field.
        verbose(bool, optional):    Show output, defaults to False.
    """

    if fname.endswith('cr2'):
        fname = cr2_to_fits(fname, **kwargs)

    solve_field = "{}/scripts/solve_field.sh".format(os.getenv('POCS'), '/var/panoptes/POCS')

    if not os.path.exists(solve_field):
        raise InvalidSystemCommand("Can't find solve-field: {}".format(solve_field))

    if solve_opts:
        options = solve_opts
    else:
        options = [
            '--guess-scale',
            '--cpulimit', str(timeout),
            '--no-verify',
            '--no-plots',
            '--crpix-center',
            '--downsample', '4',
        ]
        if kwargs.get('clobber', True):
            options.append('--overwrite')
        if kwargs.get('skip_solved', True):
            options.append('--skip-solved')
        if 'ra' in kwargs:
            options.append('--ra')
            options.append(str(kwargs.get('ra')))
        if 'dec' in kwargs:
            options.append('--dec')
            options.append(str(kwargs.get('dec')))
        if 'radius' in kwargs:
            options.append('--radius')
            options.append(str(kwargs.get('radius')))

        if os.getenv('PANTEMP'):
            options.append('--temp-dir')
            options.append(os.getenv('PANTEMP'))

    cmd = [solve_field, ' '.join(options), fname]
    if verbose:
        print(cmd)

    try:
        proc = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        raise error.InvalidCommand("Can't send command to gphoto2. {} \t {}".format(e, run_cmd))
    except ValueError as e:
        raise error.InvalidCommand("Bad parameters to gphoto2. {} \t {}".format(e, run_cmd))
    except Exception as e:
        raise error.PanError("Timeout on plate solving: {}".format(e))

    return proc


def get_solve_field(fname, **kwargs):
    """ Convenience function to wait for `solve_field` to finish.

    This function merely passes the `fname` of the image to be solved along to `solve_field`,
    which returns a subprocess.Popen object. This function then waits for that command
    to complete, populates a dictonary with the EXIF informaiton and returns.

    Parameters
    ----------
    fname : {str}
        Name of file to be solved, either a FITS or CR2
    **kwargs : {dict}
        Options to pass to `solve_field`

    Returns
    -------
    dict
        Keyword information from the solved field
    """

    verbose = kwargs.get('verbose', False)

    proc = solve_field(fname, **kwargs)
    try:
        output, errs = proc.communicate(timeout=kwargs.get('timeout', 30))
    except subprocess.TimeoutExpired:
        proc.kill()
        output, errs = proc.communicate()

    out_dict = {}

    if errs is not None:
        warnings.warn("Error in solving: {}".format(errs))
    else:
        # Read the EXIF information from the CR2
        if fname.endswith('cr2'):
            out_dict.update(read_exif(fname))
            fname = fname.replace('cr2', 'new')  # astrometry.net default extension
            out_dict['solved_fits_file'] = fname

        try:
            out_dict.update(fits.getheader(fname))
        except OSError:
            if verbose:
                print("Can't read fits header for {}".format(fname))

        # Read items from the output
        # for line in output.split('\n'):
        #     for regexp in solve_re:
        #         matches = regexp.search(line)
        #         if matches:
        #             out_dict.update(matches.groupdict())
        #             if verbose:
        #                 print(matches.groupdict())

    return out_dict


def solve_offset(first_dict, second_dict, verbose=False):
    """ Measures the offset of two images.

    This calculates the offset between the center of two images after plate-solving.

    Note:
        See `solve_field` for example of dict to be passed as argument.

    Args:
        first_dict(dict):   Dictonary describing the first image.
        second_dict(dict):   Dictonary describing the second image.

    Returns:
        out(dict):      Dictonary containing items related to the offset between the two images.
    """
    assert 'center_ra' in first_dict, warnings.warn("center_ra required for first image solving offset.")
    assert 'center_ra' in second_dict, warnings.warn("center_ra required for second image solving offset.")
    assert 'pixel_scale' in first_dict, warnings.warn("pixel_scale required for solving offset.")

    if verbose:
        print("Solving offset")

    first_ra = float(first_dict['center_ra']) * u.deg
    first_dec = float(first_dict['center_dec']) * u.deg

    second_ra = float(second_dict['center_ra']) * u.deg
    second_dec = float(second_dict['center_dec']) * u.deg

    rotation = float(first_dict['rotation']) * u.deg

    pixel_scale = float(first_dict['pixel_scale']) * (u.arcsec / u.pixel)

    first_time = Time(first_dict['DATE-OBS'])
    second_time = Time(second_dict['DATE-OBS'])

    out = {}

    # The pixel scale for the camera on our unit is:
    out['pixel_scale'] = pixel_scale
    out['rotation'] = rotation

    # Time between offset
    delta_t = ((second_time - first_time).sec * u.second).to(u.minute)
    out['delta_t'] = delta_t

    # Offset in degrees
    delta_ra = second_ra - first_ra
    delta_dec = second_dec - first_dec

    out['delta_ra_deg'] = delta_ra
    out['delta_dec_deg'] = delta_dec

    # Offset in pixels
    delta_ra = delta_ra.to(u.arcsec) / pixel_scale
    delta_dec = delta_dec.to(u.arcsec) / pixel_scale

    out['delta_ra'] = delta_ra
    out['delta_dec'] = delta_dec

    # Out unit drifted this many pixels in a minute:
    ra_rate = (delta_ra / delta_t)
    out['ra_rate'] = ra_rate

    dec_rate = (delta_dec / delta_t)
    out['dec_rate'] = dec_rate

    # Standard sidereal rate
    sidereal_rate = (24 * u.hour).to(u.minute) / (360 * u.deg).to(u.arcsec)
    out['sidereal_rate'] = sidereal_rate

    # Sidereal rate with our pixel_scale
    sidereal_scale = 1 / (sidereal_rate * pixel_scale)
    out['sidereal_scale'] = sidereal_scale

    # Difference between our rate and standard
    sidereal_factor = ra_rate / sidereal_scale
    out['sidereal_factor'] = sidereal_factor

    # Number of arcseconds we moved
    ra_delta_as = pixel_scale * delta_ra
    out['ra_delta_as'] = ra_delta_as

    # How many milliseconds at sidereal we are off
    # (NOTE: This should be current rate, not necessarily sidearal)
    ra_ms_offset = (ra_delta_as * sidereal_rate).to(u.ms)
    out['ra_ms_offset'] = ra_ms_offset

    # Number of arcseconds we moved
    dec_delta_as = pixel_scale * delta_dec
    out['dec_delta_as'] = dec_delta_as

    # How many milliseconds at sidereal we are off
    # (NOTE: This should be current rate, not necessarily sidearal)
    dec_ms_offset = (dec_delta_as * sidereal_rate).to(u.ms)
    out['dec_ms_offset'] = dec_ms_offset

    return out


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

    if fits_fname is None:
        fits_fname = cr2_fname.replace('.cr2', '.fits')

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

    for key, value in fits_headers.items():
        try:
            hdu.header.set(key.upper()[0: 8], "{}".format(value))
        except:
            pass

    try:
        hdu.writeto(fits_fname, output_verify='silentfix', clobber=clobber)
    except Exception as e:
        warnings.warn("Problem writing FITS file: {}".format(e))
    else:
        if remove_cr2:
            os.unlink(cr2_fname)

    return fits_fname


def cr2_to_pgm(cr2_fname, pgm_fname=None, dcraw='/usr/bin/dcraw', clobber=True, logger=PrintLog(verbose=False)):
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
        raw_exif = subprocess.check_output(cmd_list).decode('utf-8').split('\n')[1: -1]
    except subprocess.CalledProcessError as err:
        raise InvalidSystemCommand(msg="File: {} \n err: {}".format(fname, err))

    if raw_exif:
        for line in raw_exif:
            key, value = line.split(': ')
            exif[key] = value

    return exif


def read_pgm(fname, byteorder='>', remove_after=False, logger=PrintLog(verbose=False)):
    """Return image data from a raw PGM file as numpy array.

    Note:
        Format Spec: http://netpbm.sourceforge.net/doc/pgm.html
        Source: http://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm

    Args:
        fname(str):         Filename of PGM to be converted
        byteorder(str):     Big endian, see Note.
        remove_after(bool):   Delete fname file after reading, defaults to False.
        clobber(bool):      Clobber existing PGM or not, defaults to True
        logger(obj):        Object that can support standard logging methods, defaults to PrintLog()

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


def measure_offset(d0, d1, info={}, crop=True, pixel_factor=100, rate=None, verbose=False):
    """ Measures the offset of two images.

    This is a small wrapper around `scimage.feature.register_translation`. For now just
    crops the data to be the center image.

    Note
    ----
        This method will automatically crop_data data sets that are large. To prevent
        this, set crop_data=False.

    Parameters
    ----------
    d0 : {np.array}
        Array representing PGM data for first file (i.e. the first image)
    d1 : {np.array}
        Array representing PGM data for second file (i.e. the second image)
    info : {dict}, optional
        Optional information about the image, such as pixel scale, rotation, etc. (the default is {})
    crop : {bool}, optional
        Crop the image before offseting (the default is True, which crops the data to 500x500)
    pixel_factor : {number}, optional
        Subpixel factor (the default is 100, which will give precision to 1/100th of a pixel)
    rate : {number}, optional
        The rate at which the mount is moving (the default is sidereal rate)
    verbose : {bool}, optional
        Print messages (the default is False)

    Returns
    -------
    dict
        A dictionary of information related to the offset
    """

    assert d0.shape == d1.shape, 'Data sets must be same size to measure offset'

    if crop_data and d0.shape[0] > 500:
        d0 = crop_data(d0)
        d1 = crop_data(d1)

    offset_info = {}

    # Default for tranform matrix
    unit_pixel = 1 * (u.degree / u.pixel)

    # Get the WCS transformation matrix
    transform = np.array([
        [info.get('cd11', unit_pixel).value, info.get('cd12', unit_pixel).value],
        [info.get('cd21', unit_pixel).value, info.get('cd22', unit_pixel).value]
    ])

    # We want the negative of the applied orientation
    # theta = info.get('orientation', 0 * u.deg) * -1

    # Rotate the images so N is up (+y) and E is to the right (+x)
    # rd0 = rotate(d0, theta.value)
    # rd1 = rotate(d1, theta.value)

    shift, error, diffphase = register_translation(d0, d1, pixel_factor)

    offset_info['shift'] = (shift[0], shift[1])
    # offset_info['error'] = error
    # offset_info['diffphase'] = diffphase

    if transform is not None:

        coords_delta = np.array(shift).dot(transform)
        if verbose:
            print("Δ coords: {}".format(coords_delta))

        # pixel_scale = float(info.get('pixscale', 10.2859)) * (u.arcsec / u.pixel)

        sidereal = (15 * (u.arcsec / u.second))

        # Default to guide rate (0.9 * sidereal)
        if rate is None:
            rate = 0.9 * sidereal

        # # Number of arcseconds we moved
        ra_delta_as = (coords_delta[0] * u.deg).to(u.arcsec)
        dec_delta_as = (coords_delta[1] * u.deg).to(u.arcsec)
        offset_info['ra_delta_as'] = ra_delta_as
        offset_info['dec_delta_as'] = dec_delta_as

        # # How many milliseconds at current rate we are off
        ra_ms_offset = (ra_delta_as / rate).to(u.ms)
        dec_ms_offset = (dec_delta_as / rate).to(u.ms)
        offset_info['ra_ms_offset'] = ra_ms_offset.round()
        offset_info['dec_ms_offset'] = dec_ms_offset.round()

        delta_time = info.get('delta_time', 125 * u.second)

        ra_rate_rate = ra_delta_as / delta_time
        dec_rate_rate = dec_delta_as / delta_time

        ra_delta_rate = 1.0 - ((sidereal + ra_rate_rate) / sidereal)  # percentage of sidereal
        dec_delta_rate = 1.0 - ((sidereal + dec_rate_rate) / sidereal)  # percentage of sidereal
        offset_info['ra_delta_rate'] = round(ra_delta_rate.value, 4)
        offset_info['dec_delta_rate'] = round(dec_delta_rate.value, 4)

    return offset_info


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
        wcsinfo = '/var/panoptes/astrometry/bin/wcsinfo'

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
        wcsinfo = '/var/panoptes/astrometry/bin/wcs-rd2xy'

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


def get_pointing_error(fits_fname, verbose=False):
    """Gets the pointing error for the plate-solved FITS file.

    Gets the image center coordinates and compares this to the 'RA' and 'DEC' FITS
    headers in the same file. This is the difference between the target and actual.
    The separation (deg) is returned.

    Note
    ----
    Requires astrometry.net and utility scripts to be installed.

    Parameters
    ----------
    fits_fname : {str}
        Name of a FITS file that contains a WCS.

    Returns
    -------
    u.Quantity
        The degree separation of the target from the center of the image
    """
    assert os.path.exists(fits_fname), warnings.warn("No file exists at: {}".format(fits_fname))

    # Get the WCS info and the HEADER info
    wcs_info = get_wcsinfo(fits_fname)
    hdu = fits.open(fits_fname)[0]

    # Create two coordinates
    center = SkyCoord(ra=wcs_info['ra_center'], dec=wcs_info['dec_center'])
    target = SkyCoord(ra=float(hdu.header['RA']) * u.degree, dec=float(hdu.header['Dec']) * u.degree)

    if verbose:
        print("Center coords: {}".format(center))
        print("Target coords: {}".format(target))

    return center.separation(target)


def process_cr2(cr2_fname, fits_headers={}, solve=True, make_pretty=False, verbose=False, **kwargs):
    assert os.path.exists(cr2_fname), warnings.warn("File must exist: {}".format(cr2_fname))

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

        if solve:
            try:
                solve_info = get_solve_field(cr2_fname, fits_headers=fits_headers, **kwargs)
                if verbose:
                    print("Solve info: {}".format(solve_info))

                processed_info.update(solve_info)
            except error.PanError as e:
                warnings.warn("Timeout while solving: {}".format(e))
            except Exception as e:
                raise error.PanError("Can't solve field: {}".format(e))
    except Exception as e:
        warnings.warn("Problem in processing: {}".format(e))

    return processed_info


def get_pec_data(image_dir, ref_image='guide_000.new',
                 observer=None, phase_length=480,
                 skip_solved=True, verbose=False, **kwargs):

    base_dir = os.getenv('PANDIR', '/var/panoptes')

    target_name, obs_date_start = image_dir.rstrip('/').split('/', 1)

    target_dir = '{}/images/fields/{}'.format(base_dir, image_dir)

    guide_images = glob.glob('{}/guide_*.cr2'.format(target_dir))
    image_files = glob.glob('{}/1*.cr2'.format(target_dir))
    guide_images.sort()
    image_files.sort()

    # WCS Information
    ref_image = guide_images[-1]

    ref_solve_info = None

    # Solve the guide image if given a CR2
    if ref_image.endswith('cr2'):
        ref_solve_info = get_solve_field(ref_image)
        ref_image = ref_image.replace('cr2', 'new')

    # If no guide image, attempt a solve on similar fits
    if not os.path.exists(ref_image):
        if os.path.exists(ref_image.replace('new', 'fits')):
            ref_solve_info = get_solve_field(ref_image.replace('new', 'fits'))

    if verbose and ref_solve_info:
        print(ref_solve_info)

    assert os.path.exists(ref_image), warnings.warn("Ref image does not exist: {}".format(ref_image))

    ref_header = fits.getheader(ref_image)
    ref_info = get_wcsinfo(ref_image)
    if verbose:
        print(ref_image)
        print(ref_header)

    # Reference time
    t0 = Time(ref_header.get('DATE-OBS', date_parser.parse(obs_date_start))).datetime

    img_info = []
    for img in image_files:
        header_info = {}
        if not os.path.exists(img.replace('cr2', 'wcs')):
            if verbose:
                print("No WCS, solving CR2")

            header_info = get_solve_field(
                img,
                ra=ref_info['ra_center'].value,
                dec=ref_info['dec_center'].value,
                radius=10,
                **kwargs
            )

        # Get the WCS info for image
        if len(header_info) == 0:
            header_info.update(read_exif(img))
            header_info.update(get_wcsinfo(img.replace('cr2', 'wcs')))
            header_info.update(fits.getheader(img.replace('cr2', 'new')))

        hi = dict((k.lower(), v) for k, v in header_info.items())

        img_info.append(hi)

    ras = [w['ra_center'].value for w in img_info]
    decs = list([w['dec_center'].value for w in img_info])

    ras_as = [w['ra_center'].to(u.arcsec).value for w in img_info]
    decs_as = [w['dec_center'].to(u.arcsec).value for w in img_info]

    time_range = [Time(w['date-obs']) for w in img_info]

    ha = []

    if observer is not None:
        ha = np.array([observer.target_hour_angle(t, SkyCoord(ras[idx], decs[idx], unit='degree')).to(u.degree).value
                       for idx, t in enumerate(time_range)])

        ha[ha > 270] = ha[ha > 270] - 360

    # Delta time
    dt = np.diff([t.datetime.timestamp() for t in time_range])
    dt = np.insert(dt, 0, (time_range[0].datetime.timestamp() - t0.timestamp()))
    t_offset = np.cumsum(dt)

    # Diff between each exposure
    ra_diff = np.diff(ras_as)
    ra_diff = np.insert(ra_diff, 0, 0)

    dec_diff = np.diff(decs_as)
    dec_diff = np.insert(dec_diff, 0, 0)

    # Delta arcsecond
    dra_as = pd.Series(ra_diff)
    ddec_as = pd.Series(dec_diff)

    # Delta arcsecond rate
    dra_as_rate = dra_as / dt
    ddec_as_rate = ddec_as / dt

    dra_as_rate.fillna(value=0, inplace=True)
    ddec_as_rate.fillna(value=0, inplace=True)

    if verbose:
        print(type(ra_diff))
        print(type(dec_diff))
        print(type(dt))
        print(type(t_offset))
        print(type(ras))
        print(type(decs))

    table = Table({
        'dec': decs,
        'dec_as': ddec_as,
        'dec_as_rate': ddec_as_rate,
        'dt': dt,
        'ha': ha,
        'ra': ras,
        'ra_as': dra_as,
        'ra_as_rate': dra_as_rate,
        'offset': t_offset,
        'time_range': [t.mjd for t in time_range],
    }, meta={
        'name': target_name,
        'obs_date_start': obs_date_start,
    })

    table.add_index('time_range')

    table['ra'].format = '%+3.3f'
    table['ha'].format = '%+3.3f'
    table['dec'].format = '%+3.3f'
    table['dec_as_rate'].format = '%+1.5f'
    table['ra_as_rate'].format = '%+1.5f'
    table['time_range'].format = '%+5.5f'
    table['ra_as'].format = '%+2.3f'
    table['dec_as'].format = '%+3.3f'

    return table


def get_pec_fit(data, gear_period=480, with_plot=False, **kwargs):
    """
    Adapted from:
    http://stackoverflow.com/questions/16716302/how-do-i-fit-a-sine-curve-to-my-data-with-pylab-and-numpy
    """

    if with_plot:
        fig, axes = plt.subplots(nrows=2, ncols=1, sharex=True)

    for idx, key in enumerate(['as', 'as_rate']):

        ra_field = 'ra_{}'.format(key)
        dec_field = 'dec_{}'.format(key)

        guess_freq = 2
        guess_phase = 0
        guess_amplitude_ra = 3 * data[ra_field].std() / (2**0.5)
        guess_offset_ra = data[ra_field].mean()

        guess_amplitude_dec = 3 * data[dec_field].std() / (2**0.5)
        guess_offset_dec = data[dec_field].mean()

        # Initial guess parameters
        ra_p0 = [guess_freq, guess_amplitude_ra, guess_phase, guess_offset_ra]
        dec_p0 = [guess_freq, guess_amplitude_dec, guess_phase, guess_offset_dec]

        # Worm gear is a periodic sine function
        def gear_sin(x, freq, amplitude, phase, offset):
            return amplitude * np.sin(x * freq + phase) + offset

        # Fit to function
        fit_range = data['ha']
        ra_fit = curve_fit(gear_sin, fit_range, data[ra_field], p0=ra_p0)
        dec_fit = curve_fit(gear_sin, fit_range, data[dec_field], p0=dec_p0)

        smooth_range = np.linspace(fit_range.min(), fit_range.max(), 1000)
        smooth_ra_fit = gear_sin(smooth_range, *ra_fit[0])
        smooth_dec_fit = gear_sin(smooth_range, *dec_fit[0])

        if key == 'as_rate':
            smooth_ra_fit = np.gradient(smooth_ra_fit)
            smooth_dec_fit = np.gradient(smooth_dec_fit)

        ra_max = np.max(smooth_ra_fit)
        ra_min = np.min(smooth_ra_fit)

        if with_plot:
            ax = axes[idx]

            if key == 'as':
                ax.plot(fit_range, data[ra_field], 'o', color='red', alpha=0.5)

            ax.plot(smooth_range, smooth_ra_fit, label='RA Fit', color='blue')
            ax.plot(smooth_range, smooth_dec_fit, label='Dec Fit', color='green')

            ax.set_title("Peak-to-Peak: {} arcsec".format(round(ra_max - ra_min, 3)))
            ax.set_xlabel('HA')
            ax.set_ylabel('RA Offset Rate [arcsec]')
            ax.legend()

    if with_plot:
        plt.suptitle(kwargs.get('plot_title', ''))
        plt.savefig('/var/panoptes/images/{}'.format(kwargs.get('plot_name', 'pec_fit.png')))

    def fit_fn(x):
        return ra_fit[0][1] * np.sin(x * ra_fit[0][0] + ra_fit[0][2]) + ra_fit[0][3]

    return fit_fn
