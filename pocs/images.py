import os
import numpy as np
from datetime import datetime as time
from datetime import timedelta as dt

from astropy import units as u
from astropy import wcs
from astropy.io import fits
from skimage.feature import register_translation
from ccdproc import CCDData, rebin

class Image(object):
    def __init__(self, rawfile, sequence=[]):
        self.rawfile = rawfile
        assert os.path.exists(self.rawfile)
        assert os.path.splitext(self.rawfile)[1].lower() in ['.cr2', '.dng']
        self.sequence = sequence
        self.fits_file = cr2_to_fits(self.rawfile)
        self.hdulist = fits.open(self.fits_file, 'readonly')
        self.ny, self.nx = self.hdulist[0].data.shape
        self.header = self.hdulist[0].header
        self.CCDData = CCDData(data=self.hdulist[0].data, unit='adu',
                               meta=self.header,
                               mask=np.zeros(self.hdulist[0].data.shape))
        ## Green Pixels
        self.G_mask = np.zeros(self.hdulist[0].data.shape)
        for row in range(self.hdulist[0].data.shape[0]):
            self.G_mask[row] = [bool((i+row%2)%2)
                                for i in range(self.hdulist[0].data.shape[1])]
        self.G = rebin(CCDData(data=self.hdulist[0].data, unit='adu',
                               meta=self.header, mask=self.G_mask),
                               (int(self.ny/2), int(self.nx/2)))
        ## WCS
        w = wcs.WCS(self.header)
        if w.is_celestial:
            self.wcs = w
        else:
            self.wcs = None

        ## Time Information
        self.starttime = time.strptime(self.header['DATE-OBS'],
                                       '%Y-%m-%dT%H:%M:%S')
        self.exptime = dt(0, float(self.header['EXPTIME']))
        self.midtime = self.starttime + self.exptime/2.0

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



    def compute_offset(self, refimage, units='pix',
                       allpix=False, rotation=True):
        assert units in ['pix', 'arcsec']
        if isinstance(refimage, str):
            assert os.path,exists(refimage)
            refimage = Image(refimage)
        assert isinstance(refimage, Image)
        if allpix:
            offset_pix = compute_subframe_offset(refimage.data, self.data,
                                rotation=rotation, upsample_factor=10)
        else:
            offset_pix = compute_subframe_offset(refimage.G.data, self.G.data,
                                   rotation=rotation, upsample_factor=20)
            offset_pix['X'] *= 2
            offset_pix['Y'] *= 2

        dict = {'image': self.rawfile,
                'refimage': refimage.rawfile,
                'time0': refimage.midtime.isoformat(),
                'time1': self.midtime.isoformat(),
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




##---------------------------------------------------------------------
## Determine Offset by Cross Correlation
##---------------------------------------------------------------------
def compute_subframe_offset(im, imref, rotation=True,
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


# def crop_data(data, box_width=200, center=None, verbose=False):
#     """ Return a cropped portion of the image
# 
#     Shape is a box centered around the middle of the data
# 
#     Args:
#         data(np.array):     The original data, e.g. an image.
#         box_width(int):     Size of box width in pixels, defaults to 200px
#         center(tuple(int)): Crop around set of coords, defaults to image center.
# 
#     Returns:
#         np.array:           A clipped (thumbnailed) version of the data
#     """
#     assert data.shape[0] >= box_width, "Can't clip data, it's smaller than {} ({})".format(box_width, data.shape)
#     # Get the center
#     if verbose:
#         print("Data to crop: {}".format(data.shape))
# 
#     if center is None:
#         x_len, y_len = data.shape
#         x_center = int(x_len / 2)
#         y_center = int(y_len / 2)
#     else:
#         x_center = int(center[0])
#         y_center = int(center[1])
#         if verbose:
#             print("Using center: {} {}".format(x_center, y_center))
# 
#     box_width = int(box_width / 2)
#     if verbose:
#         print("Box width: {}".format(box_width))
# 
#     center = data[x_center - box_width: x_center + box_width, y_center - box_width: y_center + box_width]
# 
#     return center

