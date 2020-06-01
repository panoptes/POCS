import os
from contextlib import suppress

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import FK5
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
from collections import namedtuple

from .base import PanBase
from panoptes.utils.images import fits as fits_utils

OffsetError = namedtuple('OffsetError', ['delta_ra', 'delta_dec', 'magnitude'])


class Image(PanBase):

    def __init__(self, fits_file, wcs_file=None, location=None, *args, **kwargs):
        """Object to represent a single image from a PANOPTES camera.

        Args:
            fits_file (str): Name of FITS file to be read (can be .fz)
            wcs_file (str, optional): Name of FITS file to use for WCS
        """
        super().__init__(*args, **kwargs)
        assert os.path.exists(fits_file), self.logger.warning('File does not exist: {fits_file}')

        file_path, file_ext = os.path.splitext(fits_file)
        assert file_ext in ['.fits', '.fz'], self.logger.warning('File must end with .fits')

        self.wcs = None
        self._wcs_file = None
        self.fits_file = fits_file

        if wcs_file is not None:
            self.wcs_file = wcs_file
        else:
            self.wcs_file = fits_file

        self.header_ext = 0
        if file_ext == '.fz':
            self.header_ext = 1

        with fits.open(self.fits_file, 'readonly') as hdu:
            self.header = hdu[self.header_ext].header

        required_headers = ['DATE-OBS', 'EXPTIME']
        for key in required_headers:
            if key not in self.header:
                raise KeyError("Missing required FITS header: {}".format(key))

        # Location Information
        if location is None:
            cfg_loc = self.get_config('location')
            location = EarthLocation(lat=cfg_loc['latitude'],
                                     lon=cfg_loc['longitude'],
                                     height=cfg_loc['elevation'],
                                     )
        # Time Information
        self.starttime = Time(self.header['DATE-OBS'], location=location)
        self.exptime = float(self.header['EXPTIME']) * u.second
        self.midtime = self.starttime + (self.exptime / 2.0)
        self.sidereal = self.midtime.sidereal_time('apparent')
        self.FK5_Jnow = FK5(equinox=self.midtime)

        # Coordinates from header keywords
        self.header_pointing = None
        self.header_ra = None
        self.header_dec = None
        self.header_ha = None

        # Coordinates from WCS
        self.pointing = None
        self.ra = None
        self.dec = None
        self.ha = None

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
            with suppress(AssertionError):
                w = fits_utils.getwcs(filename)
                assert w.is_celestial

                self.wcs = w
                self._wcs_file = filename
                self.logger.debug("WCS loaded from image")

    @property
    def pointing_error(self):
        """Pointing error namedtuple (delta_ra, delta_dec, magnitude)

        Returns pointing error information. The first time this is accessed
        this will solve the field if not previously solved.

        Returns:
            namedtuple: Pointing error information
        """
        if self._pointing_error is None:
            assert self.pointing is not None, self.logger.warning(
                "No world coordinate system (WCS), can't get pointing_error")
            assert self.header_pointing is not None

            if self.wcs is None:
                self.solve_field()

            mag = self.pointing.separation(self.header_pointing)
            d_dec = self.pointing.dec - self.header_pointing.dec
            d_ra = self.pointing.ra - self.header_pointing.ra

            self._pointing_error = OffsetError(
                d_ra.to(u.arcsec),
                d_dec.to(u.arcsec),
                mag.to(u.arcsec)
            )

        return self._pointing_error

    def get_header_pointing(self):
        """Get the pointing information from the header

        The header should contain the `RA-MNT` and `DEC-MNT` keywords, from which
        the header pointing coordinates are built.
        """
        try:
            self.header_pointing = SkyCoord(ra=float(self.header['RA-MNT']) * u.degree,
                                            dec=float(self.header['DEC-MNT']) * u.degree)

            self.header_ra = self.header_pointing.ra.to(u.degree)
            self.header_dec = self.header_pointing.dec.to(u.degree)

            try:
                self.header_ha = float(self.header['HA-MNT']) * u.hourangle
            except KeyError:
                # Compute the HA from the RA and sidereal time.
                # Precess to the current equinox otherwise the
                # RA - LST method will be off.
                # TODO(wtgee): This conversion doesn't seem to be correct.
                # wtgee: I'm not sure what I meant by the above. May 2020.
                self.header_ha = self.header_pointing.transform_to(
                    self.FK5_Jnow).ra.to(u.hourangle) - self.sidereal

        except Exception as e:
            self.logger.warning('Cannot get header pointing information: {}'.format(e))

    def get_wcs_pointing(self):
        """Get the pointing information from the WCS

        Builds the pointing coordinates from the plate-solved WCS. These will be
        compared with the coordinates stored in the header.
        """
        if self.wcs is not None:
            ra = self.wcs.celestial.wcs.crval[0]
            dec = self.wcs.celestial.wcs.crval[1]

            self.pointing = SkyCoord(ra=ra * u.degree, dec=dec * u.degree)

            self.ra = self.pointing.ra.to(u.degree)
            self.dec = self.pointing.dec.to(u.degree)

            # Precess to the current equinox otherwise the RA - LST method will be off.
            self.ha = self.pointing.transform_to(self.FK5_Jnow).ra.to(u.degree) - self.sidereal

    def solve_field(self, **kwargs):
        """ Solve field and populate WCS information.

        Args:
            **kwargs: Options to be passed to `get_solve_field`.
        """
        solve_info = fits_utils.get_solve_field(self.fits_file,
                                                ra=self.header_pointing.ra.value,
                                                dec=self.header_pointing.dec.value,
                                                **kwargs)

        self.wcs_file = solve_info['solved_fits_file']
        self.get_wcs_pointing()

        # Remove some fields
        for header in ['COMMENT', 'HISTORY']:
            with suppress(KeyError):
                del solve_info[header]

        return solve_info

    def compute_offset(self, ref_image):
        assert isinstance(ref_image, Image), self.logger.warning(
            "Must pass an Image class for reference")

        mag = self.pointing.separation(ref_image.pointing)
        d_dec = self.pointing.dec - ref_image.pointing.dec
        d_ra = self.pointing.ra - ref_image.pointing.ra

        return OffsetError(d_ra.to(u.arcsec), d_dec.to(u.arcsec), mag.to(u.arcsec))

    def __str__(self):
        return f"{self.fits_file}: {self.header_pointing}"
