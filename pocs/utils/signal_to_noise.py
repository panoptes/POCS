from pocs.utils.config import load_config

import math
import os

import numpy as np
from scipy.interpolate import interp1d
from matplotlib import pyplot as plt

from astropy import constants as c
from astropy import units as u
from astropy.convolution import discretize_model
from astropy.modeling import Fittable2DModel
from astropy.modeling.functional_models import Moffat2D
from astropy.table import Table


def create_imagers(config=None):
    """ Parse performance data config and create a corresponding dictionary of Imager objects.

    Args:
        config (optional): a dictionary containing the performance data configuration. If not specified `load_config()``
            will be used to attempt to load a `performance.yaml` and/or `performance_local.yaml` file and use the
            resulting config.

    Returns:
        dict: dictionary of Imager objects.
    """

    if config is None:
        config = load_config('performance')

    optics = dict()
    cameras = dict()
    filters = dict()
    psfs = dict()
    imagers = dict()

    # Setup imagers
    for name, imager_info in config['imagers'].items():
        optic_name = imager_info['optic']
        try:
            # Try to get from cache
            optic = optics[optic_name]
        except KeyError:
            # Create optic from this imager
            optic_info = config['optics'][optic_name]
            optic = Optic(**optic_info)

            # Put in cache
            optics[optic_name] = optic
            camera_name = imager_info['camera']
        try:
            # Try to get from cache
            camera = cameras[camera_name]
        except KeyError:
            # Create camera for this imager
            camera_info = config['cameras'][camera_name]
            if type(camera_info['resolution']) == str:
                camera_info['resolution'] = [int(a) for a in camera_info['resolution'].split(',')]
            camera = Camera(**camera_info)

            # Put in cache
            cameras[camera_name] = camera

        filter_name = imager_info['filter']
        try:
            # Try to get from cache
            band = filters[filter_name]
        except KeyError:
            # Create optic from this imager
            filter_info = config['filters'][filter_name]
            band = Filter(**filter_info)

            # Put in cache
            filters[filter_name] = band

        psf_name = imager_info['psf']
        # Don't cache these as their attributes get modified by the Imager they're associated with so
        # each Imager should get a new instance.
        psf_info = config['psfs'][psf_name]
        assert issubclass(globals()[psf_info['model']], PSF)
        psf = globals()[psf_info['model']](**psf_info)

        imagers[name] = Imager(optic,
                               camera,
                               band,
                               psf,
                               imager_info.get('num_imagers', 1),
                               imager_info.get('num_per_computer', 1))
    return imagers


def ensure_unit(arg, unit):
    """Ensures that the argument is using the required unit"""
    if not isinstance(arg, u.Quantity):
        arg = arg * unit
    return arg.to(unit)


class Optic:

    def __init__(self, aperture, focal_length, throughput_filename, central_obstruction=0 * u.mm):
        """ Class representing the overall optical system (e.g. a telescope, including any field flattener, focal
        reducer or reimaging optics). The Filter class should be used for optical filters.

        Args:
            aperture (Quantity): diameter of the entrance pupil
            focal_length (Quantity): effective focal length
            throughput_filename (string): name of file containing optical throughput as a function of wavelength data.
                Must be in a format readable by `astropy.table.Table.read()` and use column names `Wavelength` and
                `Throughput`. If the data file does not provide units nm and dimensionless unscaled are assumed.
            central_obstruction (Quantity, optional): diameter of the central obstruction of the entrance pupil, if any.
        """

        self.aperture = ensure_unit(aperture, u.mm)
        self.central_obstruction = ensure_unit(central_obstruction, u.mm)

        self.aperture_area = np.pi * (self.aperture**2 - self.central_obstruction**2).to(u.m**2) / 4

        self.focal_length = ensure_unit(focal_length, u.mm)

        tau_data = Table.read(os.path.join(os.getenv('POCS'), throughput_filename))

        if not tau_data['Wavelength'].unit:
            tau_data['Wavelength'].unit = u.nm
        self.wavelengths = tau_data['Wavelength'].quantity.to(u.nm)

        if not tau_data['Throughput'].unit:
            tau_data['Throughput'].unit = u.dimensionless_unscaled
        self.throughput = tau_data['Throughput'].quantity.to(u.dimensionless_unscaled)


class Camera:

    def __init__(self, bit_depth, full_well, gain, bias, readout_time, pixel_size, resolution, read_noise,
                 dark_current, QE_filename, minimum_exposure):
        """Class representing a camera, which in this case means the image sensor, associated electronics, shutter,
        etc., but does not include any of the optical components of the system.

        Args:
            bit_depth (int): bits per pixel used by the camera analogue to digital converters
            full_well (Quantity): number of photo-electrons each pixel can receive before saturating
            gain (Quantity): number of photo-electrons corresponding to one ADU in the digital data
            bias (Quantity): bias level of image sensor, in ADU / pixel units. Used when determining saturation level.
            readout_time (Quantity): time required to read the data from the image sensor
            pixel_size (Quantity): pixel pitch
            resolution (Quantity): number of pixels across the image sensor in both horizontal & vertical directions
            read_noise (Quantity): intrinsic noise of image sensor and readout electronics, in electrons/pixel units
            dark_current (Quantity): rate of accumlation of dark signal, in electrons/second/pixel units
            QE_filename (string): name of a file containing quantum efficieny as a function of wavelength data. Must
                be in a format readable by `astropy.table.Table.read()` and use column names `Wavelength` and `QE`.
                If the data file does not provide units nm and dimensionless unscaled will be assumed.
            minimum_exposure (Quantity): length of the shortest exposure that the camera is able to take.
        """

        self.bit_depth = int(bit_depth)
        self.full_well = ensure_unit(full_well, u.electron / u.pixel)
        self.gain = ensure_unit(gain, u.electron / u.adu)
        self.bias = ensure_unit(bias, u.adu / u.pixel)
        self.readout_time = ensure_unit(readout_time, u.second)
        self.pixel_size = ensure_unit(pixel_size, u.micron / u.pixel)
        self.resolution = ensure_unit(resolution, u.pixel)
        self.read_noise = ensure_unit(read_noise, u.electron / u.pixel)
        self.dark_current = ensure_unit(dark_current, u.electron / (u.second * u.pixel))
        self.minimum_exposure = ensure_unit(minimum_exposure, u.second)

        # Calculate a saturation level corresponding to the lower of the 'analogue' (full well) and 'digital'
        # (ADC) limit, in electrons.
        self.saturation_level = min(self.full_well, ((2**self.bit_depth - 1) * u.adu / u.pixel - self.bias) * self.gain)

        # Calculate the noise at the saturation level
        self.max_noise = (self.saturation_level * u.electron / u.pixel + self.read_noise**2)**0.5

        QE_data = Table.read(os.path.join(os.getenv('POCS'), QE_filename))

        if not QE_data['Wavelength'].unit:
            QE_data['Wavelength'].unit = u.nm
        self.wavelengths = QE_data['Wavelength'].quantity.to(u.nm)

        if not QE_data['QE'].unit:
            QE_data['QE'].unit = u.electron / u.photon
        self.QE = QE_data['QE'].quantity.to(u.electron / u.photon)


