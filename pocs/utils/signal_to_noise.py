import math
import numpy as np
import os
from astropy import constants as c
from astropy import units as u
from astropy.convolution import discretize_model
from astropy.modeling.functional_models import Moffat2D
from astropy.table import Table
import matplotlib as mpl
from matplotlib import pyplot as plt
label_size = 15
mpl.rcParams['xtick.labelsize'] = label_size
mpl.rcParams['ytick.labelsize'] = label_size
from scipy.interpolate import interp1d


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
            bias (Quantity): bias level of image sensor, in ADU units. Used when determining saturation level.
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
        self.full_well = ensure_unit(full_well, u.electron)
        self.gain = ensure_unit(gain, u.electron / u.adu)
        self.readout_time = ensure_unit(readout_time, u.second)
        self.pixel_size = ensure_unit(pixel_size, u.micron / u.pixel)
        self.resolution = ensure_unit(resolution, u.pixel)
        self.read_noise = ensure_unit(read_noise, u.electron / u.pixel)
        self.dark_current = ensure_unit(dark_current, u.electron / (u.second * u.pixel))
        self.minimum_exposure = ensure_unit(minimum_exposure, u.second)

        # Calculate a saturation level corresponding to the lower of the 'analogue' (full well) and 'digital'
        # (ADC) limit, in electrons.
        self.saturation_level = min(self.full_well, ((2**self.bit_depth - 1) * u.adu - bias) * self.gain) / u.pixel

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
        if not isinstance(psf, Moffat_PSF):
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

        if calc_type not in ('per pixel', 'per arcsecond square'):
            raise ValueError("Invalid calculation type '{}'!".format(calc_type))

        if calc_type == 'per arcsecond squared' and binning != 1:
            raise ValueError("Cannot specify pixel binning with calculation type 'per arcsecond squared'!")

        if not isinstance(surface_brightness):
            surface_brightness = surface_brightness * u.ABmag

        try:
            # If surface brightness is a count rate this should work
            rate = surface_brightness.to(u.electrons / (u.pixel * u.second))
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have surface brightness in ABmag, call conversion function
            rate = self.SB_to_rate(surface_brightness)

        # Number of sub-exposures
        total_exp_time = ensure_unit(total_exp_time, u.second)
        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        # Round total exposure time to an integer number of sub exposures. One or both of total_exp_time or
        # sub_exp_time may be Quantity arrays, need np.ceil
        number_subs = np.ceil(total_exp_time / sub_exp_time).astype(int)
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
            saturated = (signal + sky_counts + dark_counts + total_read_noise) / number_subs > \
                        self.camera.saturation_level
            signal = np.where(saturated, 0 * u.electron / u.pixel, signal)
            noise = np.where(saturated, 0 * u.electron / u.pixel, noise)

        # Totals per (binned) pixel for all imagers
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
            saturation_check (bool, optional, default True): if true will set both signal and noise to zero if the
                electrons per pixel in a single sub-exposure exceed the saturation level.
            binning (int, optional): pixel binning factor. Cannot be used with calculation type 'per arcsecond squared'

        Returns:
            Quantity: signal to noise ratio, Quantity with dimensionless unscaled units
        """
        signal, noise = self.extended_source_signal_noise(surface_brightness, total_exp_time, sub_exp_time, calc_type,
                                                          saturation_check, binning)

        snr = np.where(noise != 0.0, signal / noise, 0.0)

        return snr.to(u.dimensionless_unscaled)

    def extended_source_etc(self, surface_brightness, snr_target, sub_exp_time, calc_type='per pixel', binning=1):
        """Calculates the total exposure time required to reach a given signal to noise ratio for a given extended
        source surface brightness.

        Args:
            surface_brightness (Quantity): surface brightness per arcsecond^2 of the source, in ABmag units, or
                an equivalent count rate in photo-electrons per second per pixel.
            snr_target: The desired signal-to-noise ratio for the target
            sub_exp_time (Quantity): length of individual sub-exposures
            calc_type (string, optional, default 'per pixel'): calculation type, 'per pixel' to calculate signal & noise
                per pixel, 'per arcsecond squared' to calculate signal & noise per arcsecond^2
            binning (int, optional): pixel binning factor. Cannot be used with calculation type 'per arcsecond squared'

        Returns:
            Quantity: total exposure time required to reach the signal to noise ratio target, rounded up to an integer
                multiple of sub_exp_time
        """

        if calc_type not in ('per pixel', 'per arcsecond square'):
            raise ValueError("Invalid calculation type '{}'!".format(calc_type))

        if calc_type == 'per arcsecond squared' and binning != 1:
            raise ValueError("Cannot specify pixel binning with calculation type 'per arcsecond squared'!")

        # Convert target SNR per array combined, binned pixel to SNR per unbinned pixel
        snr_target = snr_target / (self.num_imagers * binning)**0.5
        snr_target = ensure_unit(snr_target, u.dimensionless_unscaled)

        if calc_type == 'per arcseconds squared':
            # If snr_target was given as per arcseconds squared need to mutliply by square root of
            # pixel area to convert it to a per pixel value.
            snr_target = snr_target * self.pixel_scale / (u.arcsecond / u.pixel)

        # Science count rates
        try:
            # If surface brightness is a count rate this should work
            signal_rate = surface_brightness.to(u.electrons / (u.pixel * u.second))
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have surface brightness in ABmag, call conversion function
            signal_rate = self.SB_to_rate(surface_brightness)

        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        # If required total exposure time is much greater than the length of a sub-exposure then
        # all noise sources (including read noise) are proportional to t^0.5 and we can use a
        # simplified expression to estimate total exposure time.
        noise_squared_rate = ((signal_rate + self.sky_rate + self.camera.dark_current) * (u.electron / u.pixel) +
                              self.camera.read_noise**2 / sub_exp_time)
        noise_squared_rate = noise_squared_rate.to(u.electron**2 / (u.pixel**2 * u.second))
        total_exp_time = (snr_target**2 * noise_squared_rate / signal_rate**2).to(u.second)

        # Now just round up to the next integer number of sub-exposures, being careful because the total_exp_time
        # and/or sub_exp_time could be Quantity arrays instead of scalars. The simplified expression above is exact
        # for integer numbers of sub exposures and signal to noise ratio monotonically increases with exposure time
        # so the final signal to noise be above the target value.
        number_subs = np.ceil(total_exp_time / sub_exp_time).astype(np.int)

        return number_subs * sub_exp_time, number_subs

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

        if calc_type not in ('per pixel', 'per arcsecond square'):
            raise ValueError("Invalid calculation type '{}'!".format(calc_type))

        if calc_type == 'per arcsecond squared' and binning != 1:
            raise ValueError("Cannot specify pixel binning with calculation type 'per arcsecond squared'!")

        # Convert target SNR per array combined, binned pixel to SNR per unbinned pixel
        snr_target = snr_target / (self.num_imagers * binning)**0.5
        snr_target = ensure_unit(snr_target, u.dimensionless_unscaled)

        if calc_type == 'per arcseconds squared':
            # If snr_target was given as per arcseconds squared need to mutliply by square root of
            # pixel area to convert it to a per pixel value.
            snr_target = snr_target * self.pixel_scale / (u.arcsecond / u.pixel)

        total_exp_time = ensure_unit(total_exp_time, u.second)
        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        # Round total exposure time to an integer number of sub exposures. One or both of total_exp_time or
        # sub_exp_time may be Quantity arrays, need np.ceil
        number_subs = np.ceil(total_exp_time / sub_exp_time).astype(np.int)
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

        signal_rate = (-b + (b**2 - 4 * a * c)**0.5) / (2 * a)
        signal_rate = signal.rate.to(u.electron / (u.pixel * u.second))

        return self.rate_to_SB(signal_rate)

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
            rate = brightness.to(u.electrons / u.second)
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have brightness in ABmag, call conversion function
            rate = self.ABmag_to_rate(brightness)

        # For PSF fitting photometry the signal to noise calculation is equivalent to dividing the flux equally
        # amongst n_pix pixels, where n_pix is the sum of the squares of the pixel values of the PSF.  The psf
        # object pre-calculates n_pix for the worst case where the PSF is centred on the corner of a pixel.

        # Now calculate effective signal and noise, using binning to calculate the totals.
        signal, noise = self.extended_source_signal_noise(rate / self.psf.n_pix, total_exp_time, sub_exp_time,
                                                          binning=self.psf.n_pix, saturation_check=False)

        # Saturation check. For point sources need to know maximum fraction of total electrons that will end up
        # in a single pixel, this is available as psf.peak. Can use this to calculate maximum electrons per pixel
        # in a single sub exposure, and check against saturation_level.
        if saturation_check:
            max_signal = rate * self.psf.peak * sub_exp_time
            sky_counts = self.sky_rate * sub_exp_time
            dark_counts = self.camera.dark_current * sub_exp_time

            saturated = (max_signal + sky_counts + dark_counts + self.camera.read_noise) > \
                        self.camera.saturation_level

            signal = np.where(saturated, 0.0 * u.electron, signal)
            noise = np.where(saturated, 0.0 * u.electron, noise)

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
            saturation_check (bool, optional, default True): if true will set both signal and noise to zero if the
                electrons per pixel in a single sub-exposure exceed the saturation level.

        Returns:
            Quantity: signal to noise ratio, Quantity with dimensionless unscaled units
        """

        signal, noise = self.point_source_signal_noise(brightness, total_exp_time, sub_exp_time, saturation_check)

        snr = np.where(noise != 0.0, signal / noise, 0.0)

        return snr.to(u.dimensionless_unscaled)

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
            rate = brightness.to(u.electrons / u.second)
        except u.core.UnitConversionError:
            # Direct conversion failed so assume we have brightness in ABmag, call conversion function
            rate = self.ABmag_to_rate(brightness)

        total_exp_time = self.extended_source_etc(rate / self.psf.n_pix, snr_target, sub_exp_time,
                                                  binning=self.psf.n_pix)

        # Saturation check. For point sources need to know maximum fraction of total electrons that will end up
        # in a single pixel, this is available as psf.peak. Can use this to calculate maximum electrons per pixel
        # in a single sub exposure, and check against saturation_level.
        if saturation_check:
            max_signal = rate * self.psf.peak * sub_exp_time
            sky_counts = self.sky_rate * sub_exp_time
            dark_counts = self.camera.dark_current * sub_exp_time

            saturated = (max_signal + sky_counts + dark_counts + self.camera.read_noise) > \
                        self.camera.saturation_level

            total_exp_time = np.where(saturated, 0.0 * u.second, total_exp_time)

        return total_exp_time

    def point_source_limit(self, total_time, snr_target, sub_exp_time=600 * u.second,
                           enable_read_noise=True, enable_sky_noise=True, enable_dark_noise=True):
        """ Calculates the limiting point source magnitude

        Args:
            total_time: Total exposure time
            snr_target: signal-to-noise ratio of the point source
            sub_exp_time: Sub exposure time for each image, defaults to 300 seconds
            enable_read_noise: Allows us to remove the effect of the read noise in the calculations, when assigned 'False'
            enable_sky_noise: Allows us to remove the effect of the sky noise in the calculations, when assigned 'False'
            enable_dark_noise: Allows us to remove the effect of the dark noise in the calculations, when assigned 'False'
        """

        snr_type = 'per pixel'
        binning = self.n_pix
        signal_SB = self.SB_limit(total_time, snr_target, snr_type, sub_exp_time, binning, enable_read_noise,
                                  enable_sky_noise, enable_dark_noise)  # Calculating the surface brightness limit
        # Calculating the signal rate associated with the limit
        signal_rate = self.SB_to_rate(signal_SB) * (self.n_pix * u.pixel)
        return self.rate_to_ABmag(signal_rate)  # Converting the signal rate to point source brightness limit

    # Calculating the saturation magnitude limit for point objects
    def point_source_saturation_mag(self, exp_time):
        """ Calculates the minimum magnitude before saturation

        Args:
            exp_time: Total exposure time observing the point source target
        """

        # calculation of the maximum signal limit (in electrons) before saturation
        max_rate = self.camera.saturation_level / (exp_time * u.pixel)  # Max total count rate, electrons/s/pixel
        max_flux_fraction = self.peak / u.pixel  # Max proportion of point source flux per pixel
        max_signal_rate = (max_rate - self.sky_rate - self.camera.dark_current) / \
            max_flux_fraction  # Max count rate from point source, electron/s

        return self.rate_to_ABmag(max_signal_rate)  # Converting the rate into saturation level in ABmag

    def point_source_saturation_exp(self, point_source_magnitude):
        """ Calculates the maximum exposure time the point source can observed for before saturation

        Args:
            point_source_magnitude: Magnitude of the point source target
        """

        max_signal_rate = self.ABmag_to_rate(point_source_magnitude)
        max_flux_fraction = self.peak / u.pixel
        max_rate = (max_signal_rate * max_flux_fraction) + self.sky_rate + self.camera.dark_current
        sub_exp_time = self.camera.saturation_level / (max_rate * u.pixel)
        return sub_exp_time.to(u.second)

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


