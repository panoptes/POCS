import pytest

import os
import time
import glob
from copy import deepcopy
from ctypes.util import find_library

import astropy.units as u
from astropy.io import fits

from pocs.camera.simulator import Camera as SimCamera
from pocs.camera.simulator_sdk import Camera as SimSDKCamera
from pocs.camera.sbig import Camera as SBIGCamera
from pocs.camera.sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE
from pocs.camera.fli import Camera as FLICamera
from pocs.camera.zwo import Camera as ZWOCamera
from pocs.camera import create_cameras_from_config
from pocs.focuser.simulator import Focuser
from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation
from pocs.utils.config import load_config
from pocs.utils.error import NotFound
from pocs.utils.images import fits as fits_utils
from pocs.utils import error
from pocs import hardware


params = [SimCamera, SimCamera, SimCamera, SimSDKCamera, SBIGCamera, FLICamera, ZWOCamera]
ids = ['simulator', 'simulator_focuser', 'simulator_filterwheel', 'simulator_sdk',
       'sbig', 'fli', 'zwo']


@pytest.fixture(scope='module')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    return str(directory)


# Ugly hack to access id inside fixture
@pytest.fixture(scope='module', params=zip(params, ids), ids=ids)
def camera(request, images_dir):
    if request.param[1] == 'simulator':
        camera = SimCamera()
    elif request.param[1] == 'simulator_focuser':
        camera = SimCamera(focuser={'model': 'simulator',
                                    'focus_port': '/dev/ttyFAKE',
                                    'initial_position': 20000,
                                    'autofocus_range': (40, 80),
                                    'autofocus_step': (10, 20),
                                    'autofocus_seconds': 0.1,
                                    'autofocus_size': 500,
                                    'autofocus_keep_files': False})
    elif request.param[1] == 'simulator_filterwheel':
        camera = SimCamera(filterwheel={'model': 'simulator',
                                        'filter_names': ['one', 'deux', 'drei', 'quattro'],
                                        'move_time': 0.1,
                                        'timeout': 0.5})
    elif request.param[1] == 'simulator_sdk':
        camera = SimSDKCamera(serial_number='SSC101')
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
                    if camera_config and camera_config['model'] == request.param[1]:
                        # Camera config is the right type
                        configs.append(camera_config)

        if not configs:
            pytest.skip(
                "Found no {} configs in pocs_local.yaml, skipping tests".format(request.param[1]))

        # Create and return an camera based on the first config
        camera = request.param[0](**configs[0])

    camera.config['directories']['images'] = images_dir
    return camera


@pytest.fixture(scope='module')
def counter(camera):
    return {'value': 0}


@pytest.fixture(scope='module')
def patterns(camera, images_dir):
    patterns = {'final': os.path.join(images_dir, 'focus', camera.uid, '*',
                                      ('*_final.' + camera.file_extension)),
                'fine_plot': os.path.join(images_dir, 'focus', camera.uid, '*',
                                          'fine_focus.png'),
                'coarse_plot': os.path.join(images_dir, 'focus', camera.uid, '*',
                                            'coarse_focus.png')}
    return patterns


def test_create_cameras_from_config(config):
    cameras = create_cameras_from_config(config)
    assert len(cameras) == 2


def test_create_cameras_from_config_fail(config):
    orig_config = deepcopy(config)
    cameras = create_cameras_from_config(config)
    assert len(cameras) == 2
    simulator = hardware.get_all_names(without=['camera'])

    config['cameras']['auto_detect'] = False
    config['cameras']['devices'][0] = {
        'port': '/dev/foobar',
        'model': 'foobar'
    }

    cameras = create_cameras_from_config(config, simulator=simulator)
    assert len(cameras) != 2

    # SBIGs require a serial_number, not port
    config['cameras']['devices'][0] = {
        'port': '/dev/ttyFAKE',
        'model': 'sbig'
    }

    cameras = create_cameras_from_config(config, simulator=simulator)
    assert len(cameras) != 2

    # Canon DSLRs and the simulator require a port, not a serial_number
    config['cameras']['devices'][0] = {
        'serial_number': 'SC1234',
        'model': 'serial'
    }

    cameras = create_cameras_from_config(config, simulator=simulator)
    assert len(cameras) != 2

    # Make sure we didn't fool ourselves
    cameras = create_cameras_from_config(orig_config)
    assert len(cameras) == 2


