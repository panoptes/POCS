# Tests for the signal-to-noise module
import pytest
import astropy.units as u

import pocs.utils.signal_to_noise as snr


@pytest.fixture(scope='module')
def lens():
    lens = snr.Optic(aperture=14 * u.cm,
                     focal_length=0.391 * u.m,
                     throughput_filename='resources/performance_data/canon_throughput.csv')
    return lens


@pytest.fixture(scope='module')
def telescope():
    telescope = snr.Optic(aperture=279 * u.mm,
                          focal_length=620 * u.mm,
                          central_obstruction=129 * u.mm,
                          throughput_filename='resources/performance_data/rasa_tau.csv')
    return telescope


@pytest.fixture(scope='module')
def ccd():
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
    return ccd


@pytest.fixture(scope='module')
def bandpass():
    bandpass = snr.Filter(transmission_filename='resources/performance_data/astrodon_g.csv',
                          sky_mu=22.5 * u.ABmag)
    return bandpass


@pytest.fixture(scope='module')
def psf():
    psf = snr.Moffat_PSF(FWHM=1 / 30 * u.arcminute, shape=4.7)
    return psf


@pytest.fixture(scope='module')
def imager(lens, ccd, bandpass, psf):
    imager = snr.Imager(optic=lens, camera=ccd, band=bandpass, psf=psf, num_imagers=5, num_per_computer=5)
    return imager


def test_optic(lens, telescope):
    assert isinstance(lens, snr.Optic)
    assert lens.aperture == 140 * u.mm
    assert lens.focal_length == 39.1 * u.cm
    assert lens.central_obstruction == 0 * u.mm
    assert isinstance(lens, snr.Optic)
    assert telescope.aperture == 0.279 * u.m
    assert telescope.focal_length == 62 * u.cm
    assert telescope.central_obstruction == 129 * u.mm


def test_camera(ccd):
    assert isinstance(ccd, snr.Camera)
    assert ccd.saturation_level == min(25500 * u.electron / u.pixel,
                                       (((2**16 - 1) - 1100) * 0.37 * u.electron / u.pixel))
    assert ccd.max_noise == (ccd.saturation_level * u.electron / u.pixel + (9.3 * u.electron / u.pixel)**2)**0.5


def test_filter(bandpass):
    assert isinstance(bandpass, snr.Filter)
    assert bandpass.sky_mu == 22.5 * u.ABmag


def test_psf_base():
    with pytest.raises(TypeError):
        # Try to instantiate abstract base class, should fail
        psf_base = snr.PSF(FWHM=1 / 30 * u.arcminute)


def test_psf_moffat(psf):
    assert isinstance(psf, snr.Moffat_PSF)
    assert isinstance(psf, snr.PSF)
    assert psf.FWHM == 2 * u.arcsecond
    psf.pixel_scale = 2.85 * u.arcsecond / u.pixel
    assert psf.pixel_scale == 2.85 * u.arcsecond / u.pixel
    assert psf.n_pix == 4.25754067000986 * u.pixel
    assert psf.peak == 0.7134084656751443 / u.pixel


def test_imager_init(imager):
    assert isinstance(imager, snr.Imager)
    assert imager.pixel_scale == (5.4 * u.micron / (391 * u.mm * u.pixel)).to(u.arcsecond / u.pixel,
                                                                              equivalencies=u.dimensionless_angles())
    assert imager.pixel_area == (5.4 * u.micron /
                                 (391 * u.mm * u.pixel)).to(u.arcsecond / u.pixel,
                                                            equivalencies=u.dimensionless_angles())**2 * u.pixel
    assert (imager.field_of_view == (3326, 2504) * u.pixel * imager.pixel_scale).all()


