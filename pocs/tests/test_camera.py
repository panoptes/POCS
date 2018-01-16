import pytest

from pocs.camera.simulator import Camera as SimCamera
from pocs.camera.sbig import Camera as SBIGCamera
from pocs.camera.sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE
from pocs.camera.fli import Camera as FLICamera
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

params = [SimCamera, SBIGCamera, FLICamera]
ids = ['simulator', 'sbig', 'fli']


@pytest.fixture(scope='module')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    return str(directory)


# Ugly hack to access id inside fixture
@pytest.fixture(scope='module', params=zip(params, ids), ids=ids)
def camera(request, images_dir):
    if request.param[0] == SimCamera:
        camera = request.param[0](focuser={'model': 'simulator',
                                           'focus_port': '/dev/ttyFAKE',
                                           'initial_position': 20000,
                                           'autofocus_range': (40, 80),
                                           'autofocus_step': (10, 20),
                                           'autofocus_seconds': 0.1,
                                           'autofocus_size': 500,
                                           'autofocus_keep_files': False})
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
            pytest.skip(
                "Found no {} configs in pocs_local.yaml, skipping tests".format(request.param[1]))

        # Create and return an camera based on the first config
        camera = request.param[0](**configs[0])

    camera.config['directories']['images'] = images_dir
    return camera

# Hardware independent tests, mostly use simulator:


def test_sim_create_focuser():
    sim_camera = SimCamera(focuser={'model': 'simulator', 'focus_port': '/dev/ttyFAKE'})
    assert isinstance(sim_camera.focuser, Focuser)


def test_sim_passed_focuser():
    sim_focuser = Focuser(port='/dev/ttyFAKE')
    sim_camera = SimCamera(focuser=sim_focuser)
    assert sim_camera.focuser is sim_focuser


def test_sim_bad_focuser():
    with pytest.raises((AttributeError, ImportError, NotFound)):
        SimCamera(focuser={'model': 'NOTAFOCUSER'})


def test_sim_worse_focuser():
    sim_camera = SimCamera(focuser='NOTAFOCUSER')
    # Will log an error but raise no exceptions
    assert sim_camera.focuser is None


def test_sim_string():
    sim_camera = SimCamera()
    assert str(sim_camera) == 'Simulated Camera ({}) on None'.format(sim_camera.uid)
    sim_camera = SimCamera(name='Sim', port='/dev/ttyFAKE')
    assert str(sim_camera) == 'Sim ({}) on /dev/ttyFAKE'.format(sim_camera.uid)


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
    Manually specify an incorrect path for the SBIG shared library. The
    CDLL loader should raise OSError when it fails. Can't test a successful
    driver init as it would cause subsequent tests to fail because of the
    CDLL unload problem.
    """
    with pytest.raises(OSError):
        SBIGDriver(library_path='no_library_here')


def test_sbig_bad_serial():
    """
    Attempt to create an SBIG camera instance for a specific non-existent
    camera. No actual cameras are required to run this test but the SBIG
    driver does need to be installed.
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
    assert camera.is_connected

    if isinstance(camera, SBIGCamera):
        # Successfully initialised SBIG cameras should also have a valid 'handle'
        assert camera._handle != INVALID_HANDLE_VALUE


def test_uid(camera):
    # Camera uid should be a string (or maybe an int?) of non-zero length. Assert True
    assert camera.uid


def test_get_temp(camera):
    try:
        temperature = camera.CCD_temp
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature info".format(camera.name))
    else:
        assert temperature is not None


def test_get_set_point(camera):
    """
    Tests the getters for CCD cooling set point
    """
    try:
        set_point = camera.CCD_set_point
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))
    else:
        assert set_point is not None


def test_set_set_point(camera):
    # Set set point to 10C
    try:
        camera.CCD_set_point = 10 * u.Celsius
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))
    else:
        assert abs(camera.CCD_set_point - 10 * u.Celsius) < 0.5 * u.Celsius
        assert camera.CCD_cooling_enabled is True


def test_cooling_enabled(camera):
    try:
        cooling_enabled = camera.CCD_cooling_enabled
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))
    else:
        # If camera supported temperature control previous test will have enabled cooling.
        assert cooling_enabled is True


