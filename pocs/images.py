import os
import subprocess
from json import loads
from dateutil import parser as date_parser

import numpy as np
from numpy import ma
from datetime import datetime as time
from datetime import timedelta as dt

from astropy import units as u
from astropy import wcs
from astropy.io import fits
from astropy.coordinates import SkyCoord, EarthLocation
from astropy.time import Time, TimeDelta

from skimage.feature import register_translation
from ccdproc import CCDData, rebin

from pocs.utils.database import PanMongo
from pocs.utils.config import load_config as pocs_config

class Image(object):
    '''Object to represent a single image from a PANOPTES camera.
    
    Instantiate the object by providing a .cr2 (or .dng) file.  
    '''
    def __init__(self, rawfile, sequence=[]):
        self.rawfile = rawfile
        assert os.path.exists(self.rawfile)
        assert os.path.splitext(self.rawfile)[1].lower() in ['.cr2', '.dng']
        self.sequence = sequence
        self.fits_file = cr2_to_fits(self.rawfile)
        self.hdulist = fits.open(self.fits_file, 'readonly')
        self.ny, self.nx = self.hdulist[0].data.shape
        self.header = self.hdulist[0].header
        self.RGGB = CCDData(data=self.hdulist[0].data, unit='adu',
                            meta=self.header,
                            mask=np.zeros(self.hdulist[0].data.shape))
        self.L = self.get_L()
        ## Green Pixels