def test_imager_extended_snr(imager):
    sb = 25 * u.ABmag
    t_exp = 28 * u.hour
    t_sub = 600 * u.second

    # Calculate signal to noise ratio given surface brightness and exposure time
    snr = imager.extended_source_snr(surface_brightness=sb,
                                     total_exp_time=t_exp,
                                     sub_exp_time=t_sub,
                                     calc_type='per arcsecond squared',
                                     saturation_check=True)

    # Calculating exposure time given surface brightness and calculated SNR should match original exposure time
    # SNR target reduced a tiny amount to prevent finite numerical precision causing exposure time to get rounded up.
    assert t_exp == imager.extended_source_etc(surface_brightness=sb,
                                               snr_target=snr * 0.999999999999,
                                               sub_exp_time=t_sub,
                                               calc_type='per arcsecond squared',
                                               saturation_check=True)

    # Calculating surface brightness given exposure time and SNR should match original surface brightness
    assert sb == imager.extended_source_limit(total_exp_time=t_exp,
                                              snr_target=snr,
                                              sub_exp_time=t_sub,
                                              calc_type='per arcsecond squared')

    # Can't use pixel binning with per arcsecond squared signal, noise values
    with pytest.raises(ValueError):
        imager.extended_source_signal_noise(surface_brightness=sb,
                                            total_exp_time=t_exp,
                                            sub_exp_time=t_sub,
                                            calc_type='per arcsecond squared',
                                            saturation_check=True,
                                            binning=4)

    # Can't calculate signal to noise ratio per banana, either.
    with pytest.raises(ValueError):
        imager.extended_source_snr(surface_brightness=sb,
                                   total_exp_time=t_exp,
                                   sub_exp_time=t_sub,
                                   calc_type='per banana',
                                   saturation_check=False,
                                   binning=16)


def test_imager_extended_binning(imager):
    sb = 25 * u.ABmag
    t_exp = 28 * u.hour
    t_sub = 600 * u.second

    # Per pixel SNR shoudl scale with pixel binning^0.5
    snr_1_pix = imager.extended_source_snr(surface_brightness=sb,
                                           total_exp_time=t_exp,
                                           sub_exp_time=t_sub,
                                           calc_type='per pixel',
                                           saturation_check=False)
    snr_4_pix = imager.extended_source_snr(surface_brightness=sb,
                                           total_exp_time=t_exp,
                                           sub_exp_time=t_sub,
                                           calc_type='per pixel',
                                           saturation_check=False,
                                           binning=4)
    assert snr_4_pix == 2 * snr_1_pix

    # Binned exposure time given surface brightness and SNR should match original exposure time.
    assert t_exp == imager.extended_source_etc(surface_brightness=sb,
                                               snr_target=snr_4_pix,
                                               sub_exp_time=t_sub,
                                               saturation_check=False,
                                               binning=4)


def test_imager_extended_arrays(imager):
    # SNR functions should handle arrays values for any of the main arguments.
    assert len(imager.extended_source_snr(surface_brightness=(20.0, 25.0) * u.ABmag,
                                          total_exp_time=28 * u.hour,
                                          sub_exp_time=600 * u.second)) == 2

    assert len(imager.extended_source_snr(surface_brightness=25.0 * u.ABmag,
                                          total_exp_time=(10, 20, 30) * u.hour,
                                          sub_exp_time=(200, 400, 600) * u.second)) == 3

    assert len(imager.extended_source_etc(surface_brightness=25 * u.ABmag,
                                          snr_target=(3.0, 5.0),
                                          sub_exp_time=600 * u.second)) == 2

    assert len(imager.extended_source_etc(surface_brightness=25 * u.ABmag,
                                          snr_target=1.0,
                                          sub_exp_time=(200, 400, 600) * u.second)) == 3

    assert len(imager.extended_source_limit(total_exp_time=(20, 30) * u.hour,
                                            snr_target=1.0,
                                            sub_exp_time=600 * u.second)) == 2

    assert len(imager.extended_source_limit(total_exp_time=28 * u.hour,
                                            snr_target=(3.0, 5.0),
                                            sub_exp_time=(300, 600) * u.second)) == 2


