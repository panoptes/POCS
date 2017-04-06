import os

import numpy as np

from astropy import units as u
from astropy import wcs
from astropy.coordinates import EarthLocation
from astropy.coordinates import FK5
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
from ccdproc import CCDData
from collections import namedtuple
from skimage.feature import register_translation
from skimage.util import view_as_blocks

from pocs import PanBase
from pocs.utils import images as img_utils

PointingError = namedtuple('PointingError', ['delta_ra', 'delta_dec', 'magnitude'])


class Image(PanBase):

    def __init__(self, fits_file, wcs_file=None):
        """Object to represent a single image from a PANOPTES camera.

        Instantiate the object by providing a .cr2 (or .dng) file.

        Args:
            fits_file (str): Name of FITS file to be read (can be .fz)
            wcs_file (str, optional): Name of FITS file to use for WCS
        """
        super().__init__()
        assert os.path.exists(fits_file), self.logger.warning('File does not exist: {}'.format(fits_file))

        if fits_file.endswith('.fz'):
            fits_file = img_utils.fpack(fits_file, unpack=True)

        assert fits_file.lower().endswith(('.fits')), self.logger.warning('File must end with .fits')

        self.wcs = None
        self._wcs_file = None
        self.fits_file = fits_file

        if wcs_file is not None:
            self.wcs_file = wcs_file
        else:
            self.wcs_file = fits_file

        with fits.open(self.fits_file, 'readonly') as hdu:
            self.header = hdu[0].header
            self.data = hdu[0].data

        assert 'DATE-OBS' in self.header, self.logger.warning('FITS file must contain the DATE-OBS keyword')
        assert 'EXPTIME' in self.header, self.logger.warning('FITS file must contain the EXPTIME keyword')

        self.RGGB = CCDData(data=self.data, unit='adu',
                            meta=self.header,
                            mask=np.zeros(self.data.shape))

        # Location Information
        cfg_loc = self.config['location']
        self.loc = EarthLocation(lat=cfg_loc['latitude'],
                                 lon=cfg_loc['longitude'],
                                 height=cfg_loc['elevation'],
                                 )
        # Time Information
        self.starttime = Time(self.header['DATE-OBS'], location=self.loc)
        self.exptime = float(self.header['EXPTIME']) * u.second
        self.midtime = self.starttime + (self.exptime / 2.0)
        self.sidereal = self.midtime.sidereal_time('apparent')
        self.FK5_Jnow = FK5(equinox=self.midtime)

        # Coordinates from header keywords
        self.header_pointing = None
        self.header_RA = None
        self.header_Dec = None
        self.header_HA = None

        # Coordinates from WCS
        self.pointing = None
        self.RA = None
        self.Dec = None
        self.HA = None

        self.get_header_pointing()
        self.get_wcs_pointing()

        self._luminance = None
        self._pointing = None
        self._pointing_error = None

    @property
    def wcs_file(self):
        """WCS file name

        When setting the WCS file name, the WCS information will be read,
        setting the `wcs` property.
        """
        return self._wcs_file

    @wcs_file.setter
    def wcs_file(self, filename):
        if filename is not None:
            try:
                w = wcs.WCS(filename)
                assert w.is_celestial

                self.wcs = w
                self._wcs_file = filename
            except Exception:
                self.logger.warn("Can't get WCS from FITS file (try solve_field)")

    @property
    def luminance(self):
        """Luminance for the image

        Bin the image 2x2 combining each RGGB set of pixels in to a single
        luminance value.
        """
        if self._luminance is None:
            block_size = (2, 2)
            image_out = view_as_blocks(self.RGGB.data, block_size)

            for i in range(len(image_out.shape) // 2):
                image_out = np.average(image_out, axis=-1)

            self._luminance = image_out

        return self._luminance

    @property
    def pointing_error(self):
        """Pointing error namedtuple (delta_ra, delta_dec, magnitude)

        Returns pointing error information. The first time this is accessed
        this will solve the field if not previously solved.

        Returns:
            namedtuple: Pointing error information
        """
        if self._pointing_error is None:
            assert self.pointing is not None, self.logger.warn("No WCS, can't get pointing_error")
            assert self.header_pointing is not None

            if self.wcs is None:
                self.solve_field()

            mag = self.pointing.separation(self.header_pointing)
            dDec = self.pointing.dec - self.header_pointing.dec
            dRA = self.pointing.ra - self.header_pointing.ra

            self._pointing_error = PointingError(dRA.to(u.degree), dDec.to(u.degree), mag)

        return self._pointing_error

    def get_header_pointing(self):
        """Get the pointing information from the header

        The header should contain the `RA-MNT` and `DEC-MNT` keywords, from which
        the header pointing coordinates are built.
        """
        try:
            self.header_pointing = SkyCoord(ra=float(self.header['RA-MNT']) * u.degree,
                                            dec=float(self.header['DEC-MNT']) * u.degree)

            self.header_RA = self.header_pointing.ra.to(u.hourangle)
            self.header_Dec = self.header_pointing.dec.to(u.degree)

            # Precess to the current equinox otherwise the RA - LST method will be off.
            self.header_HA = self.header_pointing.transform_to(self.FK5_Jnow).ra.to(u.hourangle) - self.sidereal
        except Exception as e:
            self.logger.warning('Cannot get header pointing information: {}'.format(e))

    def get_wcs_pointing(self):
        """Get the pointing information from the WCS

        Builds the pointing coordinates from the plate-solved WCS. These will be
        compared with the coordinates stored in the header.
        """
        if self.wcs is not None:
            ny, nx = self.RGGB.data.shape
            decimals = self.wcs.all_pix2world(nx // 2, ny // 2, 1)

            self.pointing = SkyCoord(ra=decimals[0] * u.degree,
                                     dec=decimals[1] * u.degree)

            self.RA = self.pointing.ra.to(u.hourangle)
            self.Dec = self.pointing.dec.to(u.degree)

            # Precess to the current equinox otherwise the RA - LST method will be off.
            self.HA = self.pointing.transform_to(self.FK5_Jnow).ra.to(u.hourangle) - self.sidereal

    def solve_field(self, **kwargs):
        """ Solve field and populate WCS information

        Args:
            **kwargs (dict): Options to be passed to `get_solve_field`
        """
        solve_info = img_utils.get_solve_field(self.fits_file,
                                               ra=self.header_pointing.ra.value,
                                               dec=self.header_pointing.dec.value,
                                               **kwargs)

        self.wcs_file = solve_info['solved_fits_file']
        self.get_wcs_pointing()

        return solve_info

    def compute_offset(self, ref, units='arcsec', rotation=True):
        """Offset information between this image and a reference

        Args:
            ref (str): Refernce image, either another `Image` instance or a
                filename that will be read
            units (str, optional): Can be either `arcsec` or `pixel`
            rotation (bool, optional): If rotation information should be included,
                defaults to True

        Returns:
            dict: Offset information in key/value pairs
        """
        if isinstance(units, (u.Unit, u.Quantity, u.IrreducibleUnit)):
            units = units.name
        assert units in ['pix', 'pixel', 'arcsec']

        if isinstance(ref, str):
            assert os.path.exists(ref)
            ref = Image(ref)
        assert isinstance(ref, Image)

        offset_pix = compute_offset_rotation(ref.luminance, self.luminance)
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

        if ref.HA:
            refHA = ref.HA
        else:
            stime_diff = (self.midtime.sidereal_time('apparent') - ref.midtime.sidereal_time('apparent'))
            refHA = selfHA - stime_diff.to(u.hourangle)

        time_diff = (self.midtime - ref.midtime)

        info = {'image': self.fits_file,
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

        try:
            info['center_dec'] = self.Dec.value
            info['center_ra'] = self.RA.value
        except Exception:
            pass

        if units in ['pix', 'pixel']:
            info['offsetX'] = offset_pix['X'].to(u.pixel).value
            info['offsetY'] = offset_pix['Y'].to(u.pixel).value
        elif units == 'arcsec':
            deltapix = [offset_pix['X'].to(u.pixel).value,
                        offset_pix['Y'].to(u.pixel).value]
            offset_deg = self.wcs.pixel_scale_matrix.dot(deltapix)
            info['offsetX'] = (offset_deg[0] * u.degree).to(u.arcsecond).value
            info['offsetY'] = (offset_deg[1] * u.degree).to(u.arcsecond).value

        return info


##################################################################################################
# Private Methods
##################################################################################################

    def __str__(self):
        return "{}: {}".format(self.fits_file, self.header_pointing)


def compute_offset_rotation(im, imref, upsample_factor=20, subframe_size=200, corners=True):
    """Determine rotation information between two images

    Detremine the rotation information for the center and, if `corner`, the
    four corner boxes, each of `subframe_size` pixels.

    Args:
        im (numpy.array): Image data
        imref (numpy.array): Comparison image data
        upsample_factor (int, optional): Subpixel fraction to compute
        subframe_size (int, optional): Box size
        corners (bool, optional): If corner boxes should be included, defaults
            to True

    Returns:
        dict: Rotation offset in `X`, `Y`, and `angle`
    """
    assert im.shape == imref.shape
    ny, nx = im.shape

    subframe_half = int(subframe_size / 2)

    # Create the center point for each of our regions
    regions = {'center': (int(nx / 2), int(ny / 2)), }
    offsets = {'center': None, }

    if corners:
        regions.update({
            'upper_right': (int(nx - subframe_half), int(ny - subframe_half)),
            'upper_left': (int(subframe_half), int(ny - subframe_half)),
            'lower_right': (int(nx - subframe_half), int(subframe_half)),
            'lower_left': (int(subframe_half), int(subframe_half)),
        })

        offsets.update({
            'upper_right': None,
            'upper_left': None,
            'lower_right': None,
            'lower_left': None,
        })

    # Get im/imref offsets for each region
    for region, midpoint in regions.items():
        imarr = img_utils.crop_data(im, center=midpoint, box_width=subframe_size)
        imrefarr = img_utils.crop_data(imref, center=midpoint, box_width=subframe_size)

        shifts, err, h = register_translation(imrefarr, imarr, upsample_factor=upsample_factor)
        offsets[region] = shifts

    # Rotate the offsets according to region
    angles = []
    for region in regions.keys():
        if region != 'center':
            offsets[region] -= offsets['center']

            relpos = (regions[region][0] - regions['center'][0],
                      regions[region][1] - regions['center'][1])

            theta1 = np.arctan(relpos[1] / relpos[0])
            theta2 = np.arctan((relpos[1] + offsets[region][1]) / (relpos[0] + offsets[region][0]))
            angles.append(theta2 - theta1)

    angle = np.mean(angles)

    result = {'X': offsets['center'][0] * u.pix,
              'Y': offsets['center'][1] * u.pix,
              'angle': (angle * u.radian).to(u.degree)}

    return result