def test_disable_cooling(camera):
    # Disable cooling
    try:
        camera.CCD_set_point = None
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))
    else:
        assert abs(camera.CCD_set_point - 25 * u.Celsius) < 0.5 * u.Celsius
        assert camera.CCD_cooling_enabled is False


def test_get_cooling_power(camera):
    try:
        power = camera.CCD_cooling_power
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))
    else:
        assert power is not None


def test_exposure(camera, tmpdir):
    """
    Tests basic take_exposure functionality
    """
    fits_path = str(tmpdir.join('test_exposure.fits'))
    # A one second normal exposure.
    camera.take_exposure(filename=fits_path)
    # By default take_exposure is non-blocking, need to give it some time to complete.
    time.sleep(5)
    assert os.path.exists(fits_path)
    # If can retrieve some header data there's a good chance it's a valid FITS file
    header = fits.getheader(fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Light Frame'


def test_exposure_blocking(camera, tmpdir):
    """
    Tests blocking take_exposure functionality. At least for now only SBIG cameras do this.
    """
    fits_path = str(tmpdir.join('test_exposure_blocking.fits'))
    # A one second exposure, command should block until complete so FITS
    # should exist immediately afterwards
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
    assert os.path.exists(fits_path_1)
    assert os.path.exists(fits_path_2)
    assert fits.getval(fits_path_1, 'EXPTIME') == 2.0
    assert fits.getval(fits_path_2, 'EXPTIME') == 1.0


def test_exposure_no_filename(camera):
    with pytest.raises(AssertionError):
        camera.take_exposure(1.0)


def test_exposure_not_connected(camera):
    camera._connected = False
    with pytest.raises(AssertionError):
        camera.take_exposure(1.0)
    camera._connected = True


def test_observation(camera):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')
    observation = Observation(field, exp_time=1.5 * u.second)
    camera.take_observation(observation, headers={})
    time.sleep(7)


def test_autofocus_coarse(camera):
    autofocus_event = camera.autofocus(coarse=True)
    autofocus_event.wait()


def test_autofocus_fine(camera):
    autofocus_event = camera.autofocus()
    autofocus_event.wait()


def test_autofocus_fine_blocking(camera):
    autofocus_event = camera.autofocus(blocking=True)
    assert autofocus_event.is_set()


def test_autofocus_no_plots(camera):
    autofocus_event = camera.autofocus(plots=False)
    autofocus_event.wait()


def test_autofocus_keep_files(camera):
    autofocus_event = camera.autofocus(keep_files=True)
    autofocus_event.wait()


def test_autofocus_no_size(camera):
    initial_focus = camera.focuser.position
    thumbnail_size = camera.focuser.autofocus_size
    camera.focuser.autofocus_size = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_size = thumbnail_size
    assert camera.focuser.position == initial_focus


def test_autofocus_no_seconds(camera):
    initial_focus = camera.focuser.position
    seconds = camera.focuser.autofocus_seconds
    camera.focuser.autofocus_seconds = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_seconds = seconds
    assert camera.focuser.position == initial_focus


def test_autofocus_no_step(camera):
    initial_focus = camera.focuser.position
    autofocus_step = camera.focuser.autofocus_step
    camera.focuser.autofocus_step = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_step = autofocus_step
    assert camera.focuser.position == initial_focus


def test_autofocus_no_range(camera):
    initial_focus = camera.focuser.position
    autofocus_range = camera.focuser.autofocus_range
    camera.focuser.autofocus_range = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_range = autofocus_range
    assert camera.focuser.position == initial_focus


def test_autofocus_camera_disconnected(camera):
    initial_focus = camera.focuser.position
    camera._connected = False
    with pytest.raises(AssertionError):
        camera.autofocus()
    camera._connected = True
    assert camera.focuser.position == initial_focus


def test_autofocus_focuser_disconnected(camera):
    initial_focus = camera.focuser.position
    camera.focuser._connected = False
    with pytest.raises(AssertionError):
        camera.autofocus()
    camera.focuser._connected = True
    assert camera.focuser.position == initial_focus


def test_autofocus_no_focuser(camera):
    initial_focus = camera.focuser.position
    focuser = camera.focuser
    camera.focuser = None
    with pytest.raises(AttributeError):
        camera.autofocus()
    camera.focuser = focuser
    assert camera.focuser.position == initial_focus
