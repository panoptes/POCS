import os
import time
import pytest
import shutil
import tempfile
import subprocess

from astropy import units as u
from astropy.coordinates import SkyCoord

from pocs import hardware
from pocs.images import Image
from pocs.images import OffsetError
from panoptes.utils.error import SolveError
from panoptes.utils.error import Timeout
from panoptes.utils.logger import get_root_logger
from panoptes.utils.config.client import set_config


@pytest.fixture(scope='module')
def config_port():
    return '4861'

# Override default config_server and use function scope so we can change some values cleanly.


@pytest.fixture(scope='function')
def config_server(config_path, config_host, config_port, images_dir, db_name):
    cmd = os.path.join(os.getenv('PANDIR'),
                       'panoptes-utils',
                       'scripts',
                       'run_config_server.py'
                       )
    args = [cmd, '--config-file', config_path,
            '--host', config_host,
            '--port', config_port,
            '--ignore-local',
            '--no-save']

    logger = get_root_logger()
    logger.debug(f'Starting config_server for testing function: {args!r}')

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.critical(f'config_server started with PID={proc.pid}')

    # Give server time to start
    time.sleep(1)

    # Adjust various config items for testing
    unit_name = 'Generic PANOPTES Unit'
    unit_id = 'PAN000'
    logger.debug(f'Setting testing name and unit_id to {unit_id}')
    set_config('name', unit_name, port=config_port)
    set_config('pan_id', unit_id, port=config_port)

    logger.debug(f'Setting testing database to {db_name}')
    set_config('db.name', db_name, port=config_port)

    fields_file = 'simulator.yaml'
    logger.debug(f'Setting testing scheduler fields_file to {fields_file}')
    set_config('scheduler.fields_file', fields_file, port=config_port)

    # TODO(wtgee): determine if we need separate directories for each module.
    logger.debug(f'Setting temporary image directory for testing')
    set_config('directories.images', images_dir, port=config_port)

    # Make everything a simulator
    set_config('simulator', hardware.get_simulator_names(simulator=['all']), port=config_port)

    yield
    logger.critical(f'Killing config_server started with PID={proc.pid}')
    proc.terminate()


def copy_file_to_dir(to_dir, file):
    assert os.path.isfile(file)
    result = os.path.join(to_dir, os.path.basename(file))
    assert not os.path.exists(result)
    shutil.copy(file, to_dir)
    assert os.path.exists(result)
    return result


def test_fits_exists(config_port, unsolved_fits_file):
    with pytest.raises(AssertionError):
        Image(unsolved_fits_file.replace('.fits', '.fit'), config_port=config_port)


def test_fits_extension(config_port):
    with pytest.raises(AssertionError):
        Image(os.path.join(os.environ['POCS'], 'pocs', 'images.py'), config_port=config_port)


def test_fits_noheader(config_port, noheader_fits_file):
    with pytest.raises(KeyError):
        Image(noheader_fits_file, config_port=config_port)


def test_solve_timeout(config_port, tiny_fits_file):
    with tempfile.TemporaryDirectory() as tmpdir:
        tiny_fits_file = copy_file_to_dir(tmpdir, tiny_fits_file)
        im0 = Image(tiny_fits_file, config_port=config_port)
        assert str(im0)
        with pytest.raises(Timeout):
            im0.solve_field(verbose=True, replace=False, radius=4, timeout=1)


def test_fail_solve(config_port, tiny_fits_file):
    with tempfile.TemporaryDirectory() as tmpdir:
        tiny_fits_file = copy_file_to_dir(tmpdir, tiny_fits_file)
        im0 = Image(tiny_fits_file, config_port=config_port)
        assert str(im0)
        with pytest.raises(SolveError):
            im0.solve_field(verbose=True, replace=False, radius=4)


def test_solve_field_unsolved(config_port, unsolved_fits_file, solved_fits_file):
    # We place the input images into a temp directory so that output images
    # are also in the temp directory.
    with tempfile.TemporaryDirectory() as tmpdir:
        im0 = Image(copy_file_to_dir(tmpdir, unsolved_fits_file), config_port=config_port)

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

        # Compare it to another file of known offset.
        im1 = Image(copy_file_to_dir(tmpdir, solved_fits_file), config_port=config_port)
        offset_info = im0.compute_offset(im1)
        # print('offset_info:', offset_info)
        expected_offset = [10.1 * u.arcsec, 5.29 * u.arcsec, 8.77 * u.arcsec]
        assert u.allclose(offset_info, expected_offset, rtol=0.005)


def test_solve_field_solved(config_port, solved_fits_file):
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


def test_pointing_error_no_wcs(config_port, unsolved_fits_file):
    im0 = Image(unsolved_fits_file, config_port=config_port)

    with pytest.raises(AssertionError):
        im0.pointing_error


def test_pointing_error_passed_wcs(config_port, unsolved_fits_file, solved_fits_file):
    im0 = Image(unsolved_fits_file, wcs_file=solved_fits_file, config_port=config_port)

    assert isinstance(im0.pointing_error, OffsetError)


def test_pointing_error(config_port, solved_fits_file):
    im0 = Image(solved_fits_file, config_port=config_port)

    im0.solve_field(verbose=True, replace=False, radius=4)

    perr = im0.pointing_error
    assert isinstance(perr, OffsetError)

    assert (perr.delta_ra.to(u.degree).value - 1.647535444553057) < 1e-5
    assert (perr.delta_dec.to(u.degree).value - 1.560722632731533) < 1e-5
    assert (perr.magnitude.to(u.degree).value - 1.9445870862060288) < 1e-5
