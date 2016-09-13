import os
import shutil
import subprocess

from dateutil import parser as date_parser
from json import loads

from warnings import warn

import numpy as np

from datetime import datetime as time

from astropy import units as u
from astropy import wcs
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
from astropy.time import TimeDelta

from ccdproc import CCDData
from ccdproc import rebin
from skimage.feature import register_translation
from skimage.util import pad
from skimage.util import view_as_blocks


from pocs import PanBase
from pocs.utils import current_time
from pocs.utils import error


class Image(PanBase):

    '''Object to represent a single image from a PANOPTES camera.

    Instantiate the object by providing a .cr2 (or .dng) file.
    '''
    def __init__(self, fitsfile, sequence=[]):
        super().__init__()
        assert os.path.exists(fitsfile)
        assert os.path.splitext(fitsfile)[1].lower() in ['.fits', '.fz']
        self.sequence = sequence
        self.fits_file = fitsfile
        self.hdulist = fits.open(self.fits_file, 'readonly')
        self.ny, self.nx = self.hdulist[0].data.shape
        self.header = self.hdulist[0].header
        self.RGGB = CCDData(data=self.hdulist[0].data, unit='adu',
                            meta=self.header,
                            mask=np.zeros(self.hdulist[0].data.shape))
        self.L = self.get_L()

        ## Location
        cfg_loc = self.config['location']
        self.loc = EarthLocation(lat=cfg_loc['latitude'],
                                 lon=cfg_loc['longitude'],
                                 height=cfg_loc['elevation'],
                                 )
        ## Time Information
        self.starttime = Time(time.strptime(self.header['DATE-OBS'],
                              '%Y-%m-%dT%H:%M:%S'), location=self.loc)
        self.exptime = TimeDelta(float(self.header['EXPTIME']), format='sec')
        self.midtime = self.starttime + self.exptime/2.0
        self.sidereal = self.midtime.sidereal_time('apparent')

        ## Green Pixels