class Filter:

    def __init__(self, transmission_filename, sky_mu):
        """Class representing an optical bandpass filter

        Args:
            transmission_filename (string): name of file containing transmission as a function of wavelength data. Must
            be in a format readable by `astropy.table.Table.read()` and use column names `Wavelength` and
            `Transmission`. If the data file does not provide units nm and dimensionless unscaled will be assumed.
            sky_mu (Quantity): the sky background surface brightness per arcsecond^2 (in ABmag units) for the band.
        """

        transmission_data = Table.read(os.path.join(os.getenv('POCS'), transmission_filename))

        if not transmission_data['Wavelength'].unit:
            transmission_data['Wavelength'].unit = u.nm
        self.wavelengths = transmission_data['Wavelength'].quantity.to(u.nm)

        if not transmission_data['Transmission'].unit:
            transmission_data['Transmission'].unit = u.dimensionless_unscaled
        self.transmission = transmission_data['Transmission'].quantity.to(u.dimensionless_unscaled)

        self.sky_mu = ensure_unit(sky_mu, u.ABmag)


class PSF(Fittable2DModel):

    def __init__(self, FWHM, pixel_scale=None, **kwargs):
        """
        Abstract base class representing a 2D point spread function.

        Used to calculate pixelated version of the PSF and associated parameters useful for
        point source signal to noise and saturation limit calculations.

        Args:
            FWHM (Quantity): Full Width at Half-Maximum of the PSF in angle on the sky units
            pixel_scale (Quantity, optional): pixel scale (angle/pixel) to use when calculating pixellated point
                spread functions or related parameters. Does not need to be set on object creation but must be set
                before before pixellation function can be used.
        """
        self._FWHM = ensure_unit(FWHM, u.arcsecond)

        if pixel_scale:
            self.pixel_scale = pixel_scale

        super().__init__(**kwargs)

    @property
    def FWHM(self):
        return self._FWHM

    @FWHM.setter
    def FWHM(self, FWHM):
        self._FWHM = ensure_unit(FWHM, u.arcsecond)
        # If a pixel scale has already been set should update model parameters when FWHM changes.
        if self.pixel_scale:
            self._update_model()

    @property
    def pixel_scale(self):
        try:
            return self._pixel_scale
        except AttributeError:
            return None

    @pixel_scale.setter
    def pixel_scale(self, pixel_scale):
        self._pixel_scale = ensure_unit(pixel_scale, (u.arcsecond / u.pixel))
        # When pixel scale is set/changed need to update model parameters:
        self._update_model()

    @property
    def n_pix(self):
        try:
            return self._n_pix
        except AttributeError:
            return None

    @property
    def peak(self):
        try:
            return self._peak
        except AttributeError:
            return None

    def pixellated(self, pixel_scale=None, size=21, offsets=(0.0, 0.0)):
        """
        Calculates a pixellated version of the PSF for a given pixel scale
        """
        if not pixel_scale:
            pixel_scale = self.pixel_scale

        # Update PSF centre coordinates
        self.x_0 = offsets[0]
        self.y_0 = offsets[1]

        xrange = (-(size - 1) / 2, (size + 1) / 2)
        yrange = (-(size - 1) / 2, (size + 1) / 2)

        return discretize_model(self, xrange, yrange, mode='oversample', factor=10)

    def _get_peak(self, pixel_scale=None):
        """
        Calculate the peak pixel value (as a fraction of total counts) for a PSF centred
        on a pixel. This is useful for calculating saturation limits for point sources.
        """
        # Odd number of pixels (1) so offsets = (0, 0) is centred on a pixel
        centred_psf = self.pixellated(pixel_scale, 1, offsets=(0, 0))
        return centred_psf[0, 0] / u.pixel

    def _get_n_pix(self, pixel_scale=None, size=20):
        """
        Calculate the effective number of pixels for PSF fitting photometry with this
        PSF, in the worse case where the PSF is centred on the corner of a pixel.
        """
        # Want a even number of pixels.
        size = size + size % 2
        # Even number of pixels so offsets = (0, 0) is centred on pixel corners
        corner_psf = self.pixellated(pixel_scale, size, offsets=(0, 0))
        return 1 / ((corner_psf**2).sum()) * u.pixel

    def _update_model(self):
        raise NotImplementedError


class Moffat_PSF(PSF, Moffat2D):

    def __init__(self, model=None, shape=2.5, **kwargs):
        """
        Class representing a 2D Moffat profile point spread function.

        Used to calculate pixelated version of the PSF and associated parameters useful for
        point source signal to noise and saturation limit calculations.

        Args:
            FWHM (Quantity): Full Width at Half-Maximum of the PSF in angle on the sky units
            shape (optional, default 2.5): shape parameter of the Moffat function, must be > 1
            pixel_scale (Quantity, optional): pixel scale (angle/pixel) to use when calculating pixellated point
                spread functions or related parameters. Does not need to be set on object creation but must be set
                before before pixellation function can be used.

        Smaller values of the shape parameter correspond to 'wingier' profiles.
        A value of 4.765 would give the best fit to pure Kolmogorov atmospheric turbulence.
        When instrumental effects are added a lower value is appropriate.
        IRAF uses a default of 2.5.
        """
        if shape <= 1.0:
            raise ValueError('shape must be greater than 1!')

        super().__init__(alpha=shape, **kwargs)

    @property
    def shape(self):
        return self.alpha

    @shape.setter
    def shape(self, alpha):
        if shape <= 1.0:
            raise ValueError('shape must be greater than 1!')

        self.alpha = alpha
        # If a pixel scale has already been set should update model parameters when alpha changes.
        if self.pixel_scale:
            self._update_model()

    def _update_model(self):
        # Convert FWHM from arcsecond to pixel units
        self._FWHM_pix = self.FWHM / self.pixel_scale
        # Convert to FWHM to Moffat profile width parameter in pixel units
        gamma = self._FWHM_pix / (2 * np.sqrt(2**(1 / self.alpha) - 1))
        # Calculate amplitude required for normalised PSF
        amplitude = (self.alpha - 1) / (np.pi * gamma**2)
        # Update model parameters
        self.gamma = gamma.to(u.pixel).value
        self.amplitude = amplitude.to(u.pixel**-2).value

        self._n_pix = self._get_n_pix()
        self._peak = self._get_peak()