def test_imager_extended_rates(imager):
    # SNR function optionally accept electrons / pixel per second instead of AB mag per arcsecond^2
    rate = 0.1 * u.electron / (u.pixel * u.second)
    t_exp = 28 * u.hour
    t_sub = 600 * u.second

    # Calculate signal to noise ratio given surface brightness and exposure time
    snr = imager.extended_source_snr(surface_brightness=rate,
                                     total_exp_time=t_exp,
                                     sub_exp_time=t_sub,
                                     calc_type='per arcsecond squared',
                                     saturation_check=True)

    # Calculating exposure time given surface brightness and calculated SNR should match original exposure time
    # SNR target reduced a tiny amount to prevent finite numerical precision causing exposure time to get rounded up.
    assert t_exp == imager.extended_source_etc(surface_brightness=rate,
                                               snr_target=snr * 0.999999999999,
                                               sub_exp_time=t_sub,
                                               calc_type='per arcsecond squared',
                                               saturation_check=True)

    # Calculating surface brightness given exposure time and SNR should match original surface brightness
    assert imager.rate_to_SB(rate) == imager.extended_source_limit(total_exp_time=t_exp,
                                                                   snr_target=snr,
                                                                   sub_exp_time=t_sub,
                                                                   calc_type='per arcsecond squared')

    # Can't use pixel binning with per arcsecond squared signal, noise values
    with pytest.raises(ValueError):
        imager.extended_source_signal_noise(surface_brightness=rate,
                                            total_exp_time=t_exp,
                                            sub_exp_time=t_sub,
                                            calc_type='per arcsecond squared',
                                            saturation_check=True,
                                            binning=4)


def test_imager_point_snr(imager):
    b = 25 * u.ABmag
    t_exp = 28 * u.hour
    t_sub = 600 * u.second

    # Calculate signal to noise ratio given brightness and exposure time
    snr = imager.point_source_snr(brightness=b,
                                  total_exp_time=t_exp,
                                  sub_exp_time=t_sub,
                                  saturation_check=True)

    # Calculating exposure time given brightness and calculated SNR should match original exposure time
    # SNR target reduced a tiny amount to prevent finite numerical precision causing exposure time to get rounded up.
    assert t_exp == imager.point_source_etc(brightness=b,
                                            snr_target=snr * 0.999999999999,
                                            sub_exp_time=t_sub,
                                            saturation_check=True)

    # Calculating brightness given exposure time and SNR should match original brightness
    assert b == imager.point_source_limit(total_exp_time=t_exp,
                                          snr_target=snr,
                                          sub_exp_time=t_sub)


def test_imager_point_arrays(imager):
    # SNR functions should handle arrays values for any of the main arguments.
    assert len(imager.point_source_snr(brightness=(20.0, 25.0) * u.ABmag,
                                       total_exp_time=28 * u.hour,
                                       sub_exp_time=600 * u.second)) == 2

    assert len(imager.point_source_snr(brightness=25.0 * u.ABmag,
                                       total_exp_time=(10, 20, 30) * u.hour,
                                       sub_exp_time=(200, 400, 600) * u.second)) == 3

    assert len(imager.point_source_etc(brightness=25 * u.ABmag,
                                       snr_target=(3.0, 5.0),
                                       sub_exp_time=600 * u.second)) == 2

    assert len(imager.point_source_etc(brightness=25 * u.ABmag,
                                       snr_target=1.0,
                                       sub_exp_time=(200, 400, 600) * u.second)) == 3

    assert len(imager.point_source_limit(total_exp_time=(20, 30) * u.hour,
                                         snr_target=1.0,
                                         sub_exp_time=600 * u.second)) == 2

    assert len(imager.point_source_limit(total_exp_time=28 * u.hour,
                                         snr_target=(3.0, 5.0),
                                         sub_exp_time=(300, 600) * u.second)) == 2


def test_imager_point_rates(imager):
    rate = 0.1 * u.electron / u.second
    t_exp = 28 * u.hour
    t_sub = 600 * u.second

    # Calculate signal to noise ratio given brightness and exposure time
    snr = imager.point_source_snr(brightness=rate,
                                  total_exp_time=t_exp,
                                  sub_exp_time=t_sub,
                                  saturation_check=True)

    # Calculating exposure time given brightness and calculated SNR should match original exposure time
    # SNR target reduced a tiny amount to prevent finite numerical precision causing exposure time to get rounded up.
    assert t_exp == imager.point_source_etc(brightness=rate,
                                            snr_target=snr * 0.999999999999,
                                            sub_exp_time=t_sub,
                                            saturation_check=True)

    # Calculating brightness given exposure time and SNR should match original brightness.
    # This particular comparison seems to fail due to floating point accuracy, need to allow some tolerance.
    assert imager.rate_to_ABmag(rate).value == pytest.approx(imager.point_source_limit(total_exp_time=t_exp,
                                                                                       snr_target=snr,
                                                                                       sub_exp_time=t_sub).value,
                                                             abs=1e-14)


