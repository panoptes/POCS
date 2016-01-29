import os
import re
import warnings
import subprocess
import shutil

from skimage.feature import register_translation
from astropy.io import fits
from astropy import units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord

from dateutil import parser as date_parser
import numpy as np

from .error import *
from . import PrintLog
from . import error
from . import listify

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
    title = kwargs.get('title', '')

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
            '--downsample', '4',
        ]
        if kwargs.get('clobber', True):
            options.append('--overwrite')
        if kwargs.get('skip_solved', False):
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

    if errs is not None:
        warnings.warn("Error in solving: {}".format(errs))

    out_dict = {}

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
    for line in output.split('\n'):
        for regexp in solve_re:
            matches = regexp.search(line)
            if matches:
                out_dict.update(matches.groupdict())
                if verbose:
                    print(matches.groupdict())

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
    delta_ra_as = pixel_scale * delta_ra
    out['delta_ra_as'] = delta_ra_as

    # How many milliseconds at sidereal we are off
    # (NOTE: This should be current rate, not necessarily sidearal)
    ra_ms_offset = (delta_ra_as * sidereal_rate).to(u.ms)
    out['ra_ms_offset'] = ra_ms_offset

    # Number of arcseconds we moved
    delta_dec_as = pixel_scale * delta_dec
    out['delta_dec_as'] = delta_dec_as

    # How many milliseconds at sidereal we are off
    # (NOTE: This should be current rate, not necessarily sidearal)
    dec_ms_offset = (delta_dec_as * sidereal_rate).to(u.ms)
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
        'cr2': lambda fn: read_pgm(cr2_to_pgm(fn)),
        'fits': lambda fn: fits.open(fn)[0].data,
        'pgm': lambda fn: read_pgm(fn),
    }

    file_type = fname.split('.')[-1]
    method = method_lookup.get(file_type, None)

    d = np.array([])
    if method is not None:
        d = method(fname)

    return d


def measure_offset(d0, d1, crop=True, pixel_factor=100, info={}, verbose=False):
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
    crop : {bool}, optional
        Crop the image before offseting (the default is True, which crops the data to 500x500)
    pixel_factor : {number}, optional
        Subpixel factor (the default is 100, which will give precision to 1/100th of a pixel)
    info : {dict}, optional
        Optional information about the image, such as pixel scale, rotation, etc. (the default is {})
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

    shift, error, diffphase = register_translation(d0, d1, pixel_factor)

    offset_info['shift'] = shift
    offset_info['error'] = error
    offset_info['diffphase'] = diffphase

    # self.logger.debug("Offset measured: {} {}".format(shift[0], shift[1]))

    pixel_scale = float(info.get('pixscale', 10.2859)) * (u.arcsec / u.pixel)
    # self.logger.debug("Pixel scale: {}".format(pixel_scale))

    sidereal_rate = (24 * u.hour).to(u.minute) / (360 * u.deg).to(u.arcsec)
    # self.logger.debug("Sidereal rate: {}".format(sidereal_rate))

    delta_ra, delta_dec = get_ra_dec_deltas(
        shift[0] * u.pixel, shift[1] * u.pixel,
        rotation=info.get('orientation', 0 * u.deg),
        rate=sidereal_rate,
        pixel_scale=pixel_scale,
    )
    offset_info['delta_ra'] = delta_ra
    offset_info['delta_dec'] = delta_dec
    # self.logger.debug("Δ RA/Dec [pixel]: {} {}".format(delta_ra, delta_dec))

    # Number of arcseconds we moved
    delta_ra_as = delta_ra * pixel_scale
    delta_dec_as = delta_dec * pixel_scale
    offset_info['delta_ra_as'] = delta_ra_as
    offset_info['delta_dec_as'] = delta_dec_as
    # self.logger.debug("Δ RA/Dec [arcsec]: {} / {}".format(delta_ra_as, delta_dec_as))

    # How many milliseconds at sidereal we are off
    # (NOTE: This should be current rate, not necessarily sidearal)
    ra_ms_offset = (delta_ra_as * sidereal_rate).to(u.ms)
    offset_info['ra_ms_offset'] = ra_ms_offset
    # self.logger.debug("Δ RA [ms]: {}".format(ra_ms_offset))

    # How many milliseconds at sidereal we are off
    # (NOTE: This should be current rate, not necessarily sidearal)
    dec_ms_offset = (delta_dec_as * sidereal_rate).to(u.ms)
    offset_info['dec_ms_offset'] = dec_ms_offset
    # self.logger.debug("Δ Dec [ms]: {}".format(dec_ms_offset))

    return offset_info


