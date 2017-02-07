import pytest

from pocs.camera.simulator import Camera as SimCamera
from pocs.camera.sbig import Camera as SBIGCamera
from pocs.camera.sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE
from pocs.focuser.simulator import Focuser
from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation
from pocs.utils.config import load_config
from pocs.utils.error import NotFound

import os
import time
from ctypes.util import find_library

import astropy.units as u
import astropy.io.fits as fits

params = [SimCamera, SBIGCamera]
ids = ['simulator', 'sbig']


# Ugly hack to access id inside fixture
@pytest.fixture(scope='module', params=zip(params, ids), ids=ids)
def camera(request):
    if request.param[0] == SimCamera:
        return request.param[0]()
    else:
        # Load the local config file and look for camera configurations of the specified type
        configs = []
        local_config = load_config('pocs_local', ignore_local=True)
        camera_info = local_config.get('cameras')
        if camera_info:
            # Local config file has a cameras section
            camera_configs = camera_info.get('devices')
            if camera_configs:
                # Local config file camera section has a devices list
                for camera_config in camera_configs:
                    if camera_config['model'] == request.param[1]:
                        # Camera config is the right type
                        configs.append(camera_config)

        if not configs:
            pytest.skip("Found no {} configurations in pocs_local.yaml, skipping tests".format(request.param[1]))

        # Create and return an camera based on the first config
        return request.param[0](**configs[0])

# Hardware independant tests, mostly use simulator:


def test_sim_create_focuser():
    sim_camera = SimCamera(focuser={'model': 'simulator', 'focus_port': '/dev/ttyFAKE'})
    assert isinstance(sim_camera.focuser, Focuser)


def test_sim_passed_focuser():
    sim_focuser = Focuser(port='/dev/ttyFAKE')
    sim_camera = SimCamera(focuser=sim_focuser)
    assert sim_camera.focuser is sim_focuser


def test_sim_bad_focuser():
    with pytest.raises((AttributeError, ImportError, NotFound)):
        sim_camera = SimCamera(focuser={'model': 'NOTAFOCUSER'})


def test_sim_worse_focuser():
    sim_camera = SimCamera(focuser='NOTAFOCUSER')
    # Will log an error but raise no exceptions
    assert sim_camera.focuser is None


def test_sim_string():
    sim_camera = SimCamera()
    assert str(sim_camera) == 'Generic Camera (999999) on None'
    sim_camera = SimCamera(name='Sim', port='/dev/ttyFAKE')
    assert str(sim_camera) == 'Sim (999999) on /dev/ttyFAKE'


def test_sim_file_extension():
    sim_camera = SimCamera()
    assert sim_camera.file_extension == 'fits'
    sim_camera = SimCamera(file_extension='FIT')
    assert sim_camera.file_extension == 'FIT'


def test_sim_readout_time():
    sim_camera = SimCamera()
    assert sim_camera.readout_time == 5.0
    sim_camera = SimCamera(readout_time=2.0)
    assert sim_camera.readout_time == 2.0


def test_sbig_driver_bad_path():
    """
    Manually specify an incorrect path for the SBIG shared library. The CDLL loader should raise OSError when it fails.
    Can't test a successful driver init as it would cause subsequent tests to fail because of the CDLL unload problem.
    """
    with pytest.raises(OSError):
        sbig_driver = SBIGDriver(library_path='no_library_here')


def test_sbig_bad_serial():
    """
    Attempt to create an SBIG camera instance for a specific non-existent camera. No actual cameras are required to
    run this test but the SBIG driver does need to be installed.
    """
    if find_library('sbigudrv') is None:
        pytest.skip("Test requires SBIG camera driver to be installed")
    camera = SBIGCamera(port='NOTAREALSERIALNUMBER')
    assert camera._connected is False
    if isinstance(camera, SBIGCamera):
        assert camera._handle == INVALID_HANDLE_VALUE

# *Potentially* hardware dependant tests:


