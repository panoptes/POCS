import os
import pytest

from pocs.images import Image
from pocs.images import OffsetError
from pocs.utils.error import SolveError
from pocs.utils.error import Timeout

from astropy import units as u
from astropy.coordinates import SkyCoord


@pytest.fixture
def unsolved_fits_file(data_dir):
    return os.path.join(data_dir, 'unsolved.fits')


@pytest.fixture
def solved_fits_file(data_dir):
    return os.path.join(data_dir, 'solved.fits.fz')


@pytest.fixture
def tiny_fits_file(data_dir):
    return os.path.join(data_dir, 'tiny.fits')


@pytest.fixture
def noheader_fits_file(data_dir):
    return os.path.join(data_dir, 'noheader.fits')


def test_fits_exists(unsolved_fits_file):
    with pytest.raises(AssertionError):
        Image(unsolved_fits_file.replace('.fits', '.fit'))


def test_fits_extension():
    with pytest.raises(AssertionError):
        Image(os.path.join(os.environ['POCS'], 'pocs', 'images.py'))


def test_fits_noheader(noheader_fits_file):
    with pytest.raises(AssertionError):
        Image(noheader_fits_file)


def test_solve_timeout(tiny_fits_file):
    im0 = Image(tiny_fits_file)

    with pytest.raises(Timeout):
        im0.solve_field(verbose=True, replace=False, radius=4, timeout=1)

    try:
        os.remove(tiny_fits_file.replace('.fits', '.axy'))
    except Exception:
        pass


def test_fail_solve(tiny_fits_file):
    im0 = Image(tiny_fits_file)

    with pytest.raises(SolveError):
        im0.solve_field(verbose=True, replace=False, radius=4)

    try:
        os.remove(tiny_fits_file.replace('.fits', '.axy'))
    except Exception:  # pragma: no cover
        pass


def test_solve_field_unsolved(unsolved_fits_file):
    im0 = Image(unsolved_fits_file)

    assert isinstance(im0, Image)
    assert im0.wcs is None
    assert im0.pointing is None

    im0.solve_field(verbose=True, replace=False, radius=4)

    assert im0.wcs is not None
    assert im0.wcs_file is not None
    assert isinstance(im0.pointing, SkyCoord)
    assert im0.ra is not None
    assert im0.dec is not None
    assert im0.ha is not None

    # Remove extra files
    os.remove(unsolved_fits_file.replace('.fits', '.solved'))
    os.remove(unsolved_fits_file.replace('.fits', '.new'))


def test_solve_field_solved(solved_fits_file):
    im0 = Image(solved_fits_file)

    assert isinstance(im0, Image)
    assert im0.wcs is not None
    assert im0.wcs_file is not None
    assert im0.pointing is not None
    assert im0.ra is not None
    assert im0.dec is not None
    assert im0.ha is not None

    im0.solve_field(verbose=True, radius=4)

    assert isinstance(im0.pointing, SkyCoord)


def test_pointing_error_no_wcs(unsolved_fits_file):
    im0 = Image(unsolved_fits_file)

    with pytest.raises(AssertionError):
        im0.pointing_error


def test_pointing_error_passed_wcs(unsolved_fits_file, solved_fits_file):
    im0 = Image(unsolved_fits_file, wcs_file=solved_fits_file)

    assert isinstance(im0.pointing_error, OffsetError)


def test_pointing_error(solved_fits_file):
    im0 = Image(solved_fits_file)

    im0.solve_field(verbose=True, replace=False, radius=4)

    perr = im0.pointing_error
    assert isinstance(perr, OffsetError)

    assert (perr.delta_ra.to(u.degree).value - 1.647535444553057) < 1e-5
    assert (perr.delta_dec.to(u.degree).value - 1.560722632731533) < 1e-5
    assert (perr.magnitude.to(u.degree).value - 1.9445870862060288) < 1e-5


# def test_compute_offset_arcsec(solved_fits_file, unsolved_fits_file):
#     img0 = Image(solved_fits_file)
#     img1 = Image(unsolved_fits_file)

#     offset_info = img0.compute_offset(img1)

#     assert offset_info['offsetX'] - 3.9686712667745043 < 1e-5
#     assert offset_info['offsetY'] - 17.585827075244445 < 1e-5


# def test_compute_offset_pixel(solved_fits_file, unsolved_fits_file):
#     img0 = Image(solved_fits_file)
#     img1 = Image(unsolved_fits_file)

#     offset_info = img0.compute_offset(img1, units='pixel')

#     assert offset_info['offsetX'] == 1.7
#     assert offset_info['offsetY'] == 0.4

#     offset_info_opposite = img1.compute_offset(img0, units='pixel')

#     assert offset_info_opposite['offsetX'] == -1 * offset_info['offsetX']
#     assert offset_info_opposite['offsetY'] == -1 * offset_info['offsetY']


# def test_compute_offset_string(solved_fits_file, unsolved_fits_file):
#     img0 = Image(solved_fits_file)

#     offset_info = img0.compute_offset(unsolved_fits_file)

#     assert offset_info['offsetX'] - 3.9686712667745043 < 1e-5
#     assert offset_info['offsetY'] - 17.585827075244445 < 1e-5
