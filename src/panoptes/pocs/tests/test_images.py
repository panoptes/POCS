import os
import pytest
import shutil
import tempfile

from astropy import units as u
from astropy.coordinates import SkyCoord

from panoptes.pocs.images import Image
from panoptes.pocs.images import OffsetError
from panoptes.utils.error import SolveError
from panoptes.utils.error import Timeout


def copy_file_to_dir(to_dir, file):
    assert os.path.isfile(file)
    result = os.path.join(to_dir, os.path.basename(file))
    assert not os.path.exists(result)
    shutil.copy(file, to_dir)
    assert os.path.exists(result)
    return result


def test_fits_exists(dynamic_config_server, config_port, unsolved_fits_file):
    with pytest.raises(AssertionError):
        Image(unsolved_fits_file.replace('.fits', '.fit'), config_port=config_port)


def test_fits_extension(dynamic_config_server, config_port):
    with pytest.raises(AssertionError):
        Image(os.path.join(os.environ['POCS'], 'pocs', 'images.py'), config_port=config_port)


def test_fits_noheader(dynamic_config_server, config_port, noheader_fits_file):
    with pytest.raises(KeyError):
        Image(noheader_fits_file, config_port=config_port)


def test_solve_timeout(dynamic_config_server, config_port, tiny_fits_file):
    with tempfile.TemporaryDirectory() as tmpdir:
        tiny_fits_file = copy_file_to_dir(tmpdir, tiny_fits_file)
        im0 = Image(tiny_fits_file, config_port=config_port)
        assert str(im0)
        with pytest.raises(Timeout):
            im0.solve_field(verbose=True, replace=False, radius=4, timeout=1)


def test_fail_solve(dynamic_config_server, config_port, tiny_fits_file):
    with tempfile.TemporaryDirectory() as tmpdir:
        tiny_fits_file = copy_file_to_dir(tmpdir, tiny_fits_file)
        im0 = Image(tiny_fits_file, config_port=config_port)
        assert str(im0)
        with pytest.raises(SolveError):
            im0.solve_field(verbose=True, replace=False, radius=4)


def test_solve_field_unsolved(dynamic_config_server,
                              config_port,
                              unsolved_fits_file,
                              solved_fits_file):
    # We place the input images into a temp directory so that output images
    # are also in the temp directory.
    with tempfile.TemporaryDirectory() as tmpdir:
        im0 = Image(copy_file_to_dir(tmpdir, unsolved_fits_file), config_port=config_port)

        assert isinstance(im0, Image)
        assert im0.wcs is None
        assert im0.pointing is None

        im0.solve_field(verbose=True, replace=True, radius=4)

        assert im0.wcs is not None
        assert im0.wcs_file is not None
        assert isinstance(im0.pointing, SkyCoord)
        assert im0.ra is not None
        assert im0.dec is not None
        assert im0.ha is not None

        # Compare it to another file of known offset.
        im1 = Image(copy_file_to_dir(tmpdir, solved_fits_file), config_port=config_port)
        offset_info = im0.compute_offset(im1)
        # print('offset_info:', offset_info)
        expected_offset = [10.1 * u.arcsec, 5.29 * u.arcsec, 8.77 * u.arcsec]
        assert u.allclose(offset_info, expected_offset, rtol=0.005)


def test_solve_field_solved(dynamic_config_server, config_port, solved_fits_file):
    im0 = Image(solved_fits_file, config_port=config_port)

    assert isinstance(im0, Image)
    assert im0.wcs is not None
    assert im0.wcs_file is not None
    assert im0.pointing is not None
    assert im0.ra is not None
    assert im0.dec is not None
    assert im0.ha is not None

    im0.solve_field(verbose=True, radius=4)

    assert isinstance(im0.pointing, SkyCoord)


def test_pointing_error_no_wcs(dynamic_config_server, config_port, unsolved_fits_file):
    im0 = Image(unsolved_fits_file, config_port=config_port)

    with pytest.raises(AssertionError):
        im0.pointing_error


def test_pointing_error_passed_wcs(dynamic_config_server,
                                   config_port,
                                   unsolved_fits_file,
                                   solved_fits_file):
    im0 = Image(unsolved_fits_file, wcs_file=solved_fits_file, config_port=config_port)

    assert isinstance(im0.pointing_error, OffsetError)


def test_pointing_error(dynamic_config_server, config_port, solved_fits_file):
    im0 = Image(solved_fits_file, config_port=config_port)

    im0.solve_field(verbose=True, replace=False, radius=4)

    perr = im0.pointing_error
    assert isinstance(perr, OffsetError)

    assert (perr.delta_ra.to(u.degree).value - 1.647535444553057) < 1e-5
    assert (perr.delta_dec.to(u.degree).value - 1.560722632731533) < 1e-5
    assert (perr.magnitude.to(u.degree).value - 1.9445870862060288) < 1e-5