def test_imager_exposure(imager):
    t_elapsed = 2700 * u.second
    t_sub = 600 * u.second
    t_exp = imager.total_exposure_time(t_elapsed, t_sub)
    assert t_exp == 4 * t_sub


def test_imager_elapsed(imager):
    exp_list = (150, 300, 600, 600) * u.second
    t_elapsed = imager.total_elapsed_time(exp_list)
    assert t_elapsed == 1650 * u.second + 4 * imager.num_per_computer * imager.camera.readout_time


def test_imager_extended_sat_mag(imager):
    t_exp = 28 * u.hour
    t_sub = 600 * u.second
    sat_mag = imager.extended_source_saturation_mag(sub_exp_time=t_sub)

    assert imager.extended_source_snr(surface_brightness=sat_mag.value - 0.01,
                                      total_exp_time=t_exp,
                                      sub_exp_time=t_sub) == 0 * u.dimensionless_unscaled

    assert imager.extended_source_snr(surface_brightness=sat_mag.value + 0.01,
                                      total_exp_time=t_exp,
                                      sub_exp_time=t_sub) != 0 * u.dimensionless_unscaled

    assert imager.extended_source_snr(surface_brightness=sat_mag.value - 0.01,
                                      total_exp_time=t_exp,
                                      sub_exp_time=t_sub,
                                      saturation_check=False) != 0 * u.dimensionless_unscaled

    assert imager.extended_source_etc(surface_brightness=sat_mag.value - 0.01,
                                      snr_target=3.0,
                                      sub_exp_time=t_sub) == 0 * u.second

    assert imager.extended_source_etc(surface_brightness=sat_mag.value + 0.01,
                                      snr_target=3.0,
                                      sub_exp_time=t_sub) != 0 * u.second

    assert imager.extended_source_etc(surface_brightness=sat_mag.value - 0.01,
                                      snr_target=3.0,
                                      sub_exp_time=t_sub,
                                      saturation_check=False) != 0 * u.second


def test_imager_extended_sat_exp(imager):
    sb = 10 * u.ABmag
    t_exp = 28 * u.hour
    sat_exp = imager.extended_source_saturation_exp(surface_brightness=sb)

    assert imager.extended_source_snr(surface_brightness=sb,
                                      total_exp_time=t_exp,
                                      sub_exp_time=sat_exp * 1.01) == 0 * u.dimensionless_unscaled

    assert imager.extended_source_snr(surface_brightness=sb,
                                      total_exp_time=t_exp,
                                      sub_exp_time=sat_exp * 0.99) != 0 * u.dimensionless_unscaled

    assert imager.extended_source_snr(surface_brightness=sb,
                                      total_exp_time=t_exp,
                                      sub_exp_time=sat_exp * 1.01,
                                      saturation_check=False) != 0 * u.dimensionless_unscaled

    assert imager.extended_source_etc(surface_brightness=sb,
                                      snr_target=3.0,
                                      sub_exp_time=sat_exp * 1.01) == 0 * u.second

    assert imager.extended_source_etc(surface_brightness=sb,
                                      snr_target=3.0,
                                      sub_exp_time=sat_exp * 0.99) != 0 * u.second

    assert imager.extended_source_etc(surface_brightness=sb,
                                      snr_target=3.0,
                                      sub_exp_time=sat_exp * 1.01,
                                      saturation_check=False) != 0 * u.second

    assert imager.extended_source_saturation_mag(sub_exp_time=sat_exp) == sb