#         self.G_mask = np.zeros(self.hdulist[0].data.shape)
#         for row in range(self.hdulist[0].data.shape[0]):
#             self.G_mask[row] = [bool((i+row%2)%2)
#                                 for i in range(self.hdulist[0].data.shape[1])]
#         self.G = rebin(CCDData(data=self.hdulist[0].data, unit='adu',
#                                meta=self.header, mask=self.G_mask),
#                                (int(self.ny/2), int(self.nx/2)))

        ## WCS
        try:
            self.header_pointing = SkyCoord(ra=float(self.header['RA-MNT'])*u.degree,
                                            dec=float(self.header['DEC-MNT'])*u.degree)
            self.header_RA = self.header_pointing.ra.to(u.hourangle)
            self.header_Dec = self.header_pointing.dec.to(u.degree)
            self.header_HA = self.header_RA - self.sidereal
        except:
            self.header_pointing = None
            self.header_RA = None
            self.header_Dec = None
            self.header_HA = None
        self.HA = None
        self.RA = None
        self.Dec = None
        self.pointing = None
        w = wcs.WCS(self.header)
        if w.is_celestial:
            self.wcs = w
        else:
            self.wcs = None

        ## See if there is a WCS file associated with the 0th Image
        self.wcsfile = None
        if self.wcs is None and len(sequence) > 1:
            wcsfile = sequence[0].replace('.cr2', '.wcs')
            if os.path.exists(wcsfile):
                try:
                    hdul = fits.open(wcsfile)
                    self.wcs = wcs.WCS(hdul[0].header)
                    self.wcsfile = wcsfile
                    self.read_pointing_from_wcs()
                    assert self.wcs.is_celestial
                except:
                    pass


    def read_pointing_from_wcs(self):
        ## Get pointing information
        if self.wcs:
            ny, nx = self.RGGB.data.shape
            decimals = self.wcs.all_pix2world([ny//2], [nx//2], 1)
            self.pointing = SkyCoord(ra=decimals[0]*u.degree,
                                     dec=decimals[1]*u.degree)
            self.RA = self.pointing.ra.to(u.hourangle)[0]
            self.Dec = self.pointing.dec.to(u.degree)[0]
            self.HA = self.RA[0] - self.sidereal


    def get_L(self):
        '''Bin the image 2x2 combining each RGGB set of pixels in to a single
        luminance value.
        '''
        block_size = (2, 2)
        image_out = view_as_blocks(self.RGGB.data, block_size)
        for i in range(len(image_out.shape) // 2):
            image_out = np.average(image_out, axis=-1)
        self.L = image_out
        return image_out


    def solve_field(self, verbose=False):
        '''Invoke the solve-field astrometry.net solver and update the WCS and
        pointing information for the Image object.
        '''
        result = get_solve_field(self.fits_file, verbose=verbose)
        ffp = os.path.dirname(os.path.abspath(self.fits_file))
        wcsfile = os.path.join(ffp, self.fits_file.replace('.fits', '.wcs'))
        if os.path.exists(wcsfile):
            try:
                hdul = fits.open(wcsfile)
                self.wcs = wcs.WCS(hdul[0].header)
                self.wcsfile = wcsfile
                self.read_pointing_from_wcs()
                assert self.wcs.is_celestial
            except:
                pass


    def get_pointing_error(self):
        if self.wcs is None:
            self.solve_field()
        if self.pointing is not None and self.header_pointing is not None:
            sep  = self.pointing.separation(self.header_pointing)
            self.pointing_error = sep[0]
            return sep[0]


    def compute_offset(self, ref, units='arcsec', rotation=True):
        if isinstance(units, (u.Unit, u.Quantity, u.IrreducibleUnit)):
            units = units.name
        assert units in ['pix', 'arcsec']
        if isinstance(ref, str):
            assert os.path.exists(ref)
            ref = Image(ref)
        assert isinstance(ref, Image)
        offset_pix = compute_offset_rotation(ref.L, self.L,
                                             rotation=rotation, upsample_factor=20)
        offset_pix['X'] *= 2
        offset_pix['Y'] *= 2

        if self.HA:
            selfHA = self.HA
        else:
            selfHA = self.header_HA
        if self.Dec:
            selfDec = self.Dec
        else:
            selfDec = self.header_Dec

        time_diff = (self.midtime-ref.midtime)
        stime_diff = (self.midtime.sidereal_time('apparent')-ref.midtime.sidereal_time('apparent'))
        if ref.HA:
            refHA = ref.HA
        else:
            refHA = selfHA - stime_diff.to(u.hourangle)

        dict = {'image': self.fits_file,
                'time': self.midtime.to_datetime().isoformat(),
                'HA': selfHA.to(u.hourangle).value,
                'HA unit': 'hours',
                'Dec': selfDec.to(u.degree).value,
                'Dec unit': 'deg',

                'refimage': ref.fits_file,
                'reftime': ref.midtime.to_datetime().isoformat(),
                'refHA': refHA.to(u.hourangle).value,

                'dt': time_diff.to(u.second).value,
                'dt unit': 'seconds',
                'angle': offset_pix['angle'].to(u.degree).value,
                'angle unit': 'deg',
                'offset units': units,
                }
        if units == 'pix':
            dict['offsetX'] = offset_pix['X'].to(u.pixel).value
            dict['offsetY'] = offset_pix['Y'].to(u.pixel).value
        elif units == 'arcsec':
            deltapix = [offset_pix['X'].to(u.pixel).value,
                        offset_pix['Y'].to(u.pixel).value]
            offset_deg = self.wcs.pixel_scale_matrix.dot(deltapix)
            dict['offsetX'] = (offset_deg[0]*u.degree).to(u.arcsecond).value
            dict['offsetY'] = (offset_deg[1]*u.degree).to(u.arcsecond).value
        return dict


    def record_tracking_errors(self):
        if len(self.sequence) >= 2:
            short = self.compute_offset(self.sequence[-2])
            self.db.insert_current('images', short)
        if len(self.sequence) >= 3:
            long = self.compute_offset(self.sequence[0])
            self.db.insert_current('images', long)


##---------------------------------------------------------------------
## Determine Offset by Cross Correlation
##---------------------------------------------------------------------
def compute_offset_rotation(im, imref, rotation=True,
                            upsample_factor=20, subframe_size=200):
    assert im.shape == imref.shape
    ny, nx = im.shape

    # regions is x0, x1, y0, y1, xcen, ycen
    regions = {'center': (int(nx/2-subframe_size/2), int(nx/2+subframe_size/2),
                          int(ny/2-subframe_size/2), int(ny/2+subframe_size/2),
                          int(nx/2), int(ny/2))}
    offsets = {'center': None}
    if rotation is True:
        regions['upper right'] = (nx-subframe_size, nx,
                                  ny-subframe_size, ny,
                                  int(nx-subframe_size/2),
                                  int(ny-subframe_size/2))
        regions['upper left'] = (0, subframe_size,
                                 ny-subframe_size, ny,
                                 int(subframe_size/2), int(ny-subframe_size/2))
        regions['lower right'] = (nx-subframe_size, nx,
                                  0, subframe_size,
                                  int(nx-subframe_size/2), int(subframe_size/2))
        regions['lower left'] = (0, subframe_size,
                                 0, subframe_size,
                                 int(subframe_size/2), int(subframe_size/2))
        offsets['upper right'] = None
        offsets['upper left'] = None
        offsets['lower right'] = None
        offsets['lower left'] = None

    for region in regions.keys():
        imarr = im[regions[region][2]:regions[region][3],
                   regions[region][0]:regions[region][1]]
        imrefarr = imref[regions[region][2]:regions[region][3],
                         regions[region][0]:regions[region][1]]
        shifts, err, h = register_translation(imrefarr, imarr,
                                              upsample_factor=upsample_factor)
        offsets[region] = shifts

    angles = []
    for region in regions.keys():
        if region != 'center':
            offsets[region] -= offsets['center']
            relpos = (regions[region][4]-regions['center'][4],
                      regions[region][5]-regions['center'][5])
            theta1 = np.arctan(relpos[1]/relpos[0])
            theta2 = np.arctan( (relpos[1]+offsets[region][1])\
                              / (relpos[0]+offsets[region][0]) )
            angles.append(theta2 - theta1)
    angle = np.mean(angles)
    result = {'X': offsets['center'][0]*u.pix,
              'Y': offsets['center'][1]*u.pix,
              'angle': (angle*u.radian).to(u.degree)}
    return result


# ---------------------------------------------------------------------
# IO Functions
# ---------------------------------------------------------------------
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
        hdu.header.set('FILTER', 'RGGB')
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


def cr2_to_pgm(cr2_fname, pgm_fname=None, dcraw='dcraw', clobber=True, **kwargs):
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



def read_exif(fname, exiftool='exiftool'):
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
        raise error.InvalidSystemCommand(msg="File: {} \n err: {}".format(fname, err))

    return exif[0]


def read_pgm(fname, byteorder='>', remove_after=False):
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

    img_type, img_size, img_max_value, _ = buffer[0:header_offset].decode().split('\n')

    assert img_type == 'P5', warn("No a PGM file")

    # Get the width and height (as strings)
    width, height = img_size.split(' ')

    data = np.flipud(np.frombuffer(buffer[header_offset:],
                                   dtype=byteorder + 'u2',
                                   ).reshape((int(height), int(width))))

    if remove_after:
        os.remove(fname)

    return data


def solve_field(fname, timeout=15, solve_opts=[], **kwargs):
    """ Plate solves an image.

    Args:
        fname(str, required):       Filename to solve in either .cr2 or .fits
                                    extension.
        timeout(int, optional):     Timeout for the solve-field command,
                                    defaults to 60 seconds.
        solve_opts(list, optional): List of options for solve-field.
        verbose(bool, optional):    Show output, defaults to False.
    """
    verbose = kwargs.get('verbose', False)
    if verbose:
        print("Entering solve_field")

    solve_field_script = "{}/scripts/solve_field.sh".format(os.getenv('POCS'), '/var/panoptes/POCS')

    if not os.path.exists(solve_field_script):
        raise error.InvalidSystemCommand("Can't find solve-field: {}".format(solve_field_script))

    # Add the options for solving the field
    if solve_opts:
        options = solve_opts
    else:
        options = [
            '--guess-scale',
            '--cpulimit', str(timeout),
            '--no-verify',
            '--no-plots',
            '--no-fits2fits',
            '--crpix-center',
            '--temp-axy',
            '--match', 'none',
            '--corr', 'none',
            '--wcs', 'none',
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

    cmd = [solve_field_script, ' '.join(options), fname]
    if verbose:
        print("Cmd: ", cmd)

    try:
        proc = subprocess.Popen(cmd, universal_newlines=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        raise error.InvalidCommand("Can't send command to solve_field.sh."\
                                   " {} \t {}".format(e, cmd))
    except ValueError as e:
        raise error.InvalidCommand("Bad parameters to solve_field."\
                                   ". {} \t {}".format(e, cmd))
    except Exception as e:
        raise error.PanError("Timeout on plate solving: {}".format(e))

    return proc


def get_solve_field(fname, **kwargs):
    """ Convenience function to wait for `solve_field` to finish.

    This function merely passes the `fname` of the image to be solved along to `solve_field`,
    which returns a subprocess.Popen object. This function then waits for that command
    to complete, populates a dictonary with the EXIF informaiton and returns. This is often
    more useful than the raw `solve_field` function

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

    # Check for solved file
    if kwargs.get('skip_solved', True) and os.path.exists(fname.replace('.fits', '.solved')):
        if verbose:
            print("Solved file exists, skipping (pass skip_solved=False to solve again): {}".format(fname))
        return {'msg': 'Solved file exists'}

    if verbose:
        print("Entering get_solve_field: {}".format(fname))

    proc = solve_field(fname, **kwargs)
    try:
        output, errs = proc.communicate(timeout=kwargs.get('timeout', 30))
    except subprocess.TimeoutExpired:
        proc.kill()
        output, errs = proc.communicate()
    else:
        try:
            if os.path.exists(fname.replace('.fits', '.new')):
                # Remove converted fits
                os.remove(fname)
                # Rename solved fits to proper extension
                os.rename(fname.replace('.fits', '.new'), fname)

            # Remove extra files
            os.remove(fname.replace('.fits', '.rdls'))
            os.remove(fname.replace('.fits', '-indx.xyls'))
        except Exception as e:
            warn('Cannot remove extra files: {}'.format(e))

    out_dict = {}

    if errs is not None:
        warn("Error in solving: {}".format(errs))
    else:
        # Read the EXIF information from the CR2
        if fname.endswith('cr2'):
            out_dict.update(read_exif(fname))
            fname = fname.replace('.cr2', '.fits')  # astrometry.net default extension
            out_dict['solved_fits_file'] = fname

        try:
            out_dict.update(fits.getheader(fname))
        except OSError:
            if verbose:
                print("Can't read fits header for {}".format(fname))

    return out_dict


def make_pretty_image(fname, timeout=15, **kwargs):
    """ Make a pretty image

    This calls out to an external script which will try to extract the JPG
    directly from the CR2 file, otherwise will do an actual conversion

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
    assert os.path.exists(fname),\
        warn("File doesn't exist, can't make pretty: {}".format(fname))

    verbose = kwargs.get('verbose', False)

    title = '{} {}'.format(kwargs.get('title', ''), current_time().isot)

    solve_field = "{}/scripts/cr2_to_jpg.sh".format(os.getenv('POCS'),
                                                    '/var/panoptes/POCS')
    cmd = [solve_field, fname, title]

    if kwargs.get('primary', False):
        cmd.append('link')

    if verbose:
        print(cmd)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        if verbose:
            print(proc)
    except OSError as e:
        raise error.InvalidCommand("Can't send command to gphoto2."
                                   " {} \t {}".format(e, cmd))
    except ValueError as e:
        raise error.InvalidCommand("Bad parameters to gphoto2."
                                   " {} \t {}".format(e, cmd))
    except Exception as e:
        raise error.PanError("Timeout on plate solving: {}".format(e))

    return fname.replace('cr2', 'jpg')


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
    assert os.path.exists(fits_fname), warn("No file exists at: {}".format(fits_fname))

    wcsinfo = shutil.which('wcsinfo')
    if wcsinfo is None:
        wcsinfo = '{}/astrometry/bin/wcsinfo'.format(os.getenv('PANDIR', default='/var/panoptes'))

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


if __name__ == '__main__':
    from glob import glob
    seq = glob('/home/joshw/test_data/*fits')
    print(seq)
    im0 = Image(seq[1], seq)

    print('Solving Astrometry')
    im0.solve_field(verbose=False)
    print(im0.pointing)
    perr = im0.get_pointing_error()
    
    im1 = Image(seq[2], seq)
    print('Solving Astrometry')
    im1.solve_field()
    print(im1.pointing)
    perr = im1.get_pointing_error()
    try:
        coord_offset = im0.pointing.separation(im1.pointing)
        print('WCS offset:', coord_offset)
    except:
        print('No WCS offset calculated')

    off1 = im0.compute_offset(im1)
    for key in off1.keys():
        print(key, off1[key])