class Moffat_PSF(Moffat2D):

    def __init__(self, FWHM, alpha=2.5, pixel_scale=None):
        """
        Class representing a 2D Moffat profile point spread function.

        Used to calculate pixelated version of the PSF and associated parameters useful for
        point source signal to noise and saturation limit calculations.

        Args:
            FWHM (u.arcseconds): Full Width at Half-Maximum of the PSF
            alpha (optional): shape parameter, must be > 1, default 2.5

        Smaller values of the alpha parameter correspond to 'wingier' profiles.
        A value of 4.765 would give the best fit to pure Kolmogorov atmospheric turbulence.
        When instrumental effects are added a lower value is appropriate.
        IRAF uses a default of 2.5.
        """
        if alpha <= 1.0:
            raise ValueError('alpha must be greater than 1!')
        super(Moffat_PSF, self).__init__(alpha=alpha)

        self.FWHM = FWHM

        if pixel_scale:
            self.pixel_scale = pixel_scale

    @property
    def FWHM(self):
        return self._FWHM

    @FWHM.setter
    def FWHM(self, FWHM):
        self._FWHM = ensure_unit(FWHM, u.arcsecond)
        # If a pixel scale has been set should update model parameters when FWHM changes.
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
        return self._n_pix

    @property
    def peak(self):
        return self._peak

    def pixellated(self, pixel_scale=None, size=21, offsets=(0.0, 0.0)):
        """
        Calculates a pixellated version of the PSF for a given pixel scale
        """
        if pixel_scale:
            self.pixel_scale = pixel_scale
        else:
            # Should make sure _update_model() gets called anyway, in case
            # alpha has been changed.
            self._update_model()

        # Update PSF centre coordinates
        self.x_0 = offsets[0]
        self.y_0 = offsets[1]

        xrange = (-(size - 1) / 2, (size + 1) / 2)
        yrange = (-(size - 1) / 2, (size + 1) / 2)

        return discretize_model(self, xrange, yrange, mode='oversample', factor=10)

    def get_peak(self, pixel_scale=None):
        """
        Calculate the peak pixel value (as a fraction of total counts) for a PSF centred
        on a pixel. This is useful for calculating saturation limits for point sources.
        """
        # Odd number of pixels (1) so offsets = (0, 0) is centred on a pixel
        centred_psf = self.pixellated(pixel_scale, 1, offsets=(0, 0))
        return centred_psf[0, 0] / u.pixel

    def get_n_pix(self, pixel_scale=None, size=20):
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
        # Convert FWHM from arcsecond to pixel units
        self._FWHM_pix = self.FWHM / self.pixel_scale
        # Convert to FWHM to Moffat profile width parameter in pixel units
        gamma = self._FWHM_pix / (2 * np.sqrt(2**(1 / self.alpha) - 1))
        # Calculate amplitude required for normalised PSF
        amplitude = (self.alpha - 1) / (np.pi * gamma**2)
        # Update model parameters
        self.gamma = gamma.to(u.pixel).value
        self.amplitude = amplitude.to(u.pixel**-2).value

        self._n_pix = self.get_n_pix()
        self._peak = self.get_peak()


