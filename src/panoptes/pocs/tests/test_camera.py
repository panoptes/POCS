import pytest

import os
import time
import glob
from ctypes.util import find_library
from contextlib import suppress

import astropy.units as u
from astropy.io import fits

from panoptes.pocs.camera.simulator import Camera as SimCamera
from panoptes.pocs.camera.simulator_sdk import Camera as SimSDKCamera
from panoptes.pocs.camera.sbig import Camera as SBIGCamera
from panoptes.pocs.camera.sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE
from panoptes.pocs.camera.fli import Camera as FLICamera
from panoptes.pocs.camera.zwo import Camera as ZWOCamera

from panoptes.pocs.focuser.simulator import Focuser
from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation import Observation

from panoptes.utils.error import NotFound
from panoptes.utils.images import fits as fits_utils
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config

from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.camera import create_camera_simulator

focuser_params = {
    'model': 'simulator',
    'focus_port': '/dev/ttyFAKE',
    'initial_position': 20000,
    'autofocus_range': (40, 80),
    'autofocus_step': (10, 20),
    'autofocus_seconds': 0.1,
    'autofocus_size': 500,
    'autofocus_keep_files': False
}

filterwheel_params = {
    'model': 'simulator',
    'filter_names': ['one', 'deux', 'drei', 'quattro'],
    'move_time': 0.1,
    'timeout': 0.5
}

serial_number_params = 'SSC101'


@pytest.fixture(scope='function', params=[
    pytest.param([SimCamera, dict()]),
    pytest.param([SimCamera, dict(focuser=focuser_params)]),
    pytest.param([SimCamera, dict(filterwheel=filterwheel_params)]),
    pytest.param([SimSDKCamera, dict(serial_number=serial_number_params)]),
    pytest.param([SBIGCamera, 'sbig'], marks=[pytest.mark.with_camera]),
    pytest.param([FLICamera, 'fli'], marks=[pytest.mark.with_camera]),
    pytest.param([ZWOCamera, 'zwo'], marks=[pytest.mark.with_camera]),
], ids=[
    'simulator', 'simulator_focuser', 'simulator_filterwheel', 'simulator_sdk',
    'sbig', 'fli', 'zwo'
])
def camera(request, dynamic_config_server, config_port):
    CamClass = request.param[0]
    cam_params = request.param[1]

    if isinstance(cam_params, dict):
        # Simulator
        camera = CamClass(config_port=config_port, **cam_params)
    else:
        # Lookup real hardware device name in real life config server.
        for cam_config in get_config('cameras.devices'):
            if cam_config['model'] == cam_params:
                camera = CamClass(**cam_config)
                break

    camera.logger.debug(f'Yielding camera {camera}')
    assert camera.is_ready
    yield camera

    # simulator_sdk needs this explictly removed for some reason.
    with suppress(AttributeError):
        type(camera)._assigned_cameras.discard(camera.uid)


@pytest.fixture(scope='function')
def counter(camera):
    return {'value': 0}


@pytest.fixture(scope='function')
def patterns(camera, images_dir):
    patterns = {'final': os.path.join(images_dir, 'focus', camera.uid, '*',
                                      ('*_final.' + camera.file_extension)),
                'fine_plot': os.path.join(images_dir, 'focus', camera.uid, '*',
                                          'fine_focus.png'),
                'coarse_plot': os.path.join(images_dir, 'focus', camera.uid, '*',
                                            'coarse_focus.png')}
    return patterns


def test_create_camera_simulator():
    cameras = create_camera_simulator()
    assert len(cameras) == 2

    cameras = create_camera_simulator()
    assert len(cameras) == 2

    with pytest.raises(error.CameraNotFound):
        create_camera_simulator(num_cameras=0)


def test_create_cameras_from_config_no_autodetect(dynamic_config_server, config_port):
    set_config('cameras.auto_detect', False, port=config_port)
    set_config('cameras.devices', [
        dict(model='canon_gphoto2', port='/dev/fake01'),
        dict(model='canon_gphoto2', port='/dev/fake02'),
    ], port=config_port)

    with pytest.raises(error.CameraNotFound):
        create_cameras_from_config(config_port=config_port)


def test_create_cameras_from_config_autodetect(dynamic_config_server, config_port):
    set_config('cameras.auto_detect', True, port=config_port)
    with pytest.raises(error.CameraNotFound):
        create_cameras_from_config(config_port=config_port)


# Hardware independent tests, mostly use simulator:

def test_sim_create_focuser(dynamic_config_server, config_port):
    sim_camera = SimCamera(focuser={'model': 'simulator', 'focus_port': '/dev/ttyFAKE'},
                           config_port=config_port)
    assert isinstance(sim_camera.focuser, Focuser)


