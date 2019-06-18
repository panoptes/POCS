import pytest

from matplotlib.figure import Figure
from panoptes.utils.images import polar_alignment as pa_utils


@pytest.fixture
def pole_fits_file(data_dir):
    return '{}/pole.fits'.format(data_dir)


@pytest.fixture
def rotate_fits_file(data_dir):
    return '{}/rotation.fits'.format(data_dir)


def test_analyze_polar(pole_fits_file):
    x, y = pa_utils.analyze_polar_rotation(pole_fits_file)

    # Note that fits file has been cropped but values are
    # based on the full WCS
    assert x == pytest.approx(2885.621843270767)
    assert y == pytest.approx(1897.7483982446474)


def test_analyze_rotation(rotate_fits_file):
    x, y = pa_utils.analyze_ra_rotation(rotate_fits_file)

    assert x == pytest.approx(187)
    assert y == pytest.approx(25)


def test_plot_center(pole_fits_file, rotate_fits_file):
    pole_center = pa_utils.analyze_polar_rotation(pole_fits_file)
    rotate_center = pa_utils.analyze_ra_rotation(rotate_fits_file)

    fig = pa_utils.plot_center(
        pole_fits_file,
        rotate_fits_file,
        pole_center,
        rotate_center
    )
    assert isinstance(fig, Figure)