class ImagerArray:

    def __init__(self, imagers):
        """Class representing an array of Imagers

        Args:
            imagers (dict): dictionary containing instances of the Imager class
        """

        for imager in imagers.values():
            if not isinstance(imager, Imager):
                raise ValueError("{} not an instance of the Imager class".format(imager))
        self.imagers = imagers

        self.minimum_exposure = max([imager.camera.minimum_exposure for imager in self.imagers.values()])

    def HDR_mode(self, minimum_magnitude, name, long_exposures=1, factor=2, maximum_exp_time=300 * u.second,
                 generate_plots=False, maximum_magnitude=None):
        """Returns the exposure time array, corresponding saturation limits, total exposure and elapsed time, and SNR versus
        magnitude data

        Args:
            minimum_magnitude: Minimum magnitude we want to be able observe with the given set of imagers
            name: Name of the target
            long_exposures: Number of long exposures we want to use
            factor: increment Step between successive exposure times, up until the maximum exposure time
            maximum_exp_time: Maximum possible exposure time we can assign to the imagers
            generate_plots: Determines whether to generate the SNR versus magnitude plots for HDR versus non-HDR mode, defaults
            to False
            maximum_magnitude: Maximum magnitude we want to be able observe with the given set of imagers, defaults to None

        """

        exptime_array = self.exposure_time_array(minimum_magnitude, name, long_exposures, factor, maximum_exp_time,
                                                 maximum_magnitude)
        saturation_limits_array = self.saturation_limits(exptime_array, name)
        total_time_calc = self.total_time_calculation(exptime_array)
        snr_plot_data = self.snr_plot(exptime_array, name, maximum_exp_time, generate_plots)

        return exptime_array, saturation_limits_array, total_time_calc, snr_plot_data

    def exposure_time_array(self, minimum_magnitude, primary_imager, n_long_exposures=1, exp_time_ratio=2,
                            maximum_exp_time=300 * u.second, maximum_magnitude=None):
        """Returns a set of exposure times, which we can assign to the imagers

        Args:
            minimum_magnitude (Quantity): magnitude of the brightest point sources that we want to avoid saturating on
            primary_imager: name of the Imager that we want to use to generate the exposure time array
            long_exposures (optional, default 1): number of long exposures at the end of the HDR sequence
            exp_time_ratio (optional, default 2): ratio between successive exposure times in the HDR sequence
            maximum_exp_time (Quantity, optional, default 300s): exposure time to use for the long exposures
            maximum_magnitude (Quantity, optional): magnitude of the faintest point sources we want to detect
                (SNR>=5.0). If specified will override n_long_exposures

        """

        exp_list = []  # setting a list up

        # Calculating the number of exposure times such that shortest exposure time is a exp_time_ratio^integer
        # multiple of the longest exposure time

        saturation_exp_time = min([imager.point_source_saturation_exp(minimum_magnitude) for
                                   imager in self.imagers.values()])

        len_exp_array = math.ceil(math.log(maximum_exp_time / saturation_exp_time, exp_time_ratio))

        # Calculating the corresponding shortest exposure time
        shortest_exposure = (maximum_exp_time / (exp_time_ratio ** len_exp_array))

        # Ensuring the shortest exposure time is not lower than the minimum exposure time of the camera(s)
        if shortest_exposure < self.minimum_exposure:
            shortest_exposure *= factor**math.ceil(math.log(self.minimum_exposure / shortest_exposure, factor))
            len_exp_array = int(math.log(maximum_exp_time / shortest_exposure, factor))

        # Creating a list of exposure times from the shortest exposure time to the one directly below the
        # longest exposure time
        exp_list = [shortest_exposure.to(u.second) * exp_time_ratio**i for i in range(0, len_exp_array)]

        # Since we are using both n_long_exposures and maximum_magnitude as our parameters, we want a way to ensure that
        # both parameters aren't being set by the user. If they are, a ValueError is raised. If none are passed, a
        # default value of 1 is passed to long_exposures

        if maximum_magnitude is not None:
            if n_long_exposures != 1:
                raise ValueError("Only one of maximum_magnitude and n_long_exposures can be specified")
            else:
                num_long_exp = 0

                signals, noises = self.imagers[primary_imager].point_source_signal_noise(maximum_magnitude,
                                                                                         u.Quantity(exp_list),
                                                                                         u.Quantity(exp_list))
                net_signal = signals.sum()
                net_noise_squared = (noises**2).sum()

                while net_signal / net_noise_squared**0.5 < 5:
                    num_long_exp += 1
                    signal, noise = self.imagers[name].point_source_signal_noise(maximum_magnitude,
                                                                                 maximum_exp_time,
                                                                                 maximum_exp_time)
                    net_signal += signal
                    net_noise_squared += noise**2
        else:
            num_long_exp = n_long_exposures

        exp_list = exp_list + n_long_exposures * [maximum_exp_time]
        exp_list = np.around(exp_list, decimals=2)

        return exp_list

    def total_time_calculation(self, exp_list):
        """Returns the exposure and elapsed time for the total observation block

        Args:
            exp_list: a set of exposure times assigned to each imager

        """

        total_exp_time = sum(exp_list)
        total_elapsed_time = max([imager.total_elapsed_time(exp_list) for imager in self.imagers.values()])
        return total_exp_time, total_elapsed_time

    def saturation_limits(self, exp_list, name):
        """Returns the saturation limits for various exposure times

        Args:
            exp_list: a set of exposure times assigned to each imager
            name: name of the imager

        """

        saturation = self.imagers[name].point_source_saturation_mag(exp_list)
        return saturation

    def snr_plot(self, exp_list, name, maximum_exp_time=300 * u.second, generate_plots=False):
        """Returns point source signal-to-noise ratio across a range of magnitudes

        Args:
            exp_list: a set of exposure times assigned to each imager
            name: name of the imager
            maximum_exp_time: Maximum possible exposure time we can assign to the imagers
            generate_plots: Determines whether to generate the SNR versus magnitude plots for HDR versus non-HDR mode, defaults
            to False

        """

        # Non-HDR mode
        """The following bit of calculation generates a curve representing the combined SNR of different imagers,
        all of them taking a single exposure equal to the total elapsed time calculated by summing all the exposure
        times along with the readout time in between exposures generated by the exposure_time_array function"""

        total_elapsed_time = self.total_time_calculation(exp_list)[1]
        saturation1 = self.imagers[name].point_source_saturation_mag(total_elapsed_time)
        take_long_exposures = False  # default value

        for exp_time in exp_list:
            if exp_time == maximum_exp_time:
                take_long_exposures = True

        if take_long_exposures is True:
            '''If there are long exposures, then a sequence of single length exposures equal to maximum_exp_time is
            used, such that the total time is equal to the total_elapsed_time'''
            limit1 = self.imagers[name].point_source_limit(total_elapsed_time, 1.0, maximum_exp_time)
            mag_range1 = np.arange(saturation1.value, limit1.value, 0.1) * u.ABmag
            snr1 = self.imagers[name].point_source_snr(mag_range1, total_elapsed_time, maximum_exp_time)
        else:
            # If there are no long exposures, then a single exposure equal to the total elapsed time is taken
            limit1 = self.imagers[name].point_source_limit(total_elapsed_time, 1.0, total_elapsed_time)
            mag_range1 = np.arange(saturation1.value, limit1.value, 0.1) * u.ABmag
            snr1 = self.imagers[name].point_source_snr(mag_range1, total_elapsed_time, total_elapsed_time)

        # HDR mode
        """The following calculation genererates a curve for the combined SNR of different imagers, with each
        imager spanning through all of the predetermined set of exposure times (exp_list values)"""
        snr = []
        saturation = self.saturation_limits(exp_list, name)
        mag_range = np.arange(saturation[0].value, limit1.value, 0.1) * u.ABmag
        for magnitude in mag_range:
            net_signal = 0 * u.electron
            net_noise_squared = 0 * (u.electron ** 2)
            for exp_time in exp_list:
                signal, noise = self.imagers[name].point_source_signal_noise(magnitude, exp_time, exp_time)
                # signal and noise now both Quantity arrays, same length as explist
                net_signal = net_signal + signal
                net_noise_squared = net_noise_squared + (noise**2)

            if net_noise_squared != 0 * (u.electron ** 2):
                snr.append(net_signal / (net_noise_squared ** 0.5))
            else:
                snr.append(0.0)

        snr = snr * u.dimensionless_unscaled
        print(type(snr))
        print(type(mag_range))

        # Generating plots
        if generate_plots is True:
            plt.subplot(2, 1, 1)
            plt.plot(mag_range, snr, 'g-', label='HDR mode', linewidth=3)
            plt.plot(mag_range1, snr1, 'r:', label='Non-HDR mode', linewidth=4)
            plt.ylim(1, 400)
            plt.xlabel('Point source magnitude / AB mag', fontsize=22)
            plt.ylabel('SNR in $\sigma$', fontsize=22)
            plt.legend(loc='upper right', fancybox=True, framealpha=0.3, fontsize=22)
            plt.title('Combined SNR for the array of imagers', fontsize=24)
            plt.subplot(2, 1, 2)
            plt.semilogy(mag_range, snr, 'g-', label='HDR mode', linewidth=3)
            plt.semilogy(mag_range1, snr1, 'r--', label='Non-HDR mode', linewidth=4)
            plt.ylim(1, 400)
            plt.xlabel('Point source magnitude / AB mag', fontsize=22)
            plt.ylabel('SNR in $\sigma$', fontsize=22)
            plt.legend(loc='upper right', fancybox=True, framealpha=0.3, fontsize=22)
            plt.title('Combined SNR for the array of imagers', fontsize=24)
            plt.gcf().set_size_inches(24, 24)
            plt.savefig('snr_comparison_plot.png')
        return mag_range, snr
