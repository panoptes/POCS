# Tests for the signal-to-noise module
import pytest
import astropy.units as u

import pocs.utils.signal_to_noise as snr


def test_optic():
    lens = snr.Optic(aperture=14 * u.cm,
                     focal_length=0.391 * u.m,
                     throughput_filename='resources/performance_data/canon_throughput.csv')
    assert isinstance(lens, snr.Optic)
    assert lens.aperture == 140 * u.mm
    assert lens.focal_length == 39.1 * u.cm
    assert lens.central_obstruction == 0 * u.mm

    telescope = snr.Optic(aperture=279 * u.mm,
                          focal_length=620 * u.mm,
                          central_obstruction=129 * u.mm,
                          throughput_filename='resources/performance_data/rasa_tau.csv')
    assert isinstance(lens, snr.Optic)
    assert telescope.aperture == 0.279 * u.m
    assert telescope.focal_length == 62 * u.cm
    assert telescope.central_obstruction == 129 * u.mm


def test_camera():
    ccd = snr.Camera(bit_depth=16,
                     full_well=25500 * u.electron / u.pixel,
                     gain=0.37 * u.electron / u.adu,
                     bias=1100 * u.adu / u.pixel,
                     readout_time=0.9 * u.second,
                     pixel_size=5.4 * u.micron / u.pixel,
                     resolution=(3326, 2504) * u.pixel,
                     read_noise=9.3 * u.electron / u.pixel,
                     dark_current=0.04 * u.electron / (u.pixel * u.second),
                     minimum_exposure=0.1 * u.second,
                     QE_filename='resources/performance_data/ML8300M_QE.csv')
    assert isinstance(ccd, snr.Camera)
    assert ccd.saturation_level == min(25500 * u.electron / u.pixel,
                                       (((2**16 - 1) - 1100) * 0.37 * u.electron / u.pixel))
    assert ccd.max_noise == (ccd.saturation_level * u.electron / u.pixel + (9.3 * u.electron / u.pixel)**2)**0.5


def test_filter():
    bandpass = snr.Filter(transmission_filename='resources/performance_data/astrodon_g.csv',
                          sky_mu=22.5 * u.ABmag)
    assert isinstance(bandpass, snr.Filter)
    assert bandpass.sky_mu == 22.5 * u.ABmag


def test_psf_base():
    with pytest.raises(TypeError):
        # Try to instantiate abstract base class, should fail
        psf_base = snr.PSF(FWHM=1 / 30 * u.arcminute)


def test_psf_moffat():
    psf = snr.Moffat_PSF(FWHM=1 / 30 * u.arcminute, shape=4.7)
    assert isinstance(psf, snr.Moffat_PSF)
    assert isinstance(psf, snr.PSF)
    assert psf.FWHM == 2 * u.arcsecond