class Imager:

    def __init__(self, optic, camera, band, psf, num_imagers=1, num_per_computer=1):
        """
        Class representing an astronomical imaging system, including optics, optical filters and camera. Also includes
        a point spread function (PSF) model. It can also be used to represent an array of identical co-aligned imagers
        using the optional `num_imagers` parameter to specify the number of copies whose data will be combined.

        Args:
            optic: An instance of the Optic class
            camera: An instance of the Camera class
            band: An instance of the bandpass Filter class
            psf: An instance of the PSF class
            num_imagers (int, optional): to represent an array of identical, co-aligned imagers specify the number here
            num_per_computer (int, optional): number of cameras connected to each computer. Used in situations where
                multiple cameras must be readout sequentially so the effective readout time is equal to the readout
                time of a single camera multiplied by the number of cameras. This is the case for SBIG cameras.
        """

        if not isinstance(optic, Optic):
            raise ValueError("optic must be an instance of the Optic class")
        if not isinstance(camera, Camera):
            raise ValueError("camera must be an instance of the Camera class")
        if not isinstance(band, Filter):
            raise ValueError("band must be an instance of the Filter class")
        if not isinstance(psf, PSF):
            raise ValueError("psf must be an instance of the PSF class")

        self.optic = optic
        self.camera = camera
        self.band = band
        self.psf = psf
        self.num_imagers = int(num_imagers)
        self.num_per_computer = int(num_per_computer)

        # Calculate pixel scale, area
        self.pixel_scale = (self.camera.pixel_size / self.optic.focal_length)
        self.pixel_scale = self.pixel_scale.to(u.arcsecond / u.pixel,
                                               equivalencies=u.equivalencies.dimensionless_angles())
        self.pixel_area = self.pixel_scale**2 * u.pixel  # arcsecond^2 / pixel
        self.psf.pixel_scale = self.pixel_scale

        # Calculate field of view.
        self.field_of_view = (self.camera.resolution * self.pixel_scale)
        self.field_of_view = self.field_of_view.to(u.degree, equivalencies=u.dimensionless_angles())

        # Calculate end to end efficiencies, etc.
        self._efficiencies()

        # Calculate sky count rate for later use
        self.sky_rate = self.SB_to_rate(self.band.sky_mu)

    def extended_source_signal_noise(self, surface_brightness, total_exp_time, sub_exp_time, calc_type='per pixel',
                                     saturation_check=True, binning=1):
        """Calculates the signal and noise for an extended source with given surface brightness

        Args:
            surface_brightness (Quantity): surface brightness per arcsecond^2 of the source, in ABmag units, or
                an equivalent count rate in photo-electrons per second per pixel.
            total_exp_time (Quantity): total length of all sub-exposures. If necessary will be rounded up to integer
                multiple of sub_exp_time
            sub_exp_time (Quantity): length of individual sub-exposures
            calc_type (string, optional, default 'per pixel'): calculation type, 'per pixel' to calculate signal & noise
                per pixel, 'per arcsecond squared' to calculate signal & noise per arcsecond^2
            saturation_check (bool, optional, default True): if true will set both signal and noise to zero if the
                electrons per pixel in a single sub-exposure exceed the saturation level.
            binning (int, optional): pixel binning factor. Cannot be used with calculation type 'per arcsecond squared'

        Returns:
            (Quantity, Quantity): signal and noise, units determined by calculation type.
        """

        if calc_type not in ('per pixel', 'per arcsecond squared'):
            raise ValueError("Invalid calculation type '{}'!".format(calc_type))

        if calc_type == 'per arcsecond squared' and binning != 1:
            raise ValueError("Cannot specify pixel binning with calculation type 'per arcsecond squared'!")

        if not isinstance(surface_brightness, u.Quantity):
            surface_brightness = surface_brightness * u.ABmag

        try:
            # If surface brightness is a count rate this should work
            rate = surface_brightness.to(u.electron / (u.pixel * u.second))
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have surface brightness in ABmag, call conversion function
            rate = self.SB_to_rate(surface_brightness)

        total_exp_time = ensure_unit(total_exp_time, u.second)
        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        # Round total exposure time to an integer number of sub exposures. One or both of total_exp_time or
        # sub_exp_time may be Quantity arrays, need np.ceil
        number_subs = np.ceil(total_exp_time / sub_exp_time)
        total_exp_time = number_subs * sub_exp_time

        # Noise sources (per pixel for single imager)
        signal = (rate * total_exp_time).to(u.electron / u.pixel)
        sky_counts = self.sky_rate * total_exp_time
        dark_counts = self.camera.dark_current * total_exp_time
        total_read_noise = number_subs**0.5 * self.camera.read_noise

        noise = ((signal + sky_counts + dark_counts) * (u.electron / u.pixel) + total_read_noise**2)**0.5
        noise = noise.to(u.electron / u.pixel)

        # Saturation check
        if saturation_check:
            saturated = self._is_saturated(rate, sub_exp_time)
            # np.where strips units, need to manually put them back.
            signal = np.where(saturated, 0, signal) * u.electron / u.pixel
            noise = np.where(saturated, 0, noise) * u.electron / u.pixel

        # Totals per (binned) pixel for all imagers.
        signal = signal * self.num_imagers * binning
        noise = noise * (self.num_imagers * binning)**0.5

        # Optionally convert to totals per arcsecond squared.
        if calc_type == 'per arsecond squared':
            signal = signal / self.pixel_area  # e/arcseconds^2
            noise = noise / (self.pixel_scale * u.arcsecond)  # e/arcseconds^2

        return signal, noise

    def extended_source_snr(self, surface_brightness, total_exp_time, sub_exp_time, calc_type='per pixel',
                            saturation_check=True, binning=1):
        """ Calculates the signal and noise for an extended source with given surface brightness

        Args:
            surface_brightness (Quantity): surface brightness per arcsecond^2 of the source, in ABmag units, or
                an equivalent count rate in photo-electrons per second per pixel.
            total_exp_time (Quantity): total length of all sub-exposures. If necessary will be rounded up to integer
                multiple of sub_exp_time
            sub_exp_time (Quantity): length of individual sub-exposures
            calc_type (string, optional, default 'per pixel'): calculation type, 'per pixel' to calculate signal & noise
                per pixel, 'per arcsecond squared' to calculate signal & noise per arcsecond^2
            saturation_check (bool, optional, default True): if true will set the signal to noise ratio to zero if the
                electrons per pixel in a single sub-exposure exceed the saturation level.
            binning (int, optional): pixel binning factor. Cannot be used with calculation type 'per arcsecond squared'

        Returns:
            Quantity: signal to noise ratio, Quantity with dimensionless unscaled units
        """
        signal, noise = self.extended_source_signal_noise(surface_brightness, total_exp_time, sub_exp_time, calc_type,
                                                          saturation_check, binning)

        # np.where() strips units, need to manually put them back
        snr = np.where(noise != 0.0, signal / noise, 0.0) * u.dimensionless_unscaled

        return snr

    def extended_source_etc(self, surface_brightness, snr_target, sub_exp_time, calc_type='per pixel',
                            saturation_check=True, binning=1):
        """Calculates the total exposure time required to reach a given signal to noise ratio for a given extended
        source surface brightness.

        Args:
            surface_brightness (Quantity): surface brightness per arcsecond^2 of the source, in ABmag units, or
                an equivalent count rate in photo-electrons per second per pixel.
            snr_target: The desired signal-to-noise ratio for the target
            sub_exp_time (Quantity): length of individual sub-exposures
            calc_type (string, optional, default 'per pixel'): calculation type, 'per pixel' to calculate signal & noise
                per pixel, 'per arcsecond squared' to calculate signal & noise per arcsecond^2
            saturation_check (bool, optional, default True): if true will set the total exposure time to zero if the
                    electrons per pixel in a single sub-exposure exceed the saturation level.
            binning (int, optional): pixel binning factor. Cannot be used with calculation type 'per arcsecond squared'

        Returns:
            Quantity: total exposure time required to reach the signal to noise ratio target, rounded up to an integer
                multiple of sub_exp_time
        """

        if calc_type not in ('per pixel', 'per arcsecond squared'):
            raise ValueError("Invalid calculation type '{}'!".format(calc_type))

        if calc_type == 'per arcsecond squared' and binning != 1:
            raise ValueError("Cannot specify pixel binning with calculation type 'per arcsecond squared'!")

        # Convert target SNR per array combined, binned pixel to SNR per unbinned pixel
        snr_target = ensure_unit(snr_target, u.dimensionless_unscaled)
        snr_target = snr_target / (self.num_imagers * binning)**0.5

        if calc_type == 'per arcseconds squared':
            # If snr_target was given as per arcseconds squared need to mutliply by square root of
            # pixel area to convert it to a per pixel value.
            snr_target = snr_target * self.pixel_scale / (u.arcsecond / u.pixel)

        if not isinstance(surface_brightness, u.Quantity):
            surface_brightness = surface_brightness * u.ABmag

        try:
            # If surface brightness is a count rate this should work
            rate = surface_brightness.to(u.electron / (u.pixel * u.second))
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have surface brightness in ABmag, call conversion function
            rate = self.SB_to_rate(surface_brightness)

        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        # If required total exposure time is much greater than the length of a sub-exposure then
        # all noise sources (including read noise) are proportional to t^0.5 and we can use a
        # simplified expression to estimate total exposure time.
        noise_squared_rate = ((rate + self.sky_rate + self.camera.dark_current) * (u.electron / u.pixel) +
                              self.camera.read_noise**2 / sub_exp_time)
        noise_squared_rate = noise_squared_rate.to(u.electron**2 / (u.pixel**2 * u.second))
        total_exp_time = (snr_target**2 * noise_squared_rate / rate**2).to(u.second)

        # Now just round up to the next integer number of sub-exposures, being careful because the total_exp_time
        # and/or sub_exp_time could be Quantity arrays instead of scalars. The simplified expression above is exact
        # for integer numbers of sub exposures and signal to noise ratio monotonically increases with exposure time
        # so the final signal to noise be above the target value.
        number_subs = np.ceil(total_exp_time / sub_exp_time)

        if saturation_check:
            saturated = self._is_saturated(rate, sub_exp_time)
            number_subs = np.where(saturated, 0, number_subs)

        return number_subs * sub_exp_time

    def extended_source_limit(self, total_exp_time, snr_target, sub_exp_time, calc_type='per pixel', binning=1,
                              enable_read_noise=True, enable_sky_noise=True, enable_dark_noise=True):
        """Calculates the limiting extended source surface brightness for a given minimum signal to noise ratio and
        total exposure time.

        Args:
            total_exp_time (Quantity): total length of all sub-exposures. If necessary will be rounded up to integer
                multiple of sub_exp_time
            snr_target: The desired signal-to-noise ratio for the target
            calc_type (string, optional, default 'per pixel'): calculation type, 'per pixel' to calculate signal & noise
                per pixel, 'per arcsecond squared' to calculate signal & noise per arcsecond^2
            sub_exp_time: Sub exposure time for each image, defaults to 300 seconds
            binning (int, optional): pixel binning factor. Cannot be used with calculation type 'per arcsecond squared'
            enable_read_noise (bool, optional, default True): If False calculates limit as if read noise were zero
            enable_sky_noise (bool, optional, default True): If False calculates limit as if sky background were zero
            enable_dark_noise (bool, optional, default True): If False calculates limits as if dark current were zero

        Returns:
            Quantity: limiting source surface brightness per arcsecond squared, in AB mag units.
        """

        if calc_type not in ('per pixel', 'per arcsecond squared'):
            raise ValueError("Invalid calculation type '{}'!".format(calc_type))

        if calc_type == 'per arcsecond squared' and binning != 1:
            raise ValueError("Cannot specify pixel binning with calculation type 'per arcsecond squared'!")

        # Convert target SNR per array combined, binned pixel to SNR per unbinned pixel
        snr_target = ensure_unit(snr_target, u.dimensionless_unscaled)
        snr_target = snr_target / (self.num_imagers * binning)**0.5

        if calc_type == 'per arcseconds squared':
            # If snr_target was given as per arcseconds squared need to mutliply by square root of
            # pixel area to convert it to a per pixel value.
            snr_target = snr_target * self.pixel_scale / (u.arcsecond / u.pixel)

        total_exp_time = ensure_unit(total_exp_time, u.second)
        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        # Round total exposure time to an integer number of sub exposures. One or both of total_exp_time or
        # sub_exp_time may be Quantity arrays, need np.ceil
        number_subs = np.ceil(total_exp_time / sub_exp_time)
        total_exp_time = number_subs * sub_exp_time

        # Noise sources
        sky_counts = self.sky_rate * total_exp_time if enable_sky_noise else 0.0 * u.electron / u.pixel
        dark_counts = self.camera.dark_current * total_exp_time if enable_dark_noise else 0.0 * u.electron / u.pixel
        total_read_noise = number_subs**0.5 * \
            self.camera.read_noise if enable_read_noise else 0.0 * u.electron / u.pixel

        noise_squared = ((sky_counts + dark_counts) * (u.electron / u.pixel) + total_read_noise**2)
        noise_squared.to(u.electron**2 / u.pixel**2)

        # Calculate science count rate for target signal to noise ratio
        a = total_exp_time**2
        b = -snr_target**2 * total_exp_time * u.electron / u.pixel  # Units come from converting signal counts to noise
        c = -snr_target**2 * noise_squared

        rate = (-b + (b**2 - 4 * a * c)**0.5) / (2 * a)
        rate = rate.to(u.electron / (u.pixel * u.second))

        return self.rate_to_SB(rate)

    def ABmag_to_rate(self, mag):
        """ Converts AB magnitudes to photo-electrons per second in the image sensor

        Args:
            mag (Quantity): source brightness in AB magnitudes

        Returns:
            Quantity: corresponding photo-electrons per second
        """
        mag = ensure_unit(mag, u.ABmag)

        # First convert to incoming spectral flux density per unit frequency
        f_nu = mag.to(u.W / (u.m**2 * u.Hz), equivalencies=u.equivalencies.spectral_density(self.pivot_wave))
        # Then convert to photo-electron rate using the 'sensitivity integral' for the instrument
        rate = f_nu * self.optic.aperture_area * self._iminus1 * u.photon / c.h

        return rate.to(u.electron / u.second)

    def rate_to_ABmag(self, rate):
        """ Converts photo-electrons per second in the image sensor to AB magnitudes

        Args:
            rate (Quantity): photo-electrons per second

        Returns:
            Quantity: corresponding source brightness in AB magnitudes
        """
        rate = ensure_unit(rate, u.electron / u.second)

        # First convert to incoming spectral flux density using the 'sensitivity integral' for the instrument
        f_nu = rate * c.h / (self.optic.aperture_area * self._iminus1 * u.photon)
        # Then convert to AB magnitudes
        return f_nu.to(u.ABmag, equivalencies=u.equivalencies.spectral_density(self.pivot_wave))

    def SB_to_rate(self, mag):
        """ Converts surface brightness AB magnitudes (per arcsecond squared) to photo-electrons per pixel per second.

        Args:
            mag (Quantity): source surface brightness in AB magnitudes

        Returns:
            Quantity: corresponding photo-electrons per pixel per second
        """
        # Use ABmag_to_rate() to convert to electrons per second, then multiply by pixel area
        SB_rate = self.ABmag_to_rate(mag) * self.pixel_area / (u.arcsecond**2)
        return SB_rate.to(u.electron / (u.second * u.pixel))

    def rate_to_SB(self, SB_rate):
        """ Converts photo-electrons per pixel per second to surface brightness AB magnitudes (per arcsecond squared)

        Args:
            SB_rate (Quantity): photo-electrons per pixel per second

        Returns:
            Quantity: corresponding source surface brightness in AB magnitudes
        """
        SB_rate = ensure_unit(SB_rate, u.electron / (u.second * u.pixel))
        # Divide by pixel area to convert to electrons per second per arcsecond^2
        rate = SB_rate * u.arcsecond**2 / self.pixel_area
        # Use rate_to_ABmag() to convert to AB magnitudes
        return self.rate_to_ABmag(rate)

    def ABmag_to_flux(self, mag):
        """ Converts brightness of the target to total flux, integrated over the filter band.

        Args:
            mag: brightness of the target, measured in ABmag

        Returns:
            Quantity: corresponding total flux in units of Watts per square metre
        """
        mag = ensure_unit(mag, u.ABmag)

        # First convert to spectral flux density per unit wavelength
        f_nu = mag.to(u.W / (u.m**2 * u.Hz), equivalencies=u.equivalencies.spectral_density(self.pivot_wave))
        # Then use pre-calculated integral to convert to total flux in the band (assumed constant F_nu)
        flux = f_nu * c.c * self._iminus2 * u.photon / u.electron

        return flux.to(u.W / (u.m**2))

    def total_exposure_time(self, total_elapsed_time, sub_exp_time):
        """ Calculates total exposure time given a total elapsed time and sub-exposure time

        Args:
            total_elapsed_time (Quantity): Total elapsed time, including readout overheads
            sub_exp_time (Quantity): Exposure time of individual sub-exposures

        Returns:
            Quantity: maximum total exposure time possible in an elapsed time of no more than total_elapsed_time
        """
        total_elapsed_time = ensure_unit(total_elapsed_time, u.second)
        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        num_of_subs = np.floor(total_elapsed_time / (sub_exp_time + self.camera.readout_time * self.num_per_computer))
        total_exposure_time = num_of_subs * sub_exp_time
        return total_exposure_time

    def total_elapsed_time(self, exp_list):
        """ Calculates the total elapsed time required for a given a list of sub exposure times

        Args:
            exp_list (Quantity): list of exposure times

        Returns:
            Quantity: total elapsed time, including readout overheads, required to execute the list of sub exposures
        """
        exp_list = ensure_unit(exp_list, u.second)

        elapsed_time = exp_list.sum() + len(exp_list) * self.num_per_computer * self.camera.readout_time
        return elapsed_time

    def point_source_signal_noise(self, brightness, total_exp_time, sub_exp_time, saturation_check=True):
        """Calculates the signal and noise for a point source of a given brightness, assuming PSF fitting photometry

        Args:
            brightness (Quantity): brightness of the source, in ABmag units, or an equivalent count rate in
                photo-electrons per second.
            total_exp_time (Quantity): total length of all sub-exposures. If necessary will be rounded up to integer
                multiple of sub_exp_time
            sub_exp_time (Quantity): length of individual sub-exposures
            saturation_check (bool, optional, default True): if true will set both signal and noise to zero if the
                electrons per pixel in a single sub-exposure exceed the saturation level.

        Returns:
            (Quantity, Quantity): effective signal and noise, in electrons
        """
        if not isinstance(brightness, u.Quantity):
            brightness = brightness * u.ABmag

        try:
            # If brightness is a count rate this should work
            rate = brightness.to(u.electron / u.second)
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have brightness in ABmag, call conversion function
            rate = self.ABmag_to_rate(brightness)

        # For PSF fitting photometry the signal to noise calculation is equivalent to dividing the flux equally
        # amongst n_pix pixels, where n_pix is the sum of the squares of the pixel values of the PSF.  The psf
        # object pre-calculates n_pix for the worst case where the PSF is centred on the corner of a pixel.

        # Now calculate effective signal and noise, using binning to calculate the totals.
        signal, noise = self.extended_source_signal_noise(rate / self.psf.n_pix, total_exp_time, sub_exp_time,
                                                          saturation_check=False, binning=self.psf.n_pix / u.pixel)
        signal = signal * u.pixel
        noise = noise * u.pixel

        # Saturation check. For point sources need to know maximum fraction of total electrons that will end up
        # in a single pixel, this is available as psf.peak. Can use this to calculate maximum electrons per pixel
        # in a single sub exposure, and check against saturation_level.
        if saturation_check:
            saturated = self._is_saturated(rate * self.psf.peak, sub_exp_time)
            # np.where strips units, need to manually put them back.
            signal = np.where(saturated, 0.0, signal) * u.electron
            noise = np.where(saturated, 0.0, noise) * u.electron

        return signal, noise

    def point_source_snr(self, brightness, total_exp_time, sub_exp_time, saturation_check=True):
        """Calculates the signal to noise ratio for a point source of a given brightness, assuming PSF fitting
        photometry

        Args:
            brightness (Quantity): brightness of the source, in ABmag units, or an equivalent count rate in
                photo-electrons per second.
            total_exp_time (Quantity): total length of all sub-exposures. If necessary will be rounded up to integer
                multiple of sub_exp_time
            sub_exp_time (Quantity): length of individual sub-exposures
            saturation_check (bool, optional, default True): if true will set the signal to noise ratio to zero if the
                electrons per pixel in a single sub-exposure exceed the saturation level.

        Returns:
            Quantity: signal to noise ratio, Quantity with dimensionless unscaled units
        """
        signal, noise = self.point_source_signal_noise(brightness, total_exp_time, sub_exp_time, saturation_check)

        # np.where() strips units, need to manually put them back.
        snr = np.where(noise != 0.0, signal / noise, 0.0) * u.dimensionless_unscaled

        return snr

    def point_source_etc(self, brightness, snr_target, sub_exp_time, saturation_check=True):
        """ Calculates the total exposure time required to reach a given signal to noise ratio for a given point
        source brightness.

        Args:
            brightness (Quantity): brightness of the source, in ABmag units, or an equivalent count rate in
                photo-electrons per second.
            snr_target: the desired signal-to-noise ratio for the target
            sub_exp_time (Quantity): length of individual sub-exposures
            saturation_check (bool, optional, default True): if true will set total exposure time to zero if the
                electrons per pixel in a single sub-exposure exceed the saturation level.

        Returns:
            Quantity: total exposure time required to reach the signal to noise ratio target, rounded up to an integer
                multiple of sub_exp_time
        """
        if not isinstance(brightness, u.Quantity):
            brightness = brightness * u.ABmag

        try:
            # If brightness is a count rate this should work
            rate = brightness.to(u.electron / u.second)
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have brightness in ABmag, call conversion function
            rate = self.ABmag_to_rate(brightness)

        total_exp_time = self.extended_source_etc(rate / self.psf.n_pix, snr_target, sub_exp_time,
                                                  saturation_check=False, binning=self.psf.n_pix / u.pixel)

        # Saturation check. For point sources need to know maximum fraction of total electrons that will end up
        # in a single pixel, this is available as psf.peak. Can use this to calculate maximum electrons per pixel
        # in a single sub exposure, and check against saturation_level.
        if saturation_check:
            saturated = self._is_saturated(rate * self.psf.peak, sub_exp_time)
            # np.where() strips units, need to manually put them back
            total_exp_time = np.where(saturated, 0.0, total_exp_time) * u.second

        return total_exp_time

    def point_source_limit(self, total_exp_time, snr_target, sub_exp_time,
                           enable_read_noise=True, enable_sky_noise=True, enable_dark_noise=True):
        """Calculates the limiting point source surface brightness for a given minimum signal to noise ratio and
        total exposure time.

        Args:
            total_exp_time (Quantity): total length of all sub-exposures. If necessary will be rounded up to integer
                multiple of sub_exp_time
            snr_target: The desired signal-to-noise ratio for the target
            sub_exp_time: Sub exposure time for each image
            enable_read_noise (bool, optional, default True): If False calculates limit as if read noise were zero
            enable_sky_noise (bool, optional, default True): If False calculates limit as if sky background were zero
            enable_dark_noise (bool, optional, default True): If False calculates limits as if dark current were zero

        Returns:
            Quantity: limiting point source brightness, in AB mag units.
        """
        # For PSF fitting photometry the signal to noise calculation is equivalent to dividing the flux equally
        # amongst n_pix pixels, where n_pix is the sum of the squares of the pixel values of the PSF.  The psf
        # object pre-calculates n_pix for the worst case where the PSF is centred on the corner of a pixel.

        # Calculate the equivalent limiting surface brighness, in AB magnitude per arcsecond^2
        equivalent_SB = self.extended_source_limit(total_exp_time, snr_target, sub_exp_time,
                                                   binning=self.psf.n_pix / u.pixel,
                                                   enable_read_noise=enable_read_noise,
                                                   enable_sky_noise=enable_sky_noise,
                                                   enable_dark_noise=enable_dark_noise)

        # Multiply the limit by the area (in arcsecond^2) of n_pix pixels to convert back to point source magnitude
        # astropy.units.ABmag doesn't really support arithmetic at the moment, have to strip units.
        return (equivalent_SB.value - 2.5 * np.log10(self.psf.n_pix * self.pixel_area / u.arcsecond**2).value) * u.ABmag

    def extended_source_saturation_mag(self, sub_exp_time, n_sigma=3.0):
        """ Calculates the surface brightness of the brightest extended source that would definitely not saturate the
            image sensor in a given (sub) exposure time.

        Args:
            sub_exp_time (Quantity): length of the (sub) exposure
            n_sigma (optional, default 3.0): margin between maximum expected electrons per pixel and saturation level,
                in multiples of the noise

        Returns:
            Quantity: surface brightness per arcsecond^2 of the brightest extended source that will definitely not
                saturate, in AB magnitudes.
        """
        sub_exp_time = ensure_unit(sub_exp_time, u.second)
        max_rate = (self.camera.saturation_level - n_sigma * self.camera.max_noise) / sub_exp_time
        max_source_rate = max_rate - self.sky_rate - self.camera.dark_current

        return self.rate_to_SB(max_source_rate)

    def point_source_saturation_mag(self, sub_exp_time, n_sigma=3.0):
        """ Calculates the magnitude of the brightest point source that would definitely not saturate the image
            sensor in a given (sub) exposure time.

        Args:
            sub_exp_time (Quantity): length of the (sub) exposure
            n_sigma (optional, default 3.0): margin between maximum expected electrons per pixel and saturation level,
                in multiples of the noise

        Returns:
            Quantity: AB magnitude of the brightest point source that will definitely not saturate.
        """
        sub_exp_time = ensure_unit(sub_exp_time, u.second)
        max_rate = (self.camera.saturation_level - n_sigma * self.camera.max_noise) / sub_exp_time
        max_source_rate = max_rate - self.sky_rate - self.camera.dark_current

        return self.rate_to_ABmag(max_source_rate / self.psf.peak)

    def extended_source_saturation_exp(self, surface_brightness, n_sigma=3.0):
        """ Calculates the maximum (sub) exposure time that will definitely avoid saturation for an extended source
            of given surface brightness

        Args:
            surface_brightness (Quantity): surface brightness per arcsecond^2 of the source, in ABmag units, or
                an equivalent count rate in photo-electrons per second per pixel.
            n_sigma (optional, default 3.0): margin between maximum expected electrons per pixel and saturation level,
                in multiples of the noise

        Returns:
            Quantity: maximum length of (sub) exposure that will definitely avoid saturation
        """
        if not isinstance(surface_brightness, u.Quantity):
            brightness = brightness * u.ABmag

        try:
            # If surface brightness is a count rate this should work
            rate = surface_brightness.to(u.electron / (u.pixel * u.second))
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have surface brightness in ABmag, call conversion function
            rate = self.SB_to_rate(surface_brightness)

        total_rate = rate + self.sky_rate + self.camera.dark_current

        max_electrons_per_pixel = self.camera.saturation_level - n_sigma * self.camera.max_noise

        return max_electrons_per_pixel / total_rate

    def point_source_saturation_exp(self, brightness, n_sigma=3.0):
        """ Calculates the maximum (sub) exposure time that will definitely avoid saturation for point source of given
            brightness

        Args:
            brightness (Quantity): brightness of the point source, in ABmag units, or an equivalent count rate in
                photo-electrons per second.
            n_sigma (optional, default 3.0): margin between maximum expected electrons per pixel and saturation level,
                in multiples of the noise

        Returns:
            Quantity: maximum length of (sub) exposure that will definitely avoid saturation
        """
        if not isinstance(brightness, u.Quantity):
            brightness = brightness * u.ABmag

        try:
            # If brightness is a count rate this should work
            rate = brightness.to(u.electron / u.second)
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have brightness in ABmag, call conversion function
            rate = self.ABmag_to_rate(brightness)

        # Convert to maximum surface brightness rate by multiplying by maximum flux fraction per pixel
        return self.extended_source_saturation_exp(rate * self.psf.peak)

    def exp_time_sequence(self,
                          bright_limit=None,
                          shortest_exp_time=None,
                          longest_exp_time=None,
                          faint_limit=None,
                          num_long_exp=None,
                          exp_time_ratio=2.0,
                          snr_target=5.0):
        """
        Calculates a sequence of sub exposures to use to span a given range of either point source brightness or
        exposure time. If required the sequence will begin with an 'HDR block' of progressly increasing exposure time,
        followed by 1 or more exposures of equal length with the number of long exposures either specified directly or
        calculated from the faintest point source that the sequence is intended to detect.

        Args:
            bright_limit (Quantity, optional): brightness in ABmag of the brightest point sources that we want to avoid
                saturating on, will be used to calculate a suitable shortest exposure time. Optional, but one and only
                one of bright_limit and shortest_exp_time must be specified.
            shortest_exp_time (Quantity, optional): shortest sub exposure time to include in the sequence. Optional, but
                one and only one of bright_limit and shortest_exp_time must be specified.
            longest_exp_time (Quantity): longest sub exposure time to include in the sequence.
            faint_limit (Quantity, optional): brightness in ABmag if the faintest point sources that we want to be able
                to detect in the combined data from the sequence. Optional, but one and only one of faint_limit and
                num_long_exp must be specified.
            num_long_exp (int, optional): number of repeats of the longest sub exposure to include in the sequence.
                Optional, but one and only one of faint_limit and num_long_exp must be specified.
            exp_time_ratio (float, optional, default 2.0): ratio between successive sub exposure times in the HDR block.
            snr_target(float, optional, default 5.0): signal to noise ratio threshold for detection at faint_limit

        Returns:
            Quantity: sequence of sub exposure times
        """
        # First verify all the inputs
        if bool(bright_limit) == bool(shortest_exp_time):
            raise ValueError("One and only one of bright_limit and shortest_exp_time must be specified!")

        if bool(faint_limit) == bool(num_long_exp):
            raise ValueError("one and only one of faint_limit and num_long_exp must be specified!")

        longest_exp_time = ensure_unit(longest_exp_time, u.second)
        if longest_exp_time < self.camera.minimum_exposure:
            raise ValueError("Longest exposure time shorter than minimum exposure time of the camera!")

        if bright_limit:
            # First calculate exposure time that will just saturate on the brightest sources.
            shortest_exp_time = self.point_source_saturation_exp(bright_limit)
        else:
            shortest_exp_time = ensure_unit(shortest_exp_time, u.second)

        # If the brightest sources won't saturate even for the longest requested exposure time then HDR mode isn't
        # necessary and we can just use the normal ETC to create a boring exposure time list.
        if shortest_exp_time >= longest_exp_time:
            if faint_limit:
                total_exp_time = self.point_source_etc(brightness=faint_limit,
                                                       sub_exp_time=longest_exp_time,
                                                       snr_target=snr_target)
                num_long_exp = int(total_exp_time / longest_exp_time)

            exp_times = num_long_exp * [longest_exp_time]
            exp_times = u.Quantity(exp_times)
            return exp_times

        # Round down the shortest exposure time so that it is a exp_time_ratio^integer multiple of the longest
        # exposure time
        num_exp_times = int(math.ceil(math.log(longest_exp_time / shortest_exp_time, exp_time_ratio)))
        shortest_exp_time = (longest_exp_time / (exp_time_ratio ** num_exp_times))

        # Ensuring the shortest exposure time is not lower than the minimum exposure time of the cameras
        if shortest_exp_time < self.camera.minimum_exposure:
            shortest_exp_time *= exp_time_ratio**math.ceil(math.log(self.camera.minimum_exposure / shortest_exp_time,
                                                                    exp_time_ratio))
            num_exp_times = int(math.log(longest_exp_time / shortest_exp_time, exp_time_ratio))

        # Creating a list of exposure times from the shortest exposure time to the one directly below the
        # longest exposure time
        exp_times = [shortest_exp_time.to(u.second) * exp_time_ratio**i for i in range(num_exp_times)]

        if faint_limit:
            num_long_exp = 0
            # Signals and noises from each of the sub exposures in the HDR sequence
            signals, noises = self.point_source_signal_noise(brightness=faint_limit,
                                                             sub_exp_time=u.Quantity(exp_times),
                                                             total_exp_time=u.Quantity(exp_times))
            # Running totals
            net_signal = signals.sum()
            net_noise_squared = (noises**2).sum()

            # Check is signal to noise target reach, add individual long exposures until it is.
            while net_signal / net_noise_squared**0.5 < snr_target:
                num_long_exp += 1
                signal, noise = self.point_source_signal_noise(brightness=faint_limit,
                                                               sub_exp_time=longest_exp_time,
                                                               total_exp_time=longest_exp_time)
                net_signal += signal
                net_noise_squared += noise**2

        exp_times = exp_times + num_long_exp * [longest_exp_time]
        exp_times = u.Quantity(exp_times)
        exp_times = np.around(exp_times, decimals=2)

        return exp_times

    def snr_vs_ABmag(self, exp_times, magnitude_interval=0.02 * u.ABmag, snr_target=1.0, plot=None):
        """
        Calculates PSF fitting signal to noise ratio as a function of point source brightness for the combined data
        resulting from a given sequence of sub exposures, and optionally generates a plot of the results. Automatically
        choses limits for the magnitude range based on the saturation limit of the shortest exposure and the
        sensitivity limit of the combined data.

        Args:
            exp_times (Quantity): 1D array of the lengths of the sub exposures
            magnitude_interval (Quantity, optional, default 0.02 mag(AB)): step between consecutive brightness values
            snr_target (optional, default 1.0): signal to noise threshold used to set faint limit of magnitude range
            plot (optional): filename for the plot of SNR vs magnitude. If not given no plots will be generated.
        """
        magnitude_interval = ensure_unit(magnitude_interval, u.ABmag)

        longest_exp_time = exp_times.max()

        if (exp_times == longest_exp_time).all():
            hdr = False
            # All exposures the same length, use direct calculation.

            # Magnitudes ranging from the sub exposure saturation limit to a SNR of 1 in the combined data.
            magnitudes = np.arange(self.point_source_saturation_mag(longest_exp_time.value),
                                   self.point_source_limit(total_exp_time=exp_times.sum(),
                                                           sub_exp_time=longest_exp_time,
                                                           snr_target=snr_target).value,
                                   magnitude_interval.value) * u.ABmag
            # Calculate SNR directly.
            snrs = self.point_source_snr(brightness=magnitudes,
                                         total_exp_time=exp_times.sum(),
                                         sub_expt_time=longest_exp_time)

        else:
            hdr = True
            # Have a range of exposure times.
            # Magnitudes ranging from saturation limit of the shortest sub exposure to the SNR of 1 limit for a non-HDR
            # sequence of the same total exposure time.
            magnitudes = np.arange(self.point_source_saturation_mag(exp_times.min()).value,
                                   self.point_source_limit(total_exp_time=exp_times.sum(),
                                                           sub_exp_time=longest_exp_time,
                                                           snr_target=snr_target).value,
                                   magnitude_interval.value) * u.ABmag

            # Split into HDR block & long exposure repeats
            hdr_exposures = np.where(exp_times != longest_exp_time)

            # Quantity array for running totals of signal and noise squared at each magnitude
            total_signals = np.zeros(magnitudes.shape) * u.electron
            total_noises_squared = np.zeros(magnitudes.shape) * u.electron**2

            # Signal to noise for each individual exposure in the HDR block
            for exp_time in exp_times[hdr_exposures]:
                signals, noises = self.point_source_signal_noise(brightness=magnitudes,
                                                                 total_exp_time=exp_time,
                                                                 sub_exp_time=exp_time)
                total_signals += signals
                total_noises_squared += noises**2

            # Direct calculation for the repeated exposures
            num_long_exps = (exp_times == longest_exp_time).sum()
            signals, noises = self.point_source_signal_noise(brightness=magnitudes,
                                                             total_exp_time=num_long_exps * longest_exp_time,
                                                             sub_exp_time=longest_exp_time)
            total_signals += signals
            total_noises_squared += noises**2

            snrs = total_signals / (total_noises_squared)**0.5

        if plot:
            if hdr:
                non_hdr_snrs = self.point_source_snr(brightness=magnitudes,
                                                     total_exp_time=exp_times.sum(),
                                                     sub_exp_time=longest_exp_time)
            plt.subplot(2, 1, 1)
            plt.plot(magnitudes, snrs, 'b-', label='HDR mode')
            if hdr:
                plt.plot(magnitudes, non_hdr_snrs, 'c:', label='Non-HDR mode')
                plt.legend(loc='upper right', fancybox=True, framealpha=0.3)
            plt.xlabel('Point source brightness / AB magnitude')
            plt.ylabel('Signal to noise ratio')
            plt.title('Point source PSF fitting signal to noise ratio for combined data')

            plt.subplot(2, 1, 2)
            plt.semilogy(magnitudes, snrs, 'b-', label='HDR mode')
            if hdr:
                plt.semilogy(magnitudes, non_hdr_snrs, 'c:', label='Non-HDR mode')
                plt.legend(loc='upper right', fancybox=True, framealpha=0.3)
            plt.xlabel('Point source brightness / AB magnitude')
            plt.ylabel('Signal to noise ratio')
            plt.title('Point source PSF fitting signal to noise ratio for combined data')

            plt.gcf().set_size_inches(12, 12)
            plt.savefig(plot)

        return magnitudes.to(u.ABmag), snrs.to(u.dimensionless_unscaled)

    def _is_saturated(self, rate, sub_exp_time, n_sigma=3.0):
        # Total electrons per pixel from source, sky and dark current
        electrons_per_pixel = (rate + self.sky_rate + self.camera.dark_current) * sub_exp_time
        # Consider saturated if electrons per pixel is closer than n sigmas of noise to the saturation level
        return electrons_per_pixel > self.camera.saturation_level - n_sigma * self.camera.max_noise

    def _efficiencies(self):
        # Fine wavelength grid spanning range of filter transmission profile
        waves = np.arange(self.band.wavelengths.value.min(), self.band.wavelengths.value.max(), 1) * u.nm

        # Interpolate throughput, filter transmission and QE to new grid
        tau = interp1d(self.optic.wavelengths, self.optic.throughput, kind='linear', fill_value='extrapolate')
        ft = interp1d(self.band.wavelengths, self.band.transmission, kind='linear', fill_value='extrapolate')
        qe = interp1d(self.camera.wavelengths, self.camera.QE, kind='linear', fill_value='extrapolate')

        # End-to-end efficiency. Need to put units back after interpolation
        effs = tau(waves) * ft(waves) * qe(waves) * u.electron / u.photon

        # Band averaged efficiency, effective wavelengths, bandwidth (STSci definition), flux_integral
        i0 = np.trapz(effs, x=waves)
        i1 = np.trapz(effs * waves, x=waves)
        self._iminus1 = np.trapz(effs / waves, x=waves)  # This one is useful later
        self._iminus2 = np.trapz(effs / waves**2, x=waves)

        self.wavelengths = waves
        self.efficiencies = effs
        self.efficiency = i0 / (waves[-1] - waves[0])
        self.mean_wave = i1 / i0
        self.pivot_wave = (i1 / self._iminus1)**0.5
        self.bandwidth = i0 / effs.max()

    def _gamma0(self):
        """
        Calculates 'gamma0', the number of photons/second/pixel at the top of atmosphere
        that corresponds to 0 AB mag/arcsec^2 for a given band, aperture & pixel scale.
        """
        # Spectral flux density corresponding to 0 ABmag, pseudo-SI units
        sfd_0 = (0 * u.ABmag).to(u.W / (u.m**2 * u.um),
                                 equivalencies=u.equivalencies.spectral_density(self.pivot_wave))
        # Change to surface brightness (0 ABmag/arcsec^2)
        sfd_sb_0 = sfd_0 / u.arcsecond**2
        # Average photon energy
        energy = c.h * c.c / (self.pivot_wave * u.photon)
        # Divide by photon energy & multiply by aperture area, pixel area and bandwidth to get photons/s/pixel
        photon_flux = (sfd_sb_0 / energy) * self.optic.aperture_area * self.pixel_area * self.bandwidth

        self.gamma0 = photon_flux.to(u.photon / (u.s * u.pixel))