def crop_data(data, box_width=200, center=None):
    """ Return a cropped portion of the image

    Shape is a box centered around the middle of the data

    Args:
        data(np.array):     The original data, e.g. an image.
        box_width(int):     Size of box width in pixels, defaults to 200px
        center(tuple(int)): Crop around set of coords, defaults to image center.

    Returns:
        np.array:           A clipped (thumbnailed) version of the data
    """
    assert data.shape[0] > box_width, "Can't clip data, it's smaller than {}".format(box_width)
    # Get the center
    x_len, y_len = data.shape

    if center is None:
        x_center = int(x_len / 2)
        y_center = int(y_len / 2)
    else:
        x_center = center[0]
        y_center = center[1]

    box_width = int(box_width / 2)

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

    return wcs_info


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
            if 'object' in fits_headers:
                kwargs['title'] = "{}".format(fits_headers.get('object'))

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


@u.quantity_input
def get_ra_dec_deltas(
        dx: u.pixel,
        dy: u.pixel,
        rotation: u.deg,
        rate: (u.min / u.arcsec),
        pixel_scale: (u.arcsec / u.pixel),
        verbose=False):
    """ Given a set of x and y deltas, return RA/Dec deltas

    `dx` and `dy` represent a change in pixel coordinates (usually of a star). Given
    a certain `rate` and `pixel_scale`, this change in pixel coordinates can be expressed
    as the change in RA/Dec. Specifying `rotation` allows for coordinate transformation
    as the image rotates from up at North.

    Parameters
    ----------
    dx : {int}
        Change in pixels in x direction
    dy : {int}
        Change in pixels in y direction
    rotation : {number}, optional
        Rotation of the image (the default is 0, which is when Up on the image matches North)
    rate : {float}, optional
        The rate at which the mount is moving (the default is Sidereal rate)
    pixel_scale : {10.float}, optional
        Pixel scale of the detector used to take the image (the default is 10.2859, which is a Canon EOS 100D)
    verbose : {bool}, optional
        Print messages (the default is False, which doesn't print messages)

    Returns
    -------
    float
        Change in RA
    float
        Change in Dec
    """

    if dx == 0 and dy == 0:
        return (0 * u.pixel, 0 * u.pixel)

    # Sidereal if none
    if rate is None:
        rate = (24 * u.hour).to(u.minute) / (360 * u.deg).to(u.arcsec)

    # Canon EOS 100D
    if pixel_scale is None:
        pixel_scale = 10.2859 * (u.arcsec / u.pixel)
    elif isinstance(pixel_scale, str):
        pixel_scale = float(pixel_scale) * (u.arcsec / u.pixel)

    c = - np.sqrt(dx**2 + dy**2)

    beta = np.arcsin(dy.value / c.value)

    if hasattr(rotation, 'value'):
        rotation_rad = np.deg2rad(rotation.value)
    else:
        rotation_rad = np.deg2rad(rotation)

    alpha = (np.deg2rad(90) - rotation_rad - beta)

    east = c * np.cos(alpha)
    north = c * np.sin(alpha)

    ra = east
    dec = north

    if verbose:
        print("dx: {}".format(dx))
        print("dy: {}".format(dy))
        print("rotation: {}".format(rotation))
        print("rate: {}".format(rate))
        print("pixel_scale: {}".format(pixel_scale))
        print("c: {}".format(c))
        print("alpha: {}".format(alpha))
        print("east: {}".format(east))
        print("north: {}".format(north))

    return ra, dec