def test_create_cameras_from_empty_config():
    # create_cameras_from_config should work with no camera config, if cameras simulation is set
    empty_config = {'simulator': ['camera', ], }
    cameras = create_cameras_from_config(config=empty_config)
    assert len(cameras) == 1
    # Default simulated camera will have simulated focuser and filterwheel
    cam = cameras['Cam00']
    assert cam.is_connected
    assert cam.focuser.is_connected
    assert cam.filterwheel.is_connected


def test_dont_create_cameras_from_empty_config():
    # Can't pass a completely empty config otherwise default config will get loaded in its place.
    really_empty_config = {'i_need_to_evaluate_to': True}
    cameras = create_cameras_from_config(config=really_empty_config)
    assert len(cameras) == 0


# Hardware independent tests, mostly use simulator:

def test_sim_create_focuser():
    sim_camera = SimCamera(focuser={'model': 'simulator', 'focus_port': '/dev/ttyFAKE'})
    assert isinstance(sim_camera.focuser, Focuser)


def test_sim_passed_focuser():
    sim_focuser = Focuser(port='/dev/ttyFAKE')
    sim_camera = SimCamera(focuser=sim_focuser)
    assert sim_camera.focuser is sim_focuser


def test_sim_bad_focuser():
    with pytest.raises(NotFound):
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
    assert sim_camera.readout_time == 1.0
    sim_camera = SimCamera(readout_time=2.0)
    assert sim_camera.readout_time == 2.0


def test_sdk_no_serial_number():
    with pytest.raises(ValueError):
        sim_camera = SimSDKCamera()


def test_sdk_camera_not_found():
    with pytest.raises(error.PanError):
        sim_camera = SimSDKCamera(serial_number='SSC404')


def test_sdk_already_in_use():
    sim_camera = SimSDKCamera(serial_number='SSC999')
    with pytest.raises(error.PanError):
        sim_camera_2 = SimSDKCamera(serial_number='SSC999')

# Hardware independent tests for SBIG camera


def test_sbig_driver_bad_path():
    """
    Manually specify an incorrect path for the SBIG shared library. The
    CDLL loader should raise OSError when it fails. Can't test a successful
    driver init as it would cause subsequent tests to fail because of the
    CDLL unload problem.
    """
    with pytest.raises(OSError):
        SBIGDriver(library_path='no_library_here')


@pytest.mark.filterwarnings('ignore:Could not connect to SBIG Camera')
def test_sbig_bad_serial():
    """
    Attempt to create an SBIG camera instance for a specific non-existent
    camera. No actual cameras are required to run this test but the SBIG
    driver does need to be installed.
    """
    if find_library('sbigudrv') is None:
        pytest.skip("Test requires SBIG camera driver to be installed")
    with pytest.raises(error.PanError):
        camera = SBIGCamera(serial_number='NOTAREALSERIALNUMBER')

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
    cooling_enabled = camera.cooling_enabled
    if not camera.is_cooled_camera:
        assert not cooling_enabled


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
    if camera.is_cooled_camera and camera.cooling_enabled is False:
        camera.cooling_enabled = True
        time.sleep(5)  # Give camera time to cool
    assert camera.is_ready
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


@pytest.mark.filterwarnings('ignore:Attempt to start exposure')
def test_exposure_collision(camera, tmpdir):
    """
    Tests attempting to take an exposure while one is already in progress.
    With the SBIG cameras this will generate warning but still should work. Don't do this though!
    """
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
        assert (image_data % 2**pad_bits).any()


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


def test_move_filterwheel(camera, images_dir):
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')
    observation = Observation(field, exptime=1.5*u.second, filter_name='deux')
    observation.seq_time = '19991231T235959'
    camera.take_observation(observation, headers={})
    time.sleep(7)


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
    exposure_event = camera.take_exposure(seconds=0.1, filename=fits_path)
    # Wait for it all to be over.
    time.sleep(original_timeout)
    # Put the timeout back to the original setting.
    camera._timeout = original_timeout
    # Should be an ERROR message in the log from the exposure tiemout
    assert caplog.records[-1].levelname == "ERROR"
    # Should be no data file, camera should not be exposing, and exposure event should be set
    assert not os.path.exists(fits_path)
    assert not camera.is_exposing
    assert exposure_event is camera._exposure_event
    assert exposure_event.is_set()


def test_observation(camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')
    observation = Observation(field, exptime=1.5 * u.second)
    observation.seq_time = '19991231T235959'
    camera.take_observation(observation, headers={})
    time.sleep(7)
    observation_pattern = os.path.join(images_dir, 'fields', 'TestObservation',
                                       camera.uid, observation.seq_time, '*.fits*')
    assert len(glob.glob(observation_pattern)) == 1


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
