import math
import numpy as np
import os

from astropy import constants as c
from astropy import units as u
from astropy.convolution import discretize_model
from astropy.modeling.functional_models import Moffat2D
from astropy.table import Table
from matplotlib import pyplot as plt
from scipy.interpolate import interp1d


def ensure_unit(arg, unit):
    if not isinstance(arg, u.Quantity):
        arg = arg * unit
    return arg.to(unit)


class Optic:

    def __init__(self, aperture, focal_length, throughput_filename, central_obstruction=0 * u.mm):
        """
        Class representing imager optics (e.g. Canon lens, RASA telescope),
        incorporates basic attributes such as aperture diameter, focal length
        and central obstruction.
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

    def __init__(self, bit_depth, full_well, gain, readout_time, pixel_size, resolution, read_noise, dark_current,
                 QE_filename, minimum_exposure):
        """
        Class representing a camera, incorporated basic properties such
        as bit depth, full well, gain, readout time, pixel size, resolution, read noise and dark current.
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
        self.saturation_level = min(self.full_well, (2**self.bit_depth - 1501) * u.adu * self.gain)  # electrons

        QE_data = Table.read(os.path.join(os.getenv('POCS'), QE_filename))

        if not QE_data['Wavelength'].unit:
            QE_data['Wavelength'].unit = u.nm
        self.wavelengths = QE_data['Wavelength'].quantity.to(u.nm)

        if not QE_data['QE'].unit:
            QE_data['QE'].unit = u.electron / u.photon
        self.QE = QE_data['QE'].quantity.to(u.electron / u.photon)