def test_init(camera):
    """
    Test that camera got initialised as expected
    """
    if isinstance(camera, SimCamera):
        # Simulator Camera doesn't connect() on init
        assert camera.is_connected is False
        camera.connect()

    assert camera.is_connected

    if isinstance(camera, SBIGCamera):
        # Successfully initialised SBIG cameras should also have a valid 'handle'
        assert camera._handle != INVALID_HANDLE_VALUE


def test_uid(camera):
    # Camera uid should be a string (or maybe an int?) of non-zero length. Assert True
    assert camera.uid


def test_get_set_set_point(camera):
    """
    Tests the getters & setters for CCD cooling set point
    """
    # Set set point to 10C
    try:
        camera.CCD_set_point = 10 * u.Celsius
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))
    else:
        assert abs(camera.CCD_set_point - 10 * u.Celsius) < 0.5 * u.Celsius
        assert camera.CCD_cooling_enabled is True

    # Disable cooling
    try:
        camera.CCD_set_point = None
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))
    else:
        assert abs(camera.CCD_set_point - 25 * u.Celsius) < 0.5 * u.Celsius
        assert camera.CCD_cooling_enabled is False


def test_exposure(camera, tmpdir):
    """
    Tests basic take_exposure functionality
    """
    fits_path = str(tmpdir.join('test_exposure.fits'))
    # A one second normal exposure.
    camera.take_exposure(filename=fits_path)
    # By default take_exposure is non-blocking, need to give it some time to complete.
    time.sleep(5)
    if not isinstance(camera, SimCamera):
        # The simulator doesn't create any files but other cameras should.
        assert os.path.exists(fits_path)
        # If can retrieve some header data there's a good chance it's a valid FITS file
        header = fits.getheader(fits_path)
        assert header['EXPTIME'] == 1.0
        assert header['IMAGETYP'] == 'Light Frame'


def test_exposure_blocking(camera, tmpdir):
    """
    Tests blocking take_exposure functionality. At least for now only SBIG cameras do this.
    """
    if isinstance(camera, SimCamera):
        pytest.skip("Camera {} doesn't implement blocking in take_exposure()".format(camera.name))

    fits_path = str(tmpdir.join('test_exposure_blocking.fits'))
    # A one second exposure, command should block until complete so FITS should exist immediately afterwards
    camera.take_exposure(filename=fits_path, blocking=True)
    assert os.path.exists(fits_path)
    # If can retrieve some header data there's a good chance it's a valid FITS file
    header = fits.getheader(fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Light Frame'


def test_exposure_dark(camera, tmpdir):
    """
    Tests taking a dark. At least for now only SBIG cameras do this.
    """
    if isinstance(camera, SimCamera):
        pytest.skip("Camera {} doesn't implement darks in take_exposure()".format(camera.name))

    fits_path = str(tmpdir.join('test_exposure_dark.fits'))
    # A 1 second dark exposure
    camera.take_exposure(filename=fits_path, dark=True, blocking=True)
    assert os.path.exists(fits_path)
    # If can retrieve some header data there's a good chance it's a valid FITS file
    header = fits.getheader(fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Dark Frame'


def test_exposure_collision(camera, tmpdir):
    """
    Tests attempting to take an exposure while one is already in progress.
    With the SBIG cameras this will generate warning but still should work. Don't do this though!
    """
    fits_path_1 = str(tmpdir.join('test_exposure_collision1.fits'))
    fits_path_2 = str(tmpdir.join('test_exposure_collision2.fits'))
    camera.take_exposure(2 * u.second, filename=fits_path_1)
    camera.take_exposure(1 * u.second, filename=fits_path_2)
    time.sleep(5)
    if not isinstance(camera, SimCamera):
        # The simulator doesn't actually create any files but other cameras should
        assert os.path.exists(fits_path_1)
        assert os.path.exists(fits_path_2)
        assert fits.getval(fits_path_1, 'EXPTIME') == 2.0
        assert fits.getval(fits_path_2, 'EXPTIME') == 1.0


def test_observation(camera, tmpdir):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')
    observation = Observation(field, exp_time=1.5 * u.second)
    camera.take_observation(observation, headers={})