def test_imager_point_sat_mag(imager):
    t_exp = 28 * u.hour
    t_sub = 600 * u.second
    sat_mag = imager.point_source_saturation_mag(sub_exp_time=t_sub)

    assert imager.point_source_snr(brightness=sat_mag.value - 0.01,
                                   total_exp_time=t_exp,
                                   sub_exp_time=t_sub) == 0 * u.dimensionless_unscaled

    assert imager.point_source_snr(brightness=sat_mag.value + 0.01,
                                   total_exp_time=t_exp,
                                   sub_exp_time=t_sub) != 0 * u.dimensionless_unscaled

    assert imager.point_source_snr(brightness=sat_mag.value - 0.01,
                                   total_exp_time=t_exp,
                                   sub_exp_time=t_sub,
                                   saturation_check=False) != 0 * u.dimensionless_unscaled

    assert imager.point_source_etc(brightness=sat_mag.value - 0.01,
                                   snr_target=3.0,
                                   sub_exp_time=t_sub) == 0 * u.second

    assert imager.point_source_etc(brightness=sat_mag.value + 0.01,
                                   snr_target=3.0,
                                   sub_exp_time=t_sub) != 0 * u.second

    assert imager.point_source_etc(brightness=sat_mag.value - 0.01,
                                   snr_target=3.0,
                                   sub_exp_time=t_sub,
                                   saturation_check=False) != 0 * u.second


def test_imager_point_sat_exp(imager):
    b = 10 * u.ABmag
    t_exp = 28 * u.hour
    sat_exp = imager.point_source_saturation_exp(brightness=b)

    assert imager.point_source_snr(brightness=b,
                                   total_exp_time=t_exp,
                                   sub_exp_time=sat_exp * 1.01) == 0 * u.dimensionless_unscaled

    assert imager.point_source_snr(brightness=b,
                                   total_exp_time=t_exp,
                                   sub_exp_time=sat_exp * 0.99) != 0 * u.dimensionless_unscaled

    assert imager.point_source_snr(brightness=b,
                                   total_exp_time=t_exp,
                                   sub_exp_time=sat_exp * 1.01,
                                   saturation_check=False) != 0 * u.dimensionless_unscaled

    assert imager.point_source_etc(brightness=b,
                                   snr_target=3.0,
                                   sub_exp_time=sat_exp * 1.01) == 0 * u.second

    assert imager.point_source_etc(brightness=b,
                                   snr_target=3.0,
                                   sub_exp_time=sat_exp * 0.99) != 0 * u.second

    assert imager.point_source_etc(brightness=b,
                                   snr_target=3.0,
                                   sub_exp_time=sat_exp * 1.01,
                                   saturation_check=False) != 0 * u.second

    assert imager.point_source_saturation_mag(sub_exp_time=sat_exp) == b