def test_sim_passed_focuser(dynamic_config_server, config_port):
    sim_focuser = Focuser(port='/dev/ttyFAKE', config_port=config_port)
    sim_camera = SimCamera(focuser=sim_focuser, config_port=config_port)
    assert sim_camera.focuser is sim_focuser


def test_sim_bad_focuser(dynamic_config_server, config_port):
    with pytest.raises((NotFound)):
        SimCamera(focuser={'model': 'NOTAFOCUSER'}, config_port=config_port)


def test_sim_worse_focuser(dynamic_config_server, config_port):
    sim_camera = SimCamera(focuser='NOTAFOCUSER', config_port=config_port)
    # Will log an error but raise no exceptions
    assert sim_camera.focuser is None


def test_sim_string(dynamic_config_server, config_port):
    sim_camera = SimCamera(config_port=config_port)
    assert str(sim_camera) == 'Simulated Camera ({}) on None'.format(sim_camera.uid)
    sim_camera = SimCamera(name='Sim', port='/dev/ttyFAKE', config_port=config_port)
    assert str(sim_camera) == 'Sim ({}) on /dev/ttyFAKE'.format(sim_camera.uid)


def test_sim_file_extension(dynamic_config_server, config_port):
    sim_camera = SimCamera(config_port=config_port)
    assert sim_camera.file_extension == 'fits'
    sim_camera = SimCamera(file_extension='FIT', config_port=config_port)
    assert sim_camera.file_extension == 'FIT'


def test_sim_readout_time(dynamic_config_server, config_port):
    sim_camera = SimCamera(config_port=config_port)
    assert sim_camera.readout_time == 1.0
    sim_camera = SimCamera(readout_time=2.0, config_port=config_port)
    assert sim_camera.readout_time == 2.0


def test_sdk_no_serial_number(dynamic_config_server, config_port):
    with pytest.raises(ValueError):
        SimSDKCamera(config_port=config_port)


def test_sdk_camera_not_found(dynamic_config_server, config_port):
    with pytest.raises(error.PanError):
        SimSDKCamera(serial_number='SSC404', config_port=config_port)


def test_sdk_already_in_use(dynamic_config_server, config_port):
    sim_camera = SimSDKCamera(serial_number='SSC999', config_port=config_port)
    assert sim_camera
    with pytest.raises(error.PanError):
        SimSDKCamera(serial_number='SSC999', config_port=config_port)


# Hardware independent tests for SBIG camera


def test_sbig_driver_bad_path(dynamic_config_server, config_port):
    """
    Manually specify an incorrect path for the SBIG shared library. The
    CDLL loader should raise OSError when it fails. Can't test a successful
    driver init as it would cause subsequent tests to fail because of the
    CDLL unload problem.
    """
    with pytest.raises(OSError):
        SBIGDriver(library_path='no_library_here', config_port=config_port)


@pytest.mark.filterwarnings('ignore:Could not connect to SBIG Camera')
def test_sbig_bad_serial(dynamic_config_server, config_port):
    """
    Attempt to create an SBIG camera instance for a specific non-existent
    camera. No actual cameras are required to run this test but the SBIG
    driver does need to be installed.
    """
    if find_library('sbigudrv') is None:
        pytest.skip("Test requires SBIG camera driver to be installed")
    with pytest.raises(error.PanError):
        SBIGCamera(serial_number='NOTAREALSERIALNUMBER', config_port=config_port)


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
        temperature = camera.temperature
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature info".format(camera.name))
    else:
        assert temperature is not None


def test_is_cooled(camera):
    cooled_camera = camera.is_cooled_camera
    assert cooled_camera is not None


def test_set_target_temperature(camera):
    if camera.is_cooled_camera:
        camera._target_temperature = 10 * u.Celsius
        assert abs(camera._target_temperature - 10 * u.Celsius) < 0.5 * u.Celsius
    else:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))


def test_cooling_enabled(camera):
    print('Some test output')
    assert camera.cooling_enabled == camera.is_cooled_camera
    print('Some other output')


def test_enable_cooling(camera):
    if camera.is_cooled_camera:
        camera.cooling_enabled = True
        assert camera.cooling_enabled
    else:
        pytest.skip("Camera {} doesn't implement control of cooling status".format(camera.name))


def test_get_cooling_power(camera):
    if camera.is_cooled_camera:
        power = camera.cooling_power
        assert power is not None
    else:
        pytest.skip("Camera {} doesn't implement cooling power readout".format(camera.name))


