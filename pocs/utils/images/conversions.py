import os
import subprocess

from astropy.io import fits
from pprint import pprint
from warnings import warn

from dateutil import parser as date_parser

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


def cr2_to_fits(cr2_fname, fits_fname=None, clobber=False, headers={}, fits_headers={}, remove_cr2=False, **kwargs):
    """ Convert a CR2 file to FITS

    This is a convenience function that first converts the CR2 to PGM via `cr2_to_pgm`. Also adds keyword headers
    to the FITS file.

    Note:
        The intermediate PGM file is automatically removed

    Arguments:
        cr2_fname {str} -- Name of CR2 file to be converted
        **kwargs {dict} -- Additional keywords to be used

    Keyword Arguments:
        fits_fname {str} -- Name of FITS file to output. If None (default), the `cr2_fname` is used
            as base (default: {None})
        clobber {bool} -- A bool indicating if existing FITS should be clobbered (default: {False})
        headers {dict} -- Header data that is filtered and added to the FITS header.
        fits_headers {dict} -- Header data that is added to the FITS header without filtering.
        remove_cr2 {bool} -- A bool indicating if the CR2 should be removed (default: {False})

    """

    verbose = kwargs.get('verbose', False)

    if fits_fname is None:
        fits_fname = cr2_fname.replace('.cr2', '.fits')

    if not os.path.exists(fits_fname) or clobber:
        if verbose:
            print("Converting CR2 to PGM: {}".format(cr2_fname))

        # Convert the CR2 to a PGM file then delete PGM
        pgm = read_pgm(cr2_to_pgm(cr2_fname), remove_after=True)

        # Add the EXIF information from the CR2 file
        exif = read_exif(cr2_fname)

        # Set the PGM as the primary data for the FITS file
        hdu = fits.PrimaryHDU(pgm)

        # Set some default headers
        hdu.header.set('ISO', exif.get('ISO', ''))
        hdu.header.set('EXPTIME', exif.get('ExposureTime', 'Seconds'))
        hdu.header.set('CAMTEMP', exif.get('CameraTemperature', ''), 'Celsius - From CR2')
        hdu.header.set('CIRCCONF', exif.get('CircleOfConfusion', ''), 'From CR2')
        hdu.header.set('COLORTMP', exif.get('ColorTempMeasured', ''), 'From CR2')
        hdu.header.set('DATE-OBS', date_parser.parse(exif.get('DateTimeOriginal', '').replace(':', '-', 2)).isoformat())
        hdu.header.set('FILENAME', exif.get('FileName', ''), 'From CR2')
        hdu.header.set('INTSN', exif.get('InternalSerialNumber', ''), 'From CR2')
        hdu.header.set('CAMSN', exif.get('SerialNumber', ''), 'From CR2')
        hdu.header.set('MEASEV', exif.get('MeasuredEV', ''), 'From CR2')
        hdu.header.set('MEASEV2', exif.get('MeasuredEV2', ''), 'From CR2')
        hdu.header.set('MEASRGGB', exif.get('MeasuredRGGB', ''), 'From CR2')
        hdu.header.set('WHTLVLN', exif.get('NormalWhiteLevel', ''), 'From CR2')
        hdu.header.set('WHTLVLS', exif.get('SpecularWhiteLevel', ''), 'From CR2')
        hdu.header.set('REDBAL', exif.get('RedBalance', ''), 'From CR2')
        hdu.header.set('BLUEBAL', exif.get('BlueBalance', ''), 'From CR2')
        hdu.header.set('WBRGGB', exif.get('WB_RGGBLevelAsShot', ''), 'From CR2')

        hdu.header.set('IMAGEID', headers.get('image_id', ''))
        hdu.header.set('SEQID', headers.get('sequence_id', ''))
        hdu.header.set('FIELD', headers.get('field_name', ''))
        hdu.header.set('RA-MNT', headers.get('ra_mnt', ''), 'Degrees')
        hdu.header.set('HA-MNT', headers.get('ha_mnt', ''), 'Degrees')
        hdu.header.set('DEC-MNT', headers.get('dec_mnt', ''), 'Degrees')
        hdu.header.set('EQUINOX', headers.get('equinox', ''))
        hdu.header.set('AIRMASS', headers.get('airmass', ''), 'Sec(z)')
        hdu.header.set('FILTER', headers.get('filter', ''))
        hdu.header.set('LAT-OBS', headers.get('latitude', ''), 'Degrees')
        hdu.header.set('LONG-OBS', headers.get('longitude', ''), 'Degrees')
        hdu.header.set('ELEV-OBS', headers.get('elevation', ''), 'Meters')
        hdu.header.set('MOONSEP', headers.get('moon_separation', ''), 'Degrees')
        hdu.header.set('MOONFRAC', headers.get('moon_fraction', ''))
        hdu.header.set('CREATOR', headers.get('creator', ''), 'POCS Software version')
        hdu.header.set('INSTRUME', headers.get('camera_uid', ''), 'Camera ID')
        hdu.header.set('OBSERVER', headers.get('observer', ''), 'PANOPTES Unit ID')
        hdu.header.set('ORIGIN', headers.get('origin', ''))

        if verbose:
            print("Adding provided FITS header")

        for key, value in fits_headers.items():
            try:
                hdu.header.set(key.upper()[0: 8], value)
            except:
                pass

        try:
            if verbose:
                print("Saving fits file to: {}".format(fits_fname))

            hdu.writeto(fits_fname, output_verify='silentfix', clobber=clobber)
        except Exception as e:
            warn("Problem writing FITS file: {}".format(e))
        else:
            if remove_cr2:
                os.unlink(cr2_fname)

    return fits_fname


def cr2_to_pgm(cr2_fname, pgm_fname=None, dcraw='/usr/bin/dcraw', clobber=True, **kwargs):
    """ Convert CR2 file to PGM

    Converts a raw Canon CR2 file to a netpbm PGM file via `dcraw`. Assumes `dcraw` is installed on the system

    Note:
        This is a blocking call

    Arguments:
        cr2_fname {str} -- Name of CR2 file to convert
        **kwargs {dict} -- Additional keywords to pass to script

    Keyword Arguments:
        pgm_fname {str} -- Name of PGM file to output, if None (default) then use same name as CR2 (default: {None})
        dcraw {str} -- Path to installed `dcraw` (default: {'/usr/bin/dcraw'})
        clobber {bool} -- A bool indicating if existing PGM should be clobbered (default: {True})

    Returns:
        str -- Filename of PGM that was created

    """
    assert os.path.exists(dcraw), "dcraw does not exist at location {}".format(dcraw)
    assert os.path.exists(cr2_fname), "cr2 file does not exist at location {}".format(cr2_fname)

    verbose = kwargs.get('verbose', False)

    if pgm_fname is None:
        pgm_fname = cr2_fname.replace('.cr2', '.pgm')

    if os.path.exists(pgm_fname) and not clobber:
        if verbose:
            print("PGM file exists and clobber=False, returning existing file: {}".format(pgm_fname))
    else:
        try:
            # Build the command for this file
            command = '{} -t 0 -D -4 {}'.format(dcraw, cr2_fname)
            cmd_list = command.split()
            if verbose:
                print("PGM Conversion command: \n {}".format(cmd_list))

            # Run the command
            if subprocess.check_call(cmd_list) == 0:
                if verbose:
                    print("PGM Conversion command successful")

        except subprocess.CalledProcessError as err:
            raise InvalidSystemCommand(msg="File: {} \n err: {}".format(cr2_fname, err))

    return pgm_fname


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