def test_imager_sequence(imager):
    brightest = 10 * u.ABmag
    ratio = 2.0
    t_max = 600 * u.second
    faintest = 25 * u.ABmag

    t_exps = imager.exp_time_sequence(bright_limit=brightest,
                                      exp_time_ratio=ratio,
                                      longest_exp_time=t_max,
                                      faint_limit=faintest)

    # Shortest exposure time should be less than the time to saturation on the brightest targets
    assert t_exps[0] <= imager.point_source_saturation_exp(brightness=brightest)

    # Ratio between exposures should be close to exp_time_ratio (apart from rounding to nearest 0.01 seconds)
    assert (t_exps[1] / t_exps[0]).value == pytest.approx(2, rel=0.1)

    # Total exposure time should be close to the required exposure time for a non-HDR sequence reaching the same
    # depth.
    non_hdr_t_exp = imager.point_source_etc(brightness=faintest,
                                            snr_target=5.0,
                                            sub_exp_time=t_max)
    assert t_exps.sum() > non_hdr_t_exp
    assert t_exps.sum().value == pytest.approx(non_hdr_t_exp.value, abs=t_max.value)

    # Can't set both num_long_exp and faint_limit
    with pytest.raises(ValueError):
        imager.exp_time_sequence(bright_limit=brightest,
                                 exp_time_ratio=ratio,
                                 longest_exp_time=t_max,
                                 num_long_exp=5,
                                 faint_limit=faintest)
    # Or neither
    with pytest.raises(ValueError):
        imager.exp_time_sequence(bright_limit=brightest,
                                 exp_time_ratio=ratio,
                                 longest_exp_time=t_max)

    # If given a really bright target then shortest exposure should just be close to the minimum that the camera
    # is capabable off.
    t_exps_bright = imager.exp_time_sequence(bright_limit=-10 * u.ABmag,
                                             exp_time_ratio=ratio,
                                             longest_exp_time=t_max,
                                             faint_limit=faintest)

    assert t_exps_bright[0] >= imager.camera.minimum_exposure
    assert t_exps_bright[0].value == pytest.approx(imager.camera.minimum_exposure.value, rel=ratio)

    # If given a faint minimum magnitude (won't saturate in longest subs) then should return a non-HDR sequence.
    t_exps = imager.exp_time_sequence(bright_limit=20 * u.ABmag,
                                      exp_time_ratio=ratio,
                                      longest_exp_time=t_max,
                                      faint_limit=faintest)
    assert (t_exps == t_max).all()

    # Can instead specify number of long exposures directly.
    t_exps_n_long = imager.exp_time_sequence(bright_limit=brightest,
                                             exp_time_ratio=ratio,
                                             longest_exp_time=t_max,
                                             num_long_exp=3)
    assert (t_exps_n_long == t_max).sum() == 3

    # Can also directly specify the shortest exposure time. Will get rounded down to next integer exponent of the
    # exposure time ratio.
    t_exps_short = imager.exp_time_sequence(shortest_exp_time=100 * u.second,
                                            exp_time_ratio=ratio,
                                            longest_exp_time=t_max,
                                            num_long_exp=3)
    assert t_exps_short[0] == 75 * u.second

    # Can't specicify both bright_limit and shortest_exp_time
    with pytest.raises(ValueError):
        imager.exp_time_sequence(bright_limit=brightest,
                                 shortest_exp_time=100 * u.second,
                                 exp_time_ratio=ratio,
                                 longest_exp_time=t_max,
                                 num_long_exp=3)

    # Or neither
    with pytest.raises(ValueError):
        imager.exp_time_sequence(exp_time_ratio=ratio,
                                 longest_exp_time=t_max,
                                 num_long_exp=3)

    # Can override default SNR target of 5.0.
    t_exps_low_snr = imager.exp_time_sequence(bright_limit=brightest,
                                              exp_time_ratio=ratio,
                                              longest_exp_time=t_max,
                                              faint_limit=faintest,
                                              snr_target=2.5)
    assert t_exps_low_snr.sum().value == pytest.approx(t_exps.sum().value / 4, rel=0.02)


def test_imager_snr_vs_mag(imager, tmpdir):
    exp_times = imager.exp_time_sequence(shortest_exp_time=100 * u.second,
                                         exp_time_ratio=2,
                                         longest_exp_time=600 * u.second,
                                         num_long_exp=4)

    # Basic usage
    mags, snrs = imager.snr_vs_ABmag(exp_times=exp_times)

    # With plot
    plot_path = tmpdir.join('snr_vs_mag_test.png')
    mags, snrs = imager.snr_vs_ABmag(exp_times=exp_times, plot=plot_path.strpath)
    assert plot_path.check()

    # Finer sampling
    mags2, snrs2 = imager.snr_vs_ABmag(exp_times=exp_times, magnitude_interval=0.01 * u.ABmag)
    assert len(mags2) == pytest.approx(len(mags) * 2, abs=1)

    # Different signal to noise threshold
    mags3, snrs3 = imager.snr_vs_ABmag(exp_times=exp_times, snr_target=10.0)
    # Roughly background limited at faint end, 10 times higher SNR should be about 2.5 mag brighter
    assert mags3[-1].value == pytest.approx(mags[-1].value - 2.5, abs=0.1)


def test_create_imagers():
    imagers = snr.create_imagers()
    assert isinstance(imagers, dict)
    for key, value in imagers.items():
        assert type(key) == str
        assert isinstance(value, snr.Imager)