#         self.G_mask = np.zeros(self.hdulist[0].data.shape)
#         for row in range(self.hdulist[0].data.shape[0]):
#             self.G_mask[row] = [bool((i+row%2)%2)
#                                 for i in range(self.hdulist[0].data.shape[1])]
#         self.G = rebin(CCDData(data=self.hdulist[0].data, unit='adu',
#                                meta=self.header, mask=self.G_mask),
#                                (int(self.ny/2), int(self.nx/2)))
        ## WCS
        w = wcs.WCS(self.header)
        if w.is_celestial:
            self.wcs = w
        else:
            self.wcs = None

        ## Location
        cfg_loc = pocs_config()['location']
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

        ## See if there is a WCS file associated with the 0th Image
        self.wcsfile = None
        if self.wcs is None and len(sequence) > 1:
            wcsfile = sequence[0].replace('.cr2', '.wcs')
            if os.path.exists(wcsfile):
                try:
                    hdul = fits.open(wcsfile)
                    self.wcs= wcs.WCS(hdul[0].header)
                    self.wcsfile = wcsfile
                    assert self.wcs.is_celestial
                except:
                    pass

        ## Get pointing information
        self.HA = None
        self.RA = None
        self.Dec = None
        self.pointing = None
        if self.wcs:
            ny, nx = self.RGGB.data.shape
            decimals = self.wcs.all_pix2world(ny//2, nx//2, 1)
            self.pointing = SkyCoord(ra=decimals[0]*u.degree, dec=decimals[1]*u.degree)
            self.RA = self.pointing.ra.to(u.hourangle)
            self.Dec = self.pointing.dec.to(u.degree)
            self.HA = self.RA - self.sidereal


    def get_L(self):
        '''Bin the image 2x2 combining each RGGB set of pixels in to a single
        luminance value.
        '''
        from skimage.util import view_as_blocks, pad
        block_size = (2,2)
        image_out = view_as_blocks(self.RGGB.data, block_size)
        for i in range(len(image_out.shape) // 2):
            image_out = np.average(image_out, axis=-1)
        self.L = image_out
        return image_out


    def solve_field(self):
        '''Invoke the solve-field astrometry.net solver and update the WCS and
        pointing information for the Image object.
        '''
        result = get_solve_field(self.fits_file)
        print(result)


    def get_pointing_error(self):
        


    def compute_offset(self, ref, units='arcsec', rotation=True):
        assert units in ['pix', 'arcsec']
        if isinstance(ref, str):
            assert os.path.exists(ref)
            ref = Image(ref)
        assert isinstance(ref, Image)
        offset_pix = compute_offset_rotation(ref.L, self.L,
                               rotation=rotation, upsample_factor=20)
        offset_pix['X'] *= 2
        offset_pix['Y'] *= 2

        dict = {'image': self.rawfile,
                'time': self.midtime.isoformat(),
                'HA': self.HA.to(u.hourangle).value,
                'Dec': self.HA.to(u.degree).value,

                'refimage': refimage.rawfile,
                'reftime': refimage.midtime.isoformat(),
                'refHA': refimage.HA.to(u.hourangle).value,

                'dt': (self.midtime-refimage.midtime).total_seconds(),
                'units': units,
                'angle': offset_pix['angle'].to(u.degree).value,
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
        db = PanMongo()
        if len(self.sequence) >= 2:
            short = self.compute_offset(self.sequence[-2])
            db.insert_current('images', short)
        if len(self.sequence) >= 3:
            long = self.compute_offset(self.sequence[0])
            db.insert_current('images', long)


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
                                  int(nx-subframe_size/2), int(ny-subframe_size/2))
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
            relpos = (regions[region][4]-regions['center'][4], regions[region][5]-regions['center'][5])
            theta1 = np.arctan(relpos[1]/relpos[0])
            theta2 = np.arctan((relpos[1]+offsets[region][1])/(relpos[0]+offsets[region][0]))
            angles.append(theta2 - theta1)
    angle = np.mean(angles)
    result = {'X': offsets['center'][0]*u.pix,
              'Y': offsets['center'][1]*u.pix,
              'angle': (angle*u.radian).to(u.degree)}
    return result



##---------------------------------------------------------------------
## IO Functions
##---------------------------------------------------------------------
def cr2_to_fits(cr2_fname, fits_fname=None, clobber=False, fits_headers={}, remove_cr2=False, **kwargs):
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
        fits_headers {dict} -- Header values to be saved with the FITS, by default includes the EXIF
            info from the CR2 (default: {{}})
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
        hdu.header.set('EXPTIME', exif.get('ExposureTime', ''))
        hdu.header.set('CAMTEMP', exif.get('CameraTemperature', ''))
        hdu.header.set('CIRCCONF', exif.get('CircleOfConfusion', ''))
        hdu.header.set('COLORTMP', exif.get('ColorTempMeasured', ''))
        hdu.header.set('DATE-OBS', date_parser.parse(exif.get('DateTimeOriginal', '')).isoformat())
        hdu.header.set('FILENAME', exif.get('FileName', ''))
        hdu.header.set('INTSN', exif.get('InternalSerialNumber', ''))
        hdu.header.set('CAMSN', exif.get('SerialNumber', ''))
        hdu.header.set('MEASEV', exif.get('MeasuredEV', ''))
        hdu.header.set('MEASEV2', exif.get('MeasuredEV2', ''))
        hdu.header.set('MEASRGGB', exif.get('MeasuredRGGB', ''))
        hdu.header.set('WHTLVLN', exif.get('NormalWhiteLevel', ''))
        hdu.header.set('WHTLVLS', exif.get('SpecularWhiteLevel', ''))
        hdu.header.set('REDBAL', exif.get('RedBalance', ''))
        hdu.header.set('BLUEBAL', exif.get('BlueBalance', ''))
        hdu.header.set('WBRGGB', exif.get('WB_RGGBLevelAsShot', ''))

        if verbose:
            print("Adding provided FITS header")

        for key, value in fits_headers.items():
            try:
                hdu.header.set(key.upper()[0: 8], "{}".format(value))
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

    Converts a raw Canon CR2 file to a netpbm PGM file via `dcraw`. Assumes `dcraw` is installed on the system

    Note:
        This is a blocking call

    Arguments:
        cr2_fname {str} -- Name of CR2 file to convert
        **kwargs {dict} -- Additional keywords to pass to script

    Keyword Arguments:
        pgm_fname {str} -- Name of PGM file to output, if None (default) then use same name as CR2 (default: {None})
        dcraw {str} -- Path to installed `dcraw` (default: {'dcraw'})
        clobber {bool} -- A bool indicating if existing PGM should be clobbered (default: {True})

    Returns:
        str -- Filename of PGM that was created

    """
    
    assert subprocess.call('dcraw', stdout=subprocess.PIPE), "could not execute dcraw in path: {}".format(dcraw)
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



def read_exif(fname, exiftool='exiftool'):
    """ Read the EXIF information

    Gets the EXIF information using exiftool

    Note:
        Assumes the `exiftool` is installed

    Arguments:
        fname {str} -- Name of file (CR2) to read

    Keyword Arguments:
        exiftool {str} -- Location of exiftool (default: {'exiftool'})

    Returns:
        dict -- Dictonary of EXIF information

    """
#     assert subprocess.call(exiftool, stdout=subprocess.PIPE), "could not execute exiftool in path: {}".format(exiftool)
    assert fname is not None
    exif = {}

    # Build the command for this file
    command = '{} -j {}'.format(exiftool, fname)
    cmd_list = command.split()

    try:
        # Run the command
        output = subprocess.check_output(cmd_list)
        exif = loads(output.decode('utf-8'))
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
        fname(str, required):       Filename to solve in either .cr2 or .fits extension.
        timeout(int, optional):     Timeout for the solve-field command, defaults to 60 seconds.
        solve_opts(list, optional): List of options for solve-field.
        verbose(bool, optional):    Show output, defaults to False.
    """
    verbose = kwargs.get('verbose', False)
    if verbose:
        print("Entering solve_field")

    solve_field_script = "{}/scripts/solve_field.sh".format(os.getenv('POCS'))

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

    cmd = [solve_field_script, ' '.join(options), fname]
    if verbose:
        print("Cmd: ", cmd)

    try:
        proc = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        raise error.InvalidCommand("Can't send command to solve_field.sh. {} \t {}".format(e, cmd))
    except ValueError as e:
        raise error.InvalidCommand("Bad parameters to solve_field.sh. {} \t {}".format(e, cmd))
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
    if verbose:
        print("Entering get_solve_field")

    proc = solve_field(fname, **kwargs)
    try:
        output, errs = proc.communicate(timeout=kwargs.get('timeout', 30))
    except subprocess.TimeoutExpired:
        proc.kill()
        output, errs = proc.communicate()

    out_dict = {}

    if errs is not None:
        warn("Error in solving: {}".format(errs))
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

    return out_dict


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
