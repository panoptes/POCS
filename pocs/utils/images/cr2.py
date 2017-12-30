import os
import subprocess

from dateutil import parser as date_parser
from json import loads

from warnings import warn

import numpy as np

from astropy.io import fits

from pocs.utils import error


def cr2_to_fits(
        cr2_fname,
        fits_fname=None,
        clobber=False,
        headers={},
        fits_headers={},
        remove_cr2=False,
        **kwargs):  # pragma: no cover
    """ Convert a CR2 file to FITS

    This is a convenience function that first converts the CR2 to PGM via `cr2_to_pgm`.
    Also adds keyword headers to the FITS file.

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
    assert os.path.exists(cr2_fname),\
        warn("File doesn't exist, can't convert cr2 to fits: {}".format(cr2_fname))

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

        obs_date = date_parser.parse(
            exif.get('DateTimeOriginal', '').replace(':', '-', 2)).isoformat()

        # Set some default headers
        hdu.header.set('FILTER', 'RGGB')
        hdu.header.set('ISO', exif.get('ISO', ''))
        hdu.header.set('EXPTIME', exif.get('ExposureTime', 'Seconds'))
        hdu.header.set('CAMTEMP', exif.get(
            'CameraTemperature', ''), 'Celsius - From CR2')
        hdu.header.set('CIRCCONF', exif.get(
            'CircleOfConfusion', ''), 'From CR2')
        hdu.header.set('COLORTMP', exif.get(
            'ColorTempMeasured', ''), 'From CR2')
        hdu.header.set('FILENAME', exif.get('FileName', ''), 'From CR2')
        hdu.header.set('INTSN', exif.get(
            'InternalSerialNumber', ''), 'From CR2')
        hdu.header.set('CAMSN', exif.get('SerialNumber', ''), 'From CR2')
        hdu.header.set('MEASEV', exif.get('MeasuredEV', ''), 'From CR2')
        hdu.header.set('MEASEV2', exif.get('MeasuredEV2', ''), 'From CR2')
        hdu.header.set('MEASRGGB', exif.get('MeasuredRGGB', ''), 'From CR2')
        hdu.header.set('WHTLVLN', exif.get('NormalWhiteLevel', ''), 'From CR2')
        hdu.header.set('WHTLVLS', exif.get(
            'SpecularWhiteLevel', ''), 'From CR2')
        hdu.header.set('REDBAL', exif.get('RedBalance', ''), 'From CR2')
        hdu.header.set('BLUEBAL', exif.get('BlueBalance', ''), 'From CR2')
        hdu.header.set('WBRGGB', exif.get(
            'WB RGGBLevelAsShot', ''), 'From CR2')
        hdu.header.set('DATE-OBS', obs_date)

        hdu.header.set('IMAGEID', headers.get('image_id', ''))
        hdu.header.set('SEQID', headers.get('sequence_id', ''))
        hdu.header.set('FIELD', headers.get('field_name', ''))
        hdu.header.set('RA-MNT', headers.get('ra_mnt', ''), 'Degrees')
        hdu.header.set('HA-MNT', headers.get('ha_mnt', ''), 'Degrees')
        hdu.header.set('DEC-MNT', headers.get('dec_mnt', ''), 'Degrees')

        # Explicity convert the equinox for FITS header
        try:
            equinox = float(headers['equinox'].value.replace('J', ''))
        except KeyError:
            equinox = ''

        hdu.header.set('EQUINOX', equinox)

        hdu.header.set('AIRMASS', headers.get('airmass', ''), 'Sec(z)')
        hdu.header.set('FILTER', headers.get('filter', ''))
        hdu.header.set('LAT-OBS', headers.get('latitude', ''), 'Degrees')
        hdu.header.set('LONG-OBS', headers.get('longitude', ''), 'Degrees')
        hdu.header.set('ELEV-OBS', headers.get('elevation', ''), 'Meters')
        hdu.header.set('MOONSEP', headers.get(
            'moon_separation', ''), 'Degrees')
        hdu.header.set('MOONFRAC', headers.get('moon_fraction', ''))
        hdu.header.set('CREATOR', headers.get(
            'creator', ''), 'POCS Software version')
        hdu.header.set('INSTRUME', headers.get('camera_uid', ''), 'Camera ID')
        hdu.header.set('OBSERVER', headers.get(
            'observer', ''), 'PANOPTES Unit ID')
        hdu.header.set('ORIGIN', headers.get('origin', ''))
        hdu.header.set(
            'RA-RATE', headers.get('tracking_rate_ra', ''), 'RA Tracking Rate')

        if verbose:
            print("Adding provided FITS header")

        for key, value in fits_headers.items():
            try:
                hdu.header.set(key.upper()[0: 8], value)
            except Exception:
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


def cr2_to_pgm(
        cr2_fname,
        pgm_fname=None,
        dcraw='dcraw',
        clobber=True, *args,
        **kwargs):  # pragma: no cover
    """ Convert CR2 file to PGM

    Converts a raw Canon CR2 file to a netpbm PGM file via `dcraw`. Assumes
    `dcraw` is installed on the system

    Note:
        This is a blocking call

    Arguments:
        cr2_fname {str} -- Name of CR2 file to convert
        **kwargs {dict} -- Additional keywords to pass to script

    Keyword Arguments:
        pgm_fname {str} -- Name of PGM file to output, if None (default) then
                           use same name as CR2 (default: {None})
        dcraw {str} -- Path to installed `dcraw` (default: {'dcraw'})
        clobber {bool} -- A bool indicating if existing PGM should be clobbered
                         (default: {True})

    Returns:
        str -- Filename of PGM that was created

    """

    assert subprocess.call('dcraw', stdout=subprocess.PIPE),\
        "could not execute dcraw in path: {}".format(dcraw)
    assert os.path.exists(cr2_fname), "cr2 file does not exist at {}".format(
                                      cr2_fname)

    verbose = kwargs.get('verbose', False)

    if pgm_fname is None:
        pgm_fname = cr2_fname.replace('.cr2', '.pgm')

    if os.path.exists(pgm_fname) and not clobber:
        if verbose:
            print("PGM file exists, returning existing file: {}".format(
                  pgm_fname))
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
            raise error.InvalidSystemCommand(msg="File: {} \n err: {}".format(
                cr2_fname, err))

    return pgm_fname


def read_exif(fname, exiftool='exiftool'):  # pragma: no cover
    """ Read the EXIF information

    Gets the EXIF information using exiftool

    Note:
        Assumes the `exiftool` is installed

    Args:
        fname {str} -- Name of file (CR2) to read

    Keyword Args:
        exiftool {str} -- Location of exiftool (default: {'/usr/bin/exiftool'})

    Returns:
        dict -- Dictonary of EXIF information

    """
    assert os.path.exists(fname), warn("File does not exist: {}".format(fname))
    exif = {}

    try:
        # Build the command for this file
        command = '{} -j {}'.format(exiftool, fname)
        cmd_list = command.split()

        # Run the command
        exif = loads(subprocess.check_output(cmd_list).decode('utf-8'))
    except subprocess.CalledProcessError as err:
        raise error.InvalidSystemCommand(
            msg="File: {} \n err: {}".format(fname, err))

    return exif[0]


def read_pgm(fname, byteorder='>', remove_after=False):  # pragma: no cover
    """Return image data from a raw PGM file as numpy array.

    Note:
        Format Spec: http://netpbm.sourceforge.net/doc/pgm.html
        Source: http://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm

    Note:
        This is correctly processed as a Big endian even though the CR2 itself
        marks it as a Little endian. See the notes in Source page above as well
        as the comment about significant bit in the Format Spec

    Args:
        fname(str):         Filename of PGM to be converted
        byteorder(str):     Big endian
        remove_after(bool): Delete fname file after reading, defaults to False.
        clobber(bool):      Clobber existing PGM or not, defaults to True

    Returns:
        numpy.array:        The raw data from the PGMx

    """

    with open(fname, 'rb') as f:
        buffer = f.read()

    # We know our header info is 19 chars long
    header_offset = 19

    img_type, img_size, img_max_value, _ = buffer[
        0:header_offset].decode().split('\n')

    assert img_type == 'P5', warn("No a PGM file")

    # Get the width and height (as strings)
    width, height = img_size.split(' ')

    data = np.flipud(np.frombuffer(buffer[header_offset:],
                                   dtype=byteorder + 'u2',
                                   ).reshape((int(height), int(width))))

    if remove_after:
        os.remove(fname)

    return data