def test_disable_cooling(camera):
    if camera.is_cooled_camera:
        camera.cooling_enabled = False
        assert not camera.cooling_enabled
    else:
        pytest.skip("Camera {} doesn't implement control of cooling status".format(camera.name))


def test_temperature_tolerance(camera):
    temp_tol = camera.temperature_tolerance
    camera.temperature_tolerance = temp_tol.value + 1
    assert camera.temperature_tolerance == temp_tol + 1 * u.Celsius
    camera.temperature_tolerance = temp_tol
    assert camera.temperature_tolerance == temp_tol


def test_is_temperature_stable(camera):
    if camera.is_cooled_camera:
        camera.target_temperature = camera.temperature
        camera.cooling_enabled = True
        time.sleep(1)
        assert camera.is_temperature_stable
        camera.cooling_enabled = False
        assert not camera.is_temperature_stable
        camera.cooling_enabled = True
    else:
        assert not camera.is_temperature_stable


def test_exposure(camera, tmpdir):
    """
    Tests basic take_exposure functionality
    """
    fits_path = str(tmpdir.join('test_exposure.fits'))

    assert not camera.is_exposing
    # A one second normal exposure.
    exp_event = camera.take_exposure(filename=fits_path)
    assert camera.is_exposing
    assert not exp_event.is_set()
    assert not camera.is_ready
    # By default take_exposure is non-blocking, need to give it some time to complete.
    if isinstance(camera, FLICamera):
        time.sleep(10)
    else:
        time.sleep(5)
    # Output file should exist, Event should be set and camera should say it's not exposing.
    assert os.path.exists(fits_path)
    assert exp_event.is_set()
    assert not camera.is_exposing
    assert camera.is_ready
    # If can retrieve some header data there's a good chance it's a valid FITS file
    header = fits_utils.getheader(fits_path)
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
    header = fits_utils.getheader(fits_path)
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
    header = fits_utils.getheader(fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Dark Frame'


def test_exposure_collision(camera, tmpdir):
    """
    Tests attempting to take an exposure while one is already in progress.
    With the SBIG cameras this will generate warning but still should work. Don't do this though!
    """
    # Allow for cooling
    if camera.is_cooled_camera and camera.cooling_enabled:
        while camera.is_temperature_stable is False:
            time.sleep(0.5)

    fits_path_1 = str(tmpdir.join('test_exposure_collision1.fits'))
    fits_path_2 = str(tmpdir.join('test_exposure_collision2.fits'))
    camera.take_exposure(2 * u.second, filename=fits_path_1)
    with pytest.raises(error.PanError):
        camera.take_exposure(1 * u.second, filename=fits_path_2)
    if isinstance(camera, FLICamera):
        time.sleep(10)
    else:
        time.sleep(5)
    assert os.path.exists(fits_path_1)
    assert not os.path.exists(fits_path_2)
    assert fits_utils.getval(fits_path_1, 'EXPTIME') == 2.0


def test_exposure_scaling(camera, tmpdir):
    """Regression test for incorrect pixel value scaling.

    Checks for zero padding of LSBs instead of MSBs, as encountered
    with ZWO ASI cameras.
    """
    try:
        bit_depth = camera.bit_depth
    except NotImplementedError:
        pytest.skip("Camera does not have bit_depth attribute")
    else:
        fits_path = str(tmpdir.join('test_exposure_scaling.fits'))
        camera.take_exposure(filename=fits_path, dark=True, blocking=True)
        image_data, image_header = fits.getdata(fits_path, header=True)
        assert bit_depth == image_header['BITDEPTH'] * u.bit
        pad_bits = image_header['BITPIX'] - image_header['BITDEPTH']
        assert (image_data % 2 ** pad_bits).any()


def test_exposure_no_filename(camera):
    with pytest.raises(AssertionError):
        camera.take_exposure(1.0)


def test_exposure_not_connected(camera):
    camera._connected = False
    with pytest.raises(AssertionError):
        camera.take_exposure(1.0)
    camera._connected = True


def test_exposure_moving(camera, tmpdir):
    if not camera.filterwheel:
        pytest.skip("Camera does not have a filterwheel")
    fits_path_1 = str(tmpdir.join('test_not_moving.fits'))
    fits_path_2 = str(tmpdir.join('test_moving.fits'))
    camera.filterwheel.position = 1
    exp_event = camera.take_exposure(filename=fits_path_1)
    exp_event.wait()
    assert os.path.exists(fits_path_1)
    move_event = camera.filterwheel.move_to(2)
    with pytest.raises(error.PanError):
        camera.take_exposure(filename=fits_path_2)
    move_event.wait()
    assert not os.path.exists(fits_path_2)


def test_exposure_timeout(camera, tmpdir, caplog):
    """
    Tests response to an exposure timeout
    """
    fits_path = str(tmpdir.join('test_exposure_timeout.fits'))
    # Make timeout extremely short to force a timeout error
    original_timeout = camera._timeout
    camera._timeout = 0.01
    # This should result in a timeout error in the poll thread, but the exception won't
    # be seen in the main thread. Can check for logged error though.
    exposure_event = camera.take_exposure(seconds=2.0, filename=fits_path)

    # Wait for it all to be over.
    time.sleep(4)

    # Should be an ERROR message in the log from the exposure timeout
    assert caplog.records[-1].levelname == "ERROR"
    # Should be no data file, camera should not be exposing, and exposure event should be set
    assert not os.path.exists(fits_path)
    assert not camera.is_exposing
    assert exposure_event is camera._exposure_event
    assert exposure_event.is_set()


def test_observation(dynamic_config_server, config_port, camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s', config_port=config_port)
    observation = Observation(field, exptime=1.5 * u.second, config_port=config_port)
    observation.seq_time = '19991231T235959'
    camera.take_observation(observation, headers={})
    time.sleep(7)
    observation_pattern = os.path.join(images_dir, 'TestObservation',
                                       camera.uid, observation.seq_time, '*.fits*')
    assert len(glob.glob(observation_pattern)) == 1
    for fn in glob.glob(observation_pattern):
        os.remove(fn)


def test_observation_nofilter(dynamic_config_server, config_port, camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s', config_port=config_port)
    observation = Observation(field, exptime=1.5 * u.second, filter_name=None, config_port=config_port)
    observation.seq_time = '19991231T235959'
    camera.take_observation(observation, headers={})
    time.sleep(7)
    observation_pattern = os.path.join(images_dir, 'TestObservation',
                                       camera.uid, observation.seq_time, '*.fits*')
    assert len(glob.glob(observation_pattern)) == 1
    for fn in glob.glob(observation_pattern):
        os.remove(fn)


def test_autofocus_coarse(camera, patterns, counter):
    if not camera.focuser:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(coarse=True)
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_fine(camera, patterns, counter):
    if not camera.focuser:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus()
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_fine_blocking(camera, patterns, counter):
    if not camera.focuser:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(blocking=True)
    assert autofocus_event.is_set()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_with_plots(camera, patterns, counter):
    if not camera.focuser:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(make_plots=True)
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']
    assert len(glob.glob(patterns['fine_plot'])) == 1


def test_autofocus_coarse_with_plots(camera, patterns, counter):
    if not camera.focuser:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(coarse=True, make_plots=True)
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']
    assert len(glob.glob(patterns['coarse_plot'])) == 1


def test_autofocus_keep_files(camera, patterns, counter):
    if not camera.focuser:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(keep_files=True)
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_no_size(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
    initial_focus = camera.focuser.position
    thumbnail_size = camera.focuser.autofocus_size
    camera.focuser.autofocus_size = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_size = thumbnail_size
    assert camera.focuser.position == initial_focus


def test_autofocus_no_seconds(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
    initial_focus = camera.focuser.position
    seconds = camera.focuser.autofocus_seconds
    camera.focuser.autofocus_seconds = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_seconds = seconds
    assert camera.focuser.position == initial_focus


def test_autofocus_no_step(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
    initial_focus = camera.focuser.position
    autofocus_step = camera.focuser.autofocus_step
    camera.focuser.autofocus_step = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_step = autofocus_step
    assert camera.focuser.position == initial_focus


def test_autofocus_no_range(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
    initial_focus = camera.focuser.position
    autofocus_range = camera.focuser.autofocus_range
    camera.focuser.autofocus_range = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_range = autofocus_range
    assert camera.focuser.position == initial_focus


def test_autofocus_camera_disconnected(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
    initial_focus = camera.focuser.position
    camera._connected = False
    with pytest.raises(AssertionError):
        camera.autofocus()
    camera._connected = True
    assert camera.focuser.position == initial_focus


def test_autofocus_focuser_disconnected(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
    initial_focus = camera.focuser.position
    camera.focuser._connected = False
    with pytest.raises(AssertionError):
        camera.autofocus()
    camera.focuser._connected = True
    assert camera.focuser.position == initial_focus


def test_autofocus_no_focuser(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
    initial_focus = camera.focuser.position
    focuser = camera.focuser
    camera.focuser = None
    with pytest.raises(AttributeError):
        camera.autofocus()
    camera.focuser = focuser
    assert camera.focuser.position == initial_focus