class Filter:

    def __init__(self, transmission_filename, sky_mu):
        """
        Class representing a bandpass filter, which incorporates sky surface brightness for
        the filter band.
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

    def __init__(self, optic, camera, band, num_imagers=1, num_per_computer=1, PSF=None):
        if not isinstance(optic, Optic):
            raise ValueError("optic must be an instance of the Optic class")
        if not isinstance(camera, Camera):
            raise ValueError("camera must be an instance of the Camera class")
        if not isinstance(band, Filter):
            raise ValueError("band must be an instance of the Filter class")
        if PSF and not isinstance(PSF, Moffat_PSF):
            raise ValueError("PSF must be an instance of the Moffat PSF class")

        self.optic = optic
        self.camera = camera
        self.band = band
        self.PSF = PSF
        self.num_imagers = int(num_imagers)
        self.num_per_computer = int(num_per_computer)

        # Calculate pixel scale, area
        self.pixel_scale = (self.camera.pixel_size / self.optic.focal_length)
        self.pixel_scale = self.pixel_scale.to(u.arcsecond / u.pixel,
                                               equivalencies=u.equivalencies.dimensionless_angles())
        self.pixel_area = self.pixel_scale**2 * u.pixel
        self.PSF.pixel_scale = self.pixel_scale

        # Calculate field of view.
        self.field_of_view = (self.camera.resolution * self.pixel_scale)
        self.field_of_view = self.field_of_view.to(u.degree, equivalencies=u.dimensionless_angles())

        # Calculate n_pix value
        self.n_pix = self.PSF.n_pix()

        # Calculate peak value
        self.peak = self.PSF.peak()

        # Calculate end to end efficiencies, etc.
        self._efficiencies()

        # Calculate sky count rate for later use
        self.sky_rate = self.SB_to_rate(self.band.sky_mu)

    def SB_signal_noise(self, signal_SB, total_exp_time, sub_exp_time=300 * u.second, binning=1):

        # Signal count rates
        signal_rate = self.SB_to_rate(signal_SB)  # e/pixel/second

        # Number of sub-exposures
        total_exp_time = ensure_unit(total_exp_time, u.second)
        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        number_subs = int(math.ceil(total_exp_time / sub_exp_time))

        if (total_exp_time != number_subs * sub_exp_time):
            total_exp_time = number_subs * sub_exp_time
            print('Rounding up total exposure time to next integer multiple of sub-exposure time:', total_exp_time)

        # Noise sources
        signal = (signal_rate * total_exp_time).to(u.electron / u.pixel)
        sky_counts = (self.sky_rate * total_exp_time).to(u.electron / u.pixel)
        dark_counts = (self.camera.dark_current * total_exp_time).to(u.electron / u.pixel)
        total_read_noise = ((number_subs)**0.5 * self.camera.read_noise).to(u.electron / u.pixel)

        noise = (signal.value + sky_counts.value + dark_counts.value + total_read_noise.value**2)**0.5
        noise = noise * u.electron / u.pixel

        signal = signal * self.num_imagers * binning
        noise = noise * (self.num_imagers * binning)**0.5
        return signal, noise

    def SB_snr(self, signal_SB, total_exp_time, sub_exp_time=300 * u.second, binning=1):
        signal, noise = self.SB_signal_noise(signal_SB, total_exp_time, sub_exp_time, binning)
        snr = np.where(noise != 0.0, signal / noise, 0.0)
        return snr  # returns the signal-to-noise ratio

    def SB_etc(self, signal_SB, snr_target, sub_exp_time=300 * u.second, binning=1):

        # Science count rates
        signal_rate = self.SB_to_rate(signal_SB)

        # Convert target SNR per array combined, binned pixel to SNR per unbinned pixel
        snr_target = snr_target / (self.num_imagers * binning)**0.5
        snr_target = ensure_unit(snr_target, u.dimensionless_unscaled)

        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        # If required total exposure time is much greater than the length of a sub-exposure then
        # all noise sources (including read noise) are proportional to t^0.5 and we can use a
        # simplified expression to estimate total exposure time.
        noise_squared_rate = (signal_rate.value + self.sky_rate.value + self.camera.dark_current.value +
                              self.camera.read_noise.value**2 / sub_exp_time.value)
        noise_squared_rate = noise_squared_rate * u.electron**2 / (u.pixel**2 * u.second)
        total_exp_time = (snr_target**2 * noise_squared_rate / signal_rate**2).to(u.second)

        # The simplified expression underestimates read noise due to fractional number of sub-exposure,
        # the effect will be neglible unless the total exposure time is very short but we can fix it anyway...
        # First round up to the next integer number of sub-exposures:
        number_subs = int(math.ceil(total_exp_time / sub_exp_time))
        # If the SNR has dropped below the target value as a result of the extra read noise add another sub
        # Note: calling snr() here is horribly inefficient as it recalculates a bunch of stuff but I don't care.
        while self.SB_snr(signal_SB, number_subs * sub_exp_time, sub_exp_time, binning) < snr_target:
            number_subs = number_subs + 1

        return number_subs * sub_exp_time, number_subs

    def SB_limit(self, total_exp_time, snr_target, snr_type='per pixel', sub_exp_time=600 * u.second, binning=1,
                 enable_read_noise=True, enable_sky_noise=True, enable_dark_noise=True):
        snr_target = snr_target / (self.num_imagers * binning)**0.5
        # Convert target SNR per array combined, binned pixel to SNR per unbinned pixel
        if snr_type == 'per pixel':
            pass
        elif snr_type == 'per arcseconds squared':
            snr_target = snr_target * self.pixel_scale / (u.arcsecond / u.pixel)
        else:
            raise ValueError('invalid snr target type {}'.format(snr_type))

        snr_target = ensure_unit(snr_target, u.dimensionless_unscaled)

        # Number of sub-exposures
        total_exp_time = ensure_unit(total_exp_time, u.second)
        sub_exp_time = ensure_unit(sub_exp_time, u.second)

        number_subs = np.ceil(total_exp_time / sub_exp_time).astype(int)

        total_exp_time = number_subs * sub_exp_time

        # Noise sources
        sky_counts = self.sky_rate * total_exp_time if enable_sky_noise else 0.0 * u.electron / u.pixel
        dark_counts = self.camera.dark_current * total_exp_time if enable_dark_noise else 0.0 * u.electron / u.pixel
        total_read_noise = np.sqrt(number_subs) * \
            self.camera.read_noise if enable_read_noise else 0.0 * u.electron / u.pixel

        noise_squared = (sky_counts.value + dark_counts.value + total_read_noise.value**2) * u.electron**2 / u.pixel**2

        # Calculate science count rate for target signal to noise ratio
        a = (total_exp_time**2).value
        b = -((snr_target)**2 * total_exp_time).value
        c = -((snr_target)**2 * noise_squared).value

        signal_rate = (-b + np.sqrt(b**2 - 4 * a * c)) / (2 * a) * u.electron / (u.pixel * u.second)

        return self.rate_to_SB(signal_rate)

    def ABmag_to_rate(self, mag):
        mag = ensure_unit(mag, u.ABmag)

        f_nu = mag.to(u.W / (u.m**2 * u.Hz), equivalencies=u.equivalencies.spectral_density(self.pivot_wave))
        rate = f_nu * self.optic.aperture_area * self._iminus1 * u.photon / c.h

        return rate.to(u.electron / u.second)

    def rate_to_ABmag(self, rate):
        ensure_unit(rate, u.electron / u.second)

        f_nu = rate * c.h / (self.optic.aperture_area * self._iminus1 * u.photon)
        return f_nu.to(u.ABmag, equivalencies=u.equivalencies.spectral_density(self.pivot_wave))

    def SB_to_rate(self, mag):
        SB_rate = self.ABmag_to_rate(mag) * self.pixel_area / (u.arcsecond**2)
        return SB_rate.to(u.electron / (u.second * u.pixel))

    def rate_to_SB(self, SB_rate):
        ensure_unit(SB_rate, u.electron / (u.second * u.pixel))

        rate = SB_rate * u.arcsecond**2 / self.pixel_area
        return self.rate_to_ABmag(rate)

    def ABmag_to_flux(self, mag):
        mag = ensure_unit(mag, u.ABmag)

        f_nu = mag.to(u.W / (u.m**2 * u.Hz), equivalencies=u.equivalencies.spectral_density(self.pivot_wave))
        flux = f_nu * c.c * self._iminus2 * u.photon / u.electron

        return flux.to(u.W / (u.m**2))

    def total_exposure_time(self, total_elapsed_time, sub_exp_time):
        """Now we create a function that takes in a sub exposure time and total elapsed time and gives out total
        exposure time (maximum time). """
        total_elapsed_time = ensure_unit(total_elapsed_time, u.second)
        sub_exp_time = ensure_unit(sub_exp_time, u.second)
        num_of_subs = total_elapsed_time / (sub_exp_time + self.camera.readout_time * self.num_per_computer)
        total_exposure_time = num_of_subs * sub_exp_time
        return total_exposure_time

    def point_source_signal_noise(self, signal_mag, total_exp_time, sub_exp_time=300 * u.second):
        # ensuring that the units of point source signal magnitude is AB mag
        signal_mag = ensure_unit(signal_mag, u.ABmag)
        # converting the signal magnitude to signal rate in electron/pixel/second
        signal_rate = self.ABmag_to_rate(signal_mag) / (self.n_pix * u.pixel)
        signal_SB = self.rate_to_SB(signal_rate)  # converting the signal rate to surface brightness
        binning = self.n_pix  # scaling the binning by the number of pixels covered by the point source
        signal, noise = self.SB_signal_noise(signal_SB, total_exp_time, sub_exp_time, binning)
        point_source_saturation_magnitude = self.point_source_saturation_mag(total_exp_time)
        signal = np.where(signal_mag > point_source_saturation_magnitude, signal.value, 0.0 * u.electron) * u.electron
        noise = np.where(signal_mag > point_source_saturation_magnitude, noise.value, 0.0 * u.electron) * u.electron
        return signal, noise

    def point_source_snr(self, signal_mag, total_exp_time, sub_exp_time=300 * u.second):
        signal, noise = self.point_source_signal_noise(signal_mag, total_exp_time, sub_exp_time)
        snr = np.where(noise != 0.0, signal / noise, 0.0)
        return snr  # returns the signal-to-noise ratio

    def point_source_etc(self, signal_mag, snr_target, sub_exp_time=300 * u.second):
        signal_mag = ensure_unit(signal_mag, u.ABmag)
        signal_rate = self.ABmag_to_rate(signal_mag) / (self.n_pix * u.pixel)
        signal_SB = self.rate_to_SB(signal_rate)
        binning = self.n_pix
        return self.SB_etc(signal_SB.value, snr_target, sub_exp_time, binning)

    def point_source_limit(self, total_time, snr_target, sub_exp_time=600 * u.second,
                           enable_read_noise=True, enable_sky_noise=True, enable_dark_noise=True):
        snr_type = 'per pixel'
        binning = self.n_pix
        signal_SB = self.SB_limit(total_time, snr_target, snr_type, sub_exp_time, binning, enable_read_noise,
                                  enable_sky_noise, enable_dark_noise)  # Calculating the surface brightness limit
        # Calculating the signal rate associated with the limit
        signal_rate = self.SB_to_rate(signal_SB) * (self.n_pix * u.pixel)
        return self.rate_to_ABmag(signal_rate)  # Converting the signal rate to point source brightness limit

    # Calculating the saturation magnitude limit for point objects
    def point_source_saturation_mag(self, exp_time):
        # calculation of the maximum signal limit (in electrons) before saturation
        max_rate = self.camera.saturation_level / (exp_time * u.pixel)  # Max total count rate, electrons/s/pixel
        max_flux_fraction = self.peak / u.pixel  # Max proportion of point source flux per pixel
        max_signal_rate = (max_rate - self.sky_rate - self.camera.dark_current) / \
            max_flux_fraction  # Max count rate from point source, electron/s

        return self.rate_to_ABmag(max_signal_rate)  # Converting the rate into saturation level in ABmag

    def point_source_saturation_exp(self, point_source_magnitude):
        """ This function takes in a point source magnitude and returns the maximum sub exposure time for
        which a point source of this magnitude does not saturate """
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

    def pixellated(self, pixel_scale=None, n_pix=21, offsets=(0.0, 0.0)):
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

        xrange = (-(n_pix - 1) / 2, (n_pix + 1) / 2)
        yrange = (-(n_pix - 1) / 2, (n_pix + 1) / 2)

        return discretize_model(self, xrange, yrange, mode='oversample', factor=10)

    def peak(self, pixel_scale=None):
        """
        Calculate the peak pixel value (as a fraction of total counts) for a PSF centred
        on a pixel. This is useful for calculating saturation limits for point sources.
        """
        # Odd number of pixels (1) so offsets = (0, 0) is centred on a pixel
        centred_psf = self.pixellated(pixel_scale, 1, offsets=(0, 0))
        return centred_psf[0, 0]

    def n_pix(self, pixel_scale=None, n_pix=20):
        """
        Calculate the effective number of pixels for PSF fitting photometry with this
        PSF, in the worse case where the PSF is centred on the corner of a pixel.
        """
        # Want a even number of pixels.
        n_pix = n_pix + n_pix % 2
        # Even number of pixels so offsets = (0, 0) is centred on pixel corners
        corner_psf = self.pixellated(pixel_scale, n_pix, offsets=(0, 0))
        return 1 / ((corner_psf**2).sum())

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


class ImagerArray:

    def __init__(self, imagers):
        """
        ImagerArray class takes in a set of imagers, and calculates a set of sub
        exposure times that each of the imager spans through
        """
        for imager in imagers.values():
            if not isinstance(imager, Imager):
                raise ValueError("{} not an instance of the  Imager class".format(imager))
        self.imagers = imagers

        self.minimum_exposure = max([imager.camera.minimum_exposure for imager in self.imagers.values()])

    def HDR_mode(self, minimum_magnitude, name, long_exposures=1, factor=2, maximum_exptime=300 * u.second,
                 generate_plots=False, maximum_magnitude=None):
        """

        The following function calculates all the necessary information for the HDR mode,
        including the exposure times assigned to the imagers, the total exposure and
        elapsed time for the set of exposure times, the saturation limits for
        the corresponding exposure times, and the SNR versus magnitude data for this mode

        """

        exptime_array = self.exposure_time_array(minimum_magnitude, name, long_exposures, factor, maximum_exptime,
                                                 maximum_magnitude)
        saturation_limits_array = self.saturation_limits(exptime_array, name)
        total_time_calc = self.total_time_calculation(exptime_array, name)
        snr_plot_data = self.snr_plot(exptime_array, name, generate_plots)

        return exptime_array, saturation_limits_array, total_time_calc, snr_plot_data

    def exposure_time_array(self, minimum_magnitude, name, long_exposures=1, factor=2, maximum_exptime=300 * u.second,
                            maximum_magnitude=None):
        exp_list = []  # setting a list up
        """Calculating the number of exposure times such that minimum exposure time is a factor^integer multiple
        of the highest exposure time set to be 300 seconds"""
        minimum_exptime = min([imager.point_source_saturation_exp(minimum_magnitude)
                               for imager in self.imagers.values()])

        len_exp_array = math.ceil(math.log(maximum_exptime / minimum_exptime, factor))

        # Calculating the corresponding shortest exposure time
        shortest_exposure = (maximum_exptime / (factor ** len_exp_array))

        # Ensuring the shortest exposure time is not lower than the minimum exposure time of the camera(s)
        if shortest_exposure < self.minimum_exposure:
            shortest_exposure *= factor**math.ceil(math.log(self.minimum_exposure / shortest_exposure, factor))
            len_exp_array = int(math.log(maximum_exptime / shortest_exposure, factor))

        # Creating a list of exposure times from the lowest exposure time to the
        # one directly below the maximum exposure time
        exp_list = [shortest_exposure.to(u.second).value * factor**i for i in range(0, len_exp_array)]

        if maximum_magnitude is not None:
            num_long_exp = 0
            net_signal = 0 * u.electron
            net_noise_squared = 0 * (u.electron ** 2)

            for exp_time in exp_list:
                signal, noise = self.imagers[name].point_source_signal_noise(
                    maximum_magnitude, exp_time * u.second, exp_time * u.second)
                net_signal = signal.sum()
                net_noise_squared = (noise**2).sum()

            while net_signal / net_noise_squared**0.5 < 5:
                num_long_exp += 1
                signal, noise = self.imagers[name].point_source_signal_noise(maximum_magnitude, maximum_exptime,
                                                                             maximum_exptime)
                net_signal += signal
                net_noise_squared += noise**2
        else:
            num_long_exp = long_exposures

        for i in range(0, num_long_exp):
            exp_list.append(maximum_exptime.value)

        exp_list = np.around(exp_list, decimals=2) * u.second
        return exp_list

    def total_time_calculation(self, exp_list, name):
        """Given a list of exposure times that each camera spans through, total_time_calculation calculates the
        total exposure time and total elapsed time (includes the readout time between successive sub exposures"""
        total_exp_time = sum(exp_list)
        total_elapsed_time = total_exp_time + len(exp_list) * min(self.imagers[name].num_per_computer,
                                                                  self.imagers[name].num_imagers
                                                                  ) * self.imagers[name].camera.readout_time

        return total_exp_time, total_elapsed_time

    def saturation_limits(self, exp_list, name):
        saturation = []
        for i in range(0, len(exp_list)):
            saturation.append(self.imagers[name].point_source_saturation_mag(exp_list[i]))
        return saturation

    def snr_plot(self, exp_list, name, generate_plots=False):
        """The following bit of calculation generates a curve representing the combined SNR of different imagers,
        all of them taking a single exposure equal to the total elapsed time calculated by summing all the exposure
        times along with the readout time in between exposures generated by the exposure_time_array function"""

        total_elapsed_time = self.total_time_calculation(exp_list, name)[1]
        saturation1 = self.imagers[name].point_source_saturation_mag(total_elapsed_time)
        limit1 = self.imagers[name].point_source_limit(
            total_elapsed_time, 1.0, total_elapsed_time, enable_read_noise=True,
            enable_sky_noise=True, enable_dark_noise=True)  # the magnitude that gives a value of 1.0 SNR

        mag_range1 = np.arange(saturation1.value, limit1.value, 0.1) * u.ABmag
        snr1 = self.imagers[name].point_source_snr(mag_range1, total_elapsed_time, total_elapsed_time)

        """The following calculation genererates a curve for the combined SNR of different imagers, with each
        imager spanning through all of the predetermined set of exposure times (exp_list values)"""
        saturation = self.saturation_limits(exp_list, name)
        mag_range = np.arange(saturation[0].value, limit1.value, 0.1) * u.ABmag
        dimension = int(round((limit1.value - saturation[0].value) / 0.1))
        net_signal = np.zeros(dimension) * u.electron
        net_noise_squared = np.zeros(dimension) * (u.electron ** 2)
        for exp_time in exp_list:
            signal, noise = self.imagers[name].point_source_signal_noise(mag_range, exp_time, exp_time)
            net_signal = net_signal + signal
            net_noise_squared = net_noise_squared + (noise**2)
        snr = np.where(net_noise_squared != 0, net_signal / (net_noise_squared) ** 0.5, 0.0)

        if generate_plots is True:
            plt.subplot(2, 1, 1)
            plt.plot(mag_range, snr, 'g-', label='HDR mode', linewidth=3)
            plt.plot(mag_range1, snr1, 'r:', label='Non-HDR mode', linewidth=4)
            plt.ylim(1, 1300)
            plt.xlabel('Point source magnitude / AB mag', fontsize=20)
            plt.ylabel('SNR in $\sigma$', fontsize=20)
            plt.legend(loc='upper right', fancybox=True, framealpha=0.3, fontsize=20)
            plt.title('Combined SNR for the array of imagers', fontsize=24)
            plt.subplot(2, 1, 2)
            plt.semilogy(mag_range, snr, 'g-', label='HDR mode', linewidth=3)
            plt.semilogy(mag_range1, snr1, 'r--', label='Non-HDR mode', linewidth=4)
            plt.ylim(1, 1300)
            plt.xlabel('Point source magnitude / AB mag', fontsize=20)
            plt.ylabel('SNR in $\sigma$', fontsize=20)
            plt.legend(loc='upper right', fancybox=True, framealpha=0.3, fontsize=20)
            plt.title('Combined SNR for the array of imagers', fontsize=24)
            plt.gcf().set_size_inches(24, 24)
            plt.savefig('snr_comparison_plot.png')
        return mag_range, snr
