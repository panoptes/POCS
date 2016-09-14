import os
import pytest

from pocs.images import Image
from pocs.images import PointingError
from pocs.utils.error import SolveError

from astropy.coordinates import SkyCoord


@pytest.fixture
def unsolved_fits_file(data_dir):
    return '{}/unsolved.fits'.format(data_dir)


@pytest.fixture
def solved_fits_file(data_dir):
    return '{}/solved.fits'.format(data_dir)


@pytest.fixture
def tiny_fits_file(data_dir):
    return '{}/tiny.fits'.format(data_dir)


def test_fits_exists(unsolved_fits_file):
    with pytest.raises(AssertionError):
        Image(unsolved_fits_file.replace('.fits', '.fit'))


def test_fits_extension():
    with pytest.raises(AssertionError):
        Image('{}/pocs/images.py'.format(os.getenv('POCS')))


def test_fail_solve(tiny_fits_file):
    im0 = Image(tiny_fits_file)

    with pytest.raises(SolveError):
        im0.solve_field(verbose=True, replace=False, radius=4)


def test_solve_field_unsolved(unsolved_fits_file):
    im0 = Image(unsolved_fits_file)

    assert isinstance(im0, Image)
    assert im0.wcs is None
    assert im0.pointing is None

    im0.solve_field(verbose=True, replace=False, radius=4)

    assert im0.wcs is not None
    assert isinstance(im0.pointing, SkyCoord)
    assert im0.RA is not None
    assert im0.Dec is not None
    assert im0.HA is not None

    # Remove extra files
    os.remove(unsolved_fits_file.replace('.fits', '.solved'))
    os.remove(unsolved_fits_file.replace('.fits', '.new'))


def test_solve_field_solved(solved_fits_file):
    im0 = Image(solved_fits_file)

    assert isinstance(im0, Image)
    assert im0.wcs is not None
    assert im0.pointing is not None
    assert im0.RA is not None
    assert im0.Dec is not None
    assert im0.HA is not None

    im0.solve_field(verbose=True, radius=4)

    assert isinstance(im0.pointing, SkyCoord)


def test_pointing_error(solved_fits_file):
    im0 = Image(solved_fits_file)

    im0.solve_field(verbose=True, replace=False, radius=4)

    perr = im0.pointing_error
    assert isinstance(perr, PointingError)

    assert (perr.delta_ra.value - 1.647535444553057) < 1e-5
    assert (perr.delta_dec.value - 1.560722632731533) < 1e-5
    assert (perr.magnitude.value - 1.9445870862060288) < 1e-5
