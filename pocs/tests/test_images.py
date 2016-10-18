import os
import pytest
import shutil

from pocs.images import Image
from pocs.images import PointingError
from pocs.utils.error import SolveError

from astropy.coordinates import SkyCoord

can_solve = pytest.mark.skipif(
    not pytest.config.getoption("--solve"),
    reason="need --camera to observe"
)


@pytest.fixture
def unsolved_fits_file(data_dir):
    return '{}/unsolved.fits'.format(data_dir)


@pytest.fixture
def solved_fits_file(data_dir):
    return '{}/solved.fits'.format(data_dir)


@pytest.fixture
def tiny_fits_file(data_dir):
    return '{}/tiny.fits'.format(data_dir)


@pytest.fixture
def noheader_fits_file(data_dir):
    return '{}/noheader.fits'.format(data_dir)


def test_fits_exists(unsolved_fits_file):
    with pytest.raises(AssertionError):
        Image(unsolved_fits_file.replace('.fits', '.fit'))


def test_fits_extension():
    with pytest.raises(AssertionError):
        Image('{}/pocs/images.py'.format(os.getenv('POCS')))


def test_fits_noheader(noheader_fits_file):
    with pytest.raises(AssertionError):
        Image(noheader_fits_file)


def test_fail_solve(tiny_fits_file):
    im0 = Image(tiny_fits_file)

    with pytest.raises(SolveError):
        im0.solve_field(verbose=True, replace=False, radius=4)


@can_solve
def test_solve_field_unsolved(unsolved_fits_file):
    im0 = Image(unsolved_fits_file)

    assert isinstance(im0, Image)
    assert im0.wcs is None
    assert im0.pointing is None

    im0.solve_field(verbose=True, replace=False, radius=4)

    assert im0.wcs is not None
    assert im0.wcs_file is not None
    assert isinstance(im0.pointing, SkyCoord)
    assert im0.RA is not None
    assert im0.Dec is not None
    assert im0.HA is not None

    # Remove extra files
    os.remove(unsolved_fits_file.replace('.fits', '.solved'))
    os.remove(unsolved_fits_file.replace('.fits', '.new'))


@can_solve
def test_solve_field_solved(solved_fits_file):
    im0 = Image(solved_fits_file)

    assert isinstance(im0, Image)
    assert im0.wcs is not None
    assert im0.wcs_file is not None
    assert im0.pointing is not None
    assert im0.RA is not None
    assert im0.Dec is not None
    assert im0.HA is not None

    im0.solve_field(verbose=True, radius=4)

    assert isinstance(im0.pointing, SkyCoord)


def test_pointing_error_no_wcs(unsolved_fits_file):
    im0 = Image(unsolved_fits_file)

    with pytest.raises(AssertionError):
        im0.pointing_error


def test_pointing_error_passed_wcs(unsolved_fits_file, solved_fits_file):
    im0 = Image(unsolved_fits_file, wcs_file=solved_fits_file)

    assert isinstance(im0.pointing_error, PointingError)


def test_pointing_error(solved_fits_file):
    im0 = Image(solved_fits_file)

    im0.solve_field(verbose=True, replace=False, radius=4)

    perr = im0.pointing_error
    assert isinstance(perr, PointingError)

    assert (perr.delta_ra.value - 1.647535444553057) < 1e-5
    assert (perr.delta_dec.value - 1.560722632731533) < 1e-5
    assert (perr.magnitude.value - 1.9445870862060288) < 1e-5


def test_compute_offset_arcsec(solved_fits_file, unsolved_fits_file):
    img0 = Image(solved_fits_file)
    img1 = Image(unsolved_fits_file)

    offset_info = img0.compute_offset(img1)

    assert offset_info['offsetX'] - 3.9686712667745043 < 1e-5
    assert offset_info['offsetY'] - 17.585827075244445 < 1e-5


def test_compute_offset_pixel(solved_fits_file, unsolved_fits_file):
    img0 = Image(solved_fits_file)
    img1 = Image(unsolved_fits_file)

    offset_info = img0.compute_offset(img1, units='pixel')

    assert offset_info['offsetX'] == 1.7
    assert offset_info['offsetY'] == 0.4

    offset_info_opposite = img1.compute_offset(img0, units='pixel')

    assert offset_info_opposite['offsetX'] == -1 * offset_info['offsetX']
    assert offset_info_opposite['offsetY'] == -1 * offset_info['offsetY']


def test_compute_offset_string(solved_fits_file, unsolved_fits_file):
    img0 = Image(solved_fits_file)

    offset_info = img0.compute_offset(unsolved_fits_file)

    assert offset_info['offsetX'] - 3.9686712667745043 < 1e-5
    assert offset_info['offsetY'] - 17.585827075244445 < 1e-5
