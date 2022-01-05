import os
import time
import glob
from ctypes.util import find_library
from contextlib import suppress

import pytest
import astropy.units as u
from astropy.io import fits
import requests

from panoptes.pocs.camera.simulator.dslr import Camera as SimCamera
from panoptes.pocs.camera.simulator.ccd import Camera as SimSDKCamera
from panoptes.pocs.camera.sbig import Camera as SBIGCamera
from panoptes.pocs.camera.sbigudrv import INVALID_HANDLE_VALUE, SBIGDriver
from panoptes.pocs.camera.fli import Camera as FLICamera
from panoptes.pocs.camera.zwo import Camera as ZWOCamera

from panoptes.pocs.focuser.simulator import Focuser
from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation
from panoptes.pocs.scheduler.observation.bias import BiasObservation
from panoptes.pocs.scheduler.observation.dark import DarkObservation

from panoptes.utils.error import NotFound
from panoptes.utils.images import fits as fits_utils
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config

from panoptes.pocs.camera import create_cameras_from_config
from panoptes.utils.serializers import to_json
from panoptes.utils.time import CountdownTimer


@pytest.fixture(scope='module', params=[
    pytest.param([SimCamera, dict()]),
    pytest.param([SimCamera, get_config('cameras.devices[0]')]),
    pytest.param([SimCamera, get_config('cameras.devices[1]')]),
    pytest.param([SimCamera, get_config('cameras.devices[2]')]),
    pytest.param([SimSDKCamera, get_config('cameras.devices[3]')]),
    pytest.param([SBIGCamera, 'sbig'], marks=[pytest.mark.with_camera]),
    pytest.param([FLICamera, 'fli'], marks=[pytest.mark.with_camera]),
    pytest.param([ZWOCamera, 'zwo'], marks=[pytest.mark.with_camera]),
], ids=[
    'dslr',
    'dslr.00',
    'dslr.focuser.cooling.00',
    'dslr.filterwheel.cooling.00',
    'ccd.filterwheel.cooling.00',
    'sbig',
    'fli',
    'zwo'
])
def camera(request):
    CamClass = request.param[0]
    cam_params = request.param[1]

    camera = None

    if isinstance(cam_params, dict):
        # Simulator
        camera = CamClass(**cam_params)
    else:
        # Lookup real hardware device name in real life config server.
        for cam_config in get_config('cameras.devices'):
            if cam_config['model'] == cam_params:
                camera = CamClass(**cam_config)
                break

    camera.logger.log('testing', f'Camera created: {camera!r}')

    # Wait for cooled camera
    if camera.is_cooled_camera:
        camera.logger.log('testing', f'Cooled camera needs to wait for cooling.')
        assert not camera.is_temperature_stable
        # Wait for cooling
        cooling_timeout = CountdownTimer(60)  # Should never have to wait this long.
        while not camera.is_temperature_stable and not cooling_timeout.expired():
            camera.logger.log('testing',
                              f'Still waiting for cooling: {cooling_timeout.time_left()}')
            cooling_timeout.sleep(max_sleep=2)
        assert camera.is_temperature_stable and cooling_timeout.expired() is False

    assert camera.is_ready
    camera.logger.debug(f'Yielding camera {camera}')
    yield camera

    # simulator_sdk needs this explicitly removed for some reason.
    # SDK Camera class destructor *should* be doing this when the fixture goes out of scope.
    with suppress(AttributeError):
        type(camera)._assigned_cameras.discard(camera.uid)


@pytest.fixture(scope='module')
def counter(camera):
    return {'value': 0}


@pytest.fixture(scope='module')
def patterns(camera, images_dir):
    base_dir = os.path.join(images_dir, 'focus', camera.uid, '*')
    patterns = {
        'final': os.path.join(base_dir, ('*-final.' + camera.file_extension)),
        'fine_plot': os.path.join(base_dir, 'fine-focus.png'),
        'coarse_plot': os.path.join(base_dir, 'coarse-focus.png')
    }
    return patterns


def reset_conf(config_host, config_port):
    url = f'http://{config_host}:{config_port}/reset-config'
    response = requests.post(url,
                             data=to_json({'reset': True}),
                             headers={'Content-Type': 'application/json'}
                             )
    assert response.ok


def test_create_cameras_from_config_no_autodetect(config_host, config_port):
    set_config('cameras.auto_detect', False)
    set_config('cameras.devices', [
        dict(model='canon_gphoto2', port='/dev/fake01'),
        dict(model='canon_gphoto2', port='/dev/fake02'),
    ])

    with pytest.raises(error.CameraNotFound):
        create_cameras_from_config()

    reset_conf(config_host, config_port)


def test_create_cameras_from_config_autodetect(config_host, config_port):
    set_config('cameras.defaults.auto_detect', True)
    with pytest.raises(error.CameraNotFound):
        create_cameras_from_config()
    reset_conf(config_host, config_port)


# Hardware independent tests, mostly use simulator:

def test_sim_create_focuser():
    sim_camera = SimCamera(focuser={'model': 'panoptes.pocs.focuser.simulator.Focuser',
                                    'focus_port': '/dev/ttyFAKE'})
    assert isinstance(sim_camera.focuser, Focuser)


def test_sim_passed_focuser():
    sim_focuser = Focuser(port='/dev/ttyFAKE')
    sim_camera = SimCamera(focuser=sim_focuser)
    assert sim_camera.focuser is sim_focuser


def test_sim_bad_focuser():
    with pytest.raises(NotFound):
        SimCamera(focuser={'model': 'NOTAFOCUSER'})


def test_sim_worse_focuser():
    with pytest.raises(NotFound):
        sim_camera = SimCamera(focuser='NOTAFOCUSER')


def test_sim_string():
    sim_camera = SimCamera()
    assert str(sim_camera) == f'Simulated Camera ({sim_camera.uid})'
    sim_camera = SimCamera(name='Sim', port='/dev/ttyFAKE')
    assert str(sim_camera) == f'Sim ({sim_camera.uid}) port=/dev/ttyFAKE'


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
        SimSDKCamera()


def test_sdk_already_in_use():
    serial_number = get_config('cameras.devices[-1].serial_number')
    sim_camera = SimSDKCamera(serial_number=serial_number)
    assert sim_camera
    with pytest.raises(error.PanError):
        SimSDKCamera(serial_number=serial_number)

    # Explicitly delete camera to clear `_assigned_cameras`.
    del sim_camera


def test_sdk_camera_not_found():
    with pytest.raises(error.InvalidConfig):
        SimSDKCamera(serial_number='SSC404')


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
        SBIGCamera(serial_number='NOTAREALSERIALNUMBER')


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
        camera.target_temperature = 10 * u.Celsius
        assert abs(camera.target_temperature - 10 * u.Celsius) < 0.5 * u.Celsius
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
        while not camera.is_temperature_stable:
            time.sleep(2)

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
    assert camera.is_ready
    # A one second normal exposure.
    camera.take_exposure(filename=fits_path)
    assert camera.is_exposing
    assert not camera.is_ready
    # By default take_exposure is non-blocking, need to give it some time to complete.
    if isinstance(camera, FLICamera):
        time.sleep(10)
    else:
        time.sleep(5)
    # Output file should exist, Event should be set and camera should say it's not exposing.
    assert os.path.exists(fits_path)
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


def test_long_exposure_blocking(camera, tmpdir):
    """
    Tests basic take_exposure functionality
    """
    fits_path = str(tmpdir.join('test_long_exposure_blocking.fits'))
    original_timeout = camera._timeout
    original_readout = camera._readout_time
    try:
        camera._timeout = 1
        camera._readout_time = 0.5
        assert not camera.is_exposing
        assert camera.is_ready
        seconds = 2 * (camera._timeout + camera._readout_time)
        camera.take_exposure(filename=fits_path, seconds=seconds, blocking=True)
        # Output file should exist, Event should be set and camera should say it's not exposing.
        assert os.path.exists(fits_path)
        assert not camera.is_exposing
        assert camera.is_ready
    finally:
        camera._timeout = original_timeout
        camera._readout_time = original_readout


def test_exposure_dark(camera, tmpdir):
    """
    Tests taking a dark.
    """
    fits_path = str(tmpdir.join('test_exposure_dark.fits'))
    # A 1 second dark exposure
    camera.take_exposure(filename=fits_path, dark=True, blocking=True)
    assert os.path.exists(fits_path)
    # If can retrieve some header data there's a good chance it's a valid FITS file
    header = fits_utils.getheader(fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Dark Frame'
    with suppress(AttributeError):
        if not camera.can_take_internal_darks and camera.filterwheel._dark_position:
            # Filterwheel should have moved to 'blank' position due to dark exposure.
            assert camera.filterwheel.current_filter == 'blank'
            fits_path2 = str(tmpdir.join('test_exposure_dark_light.fits'))
            camera.take_exposure(filename=fits_path2, blocking=True)
            # Filterwheel should have moved back to most recent non opaque filter now.
            assert camera.filterwheel.current_filter == 'one'


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
    camera.logger.log('testing', 'Exposure 1 started')
    with pytest.raises(error.PanError):
        camera.take_exposure(1 * u.second, filename=fits_path_2)
    camera.logger.log('testing', 'Exposure 2 collided')
    # Wait for exposure.
    while camera.is_exposing:
        time.sleep(0.5)
    # Wait for readout on file.
    while not os.path.exists(fits_path_1):
        time.sleep(0.5)
    time.sleep(1)  # Make sure the file is fully-written

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
    if camera.filterwheel is None:
        pytest.skip("Camera does not have a filterwheel")
    fits_path_1 = str(tmpdir.join('test_not_moving.fits'))
    fits_path_2 = str(tmpdir.join('test_moving.fits'))
    camera.filterwheel.position = 1
    exp_event = camera.take_exposure(filename=fits_path_1, blocking=True)
    assert os.path.exists(fits_path_1)
    move_event = camera.filterwheel.move_to(2)
    with pytest.raises(error.PanError):
        camera.take_exposure(filename=fits_path_2, blocking=True)
    move_event.wait()
    assert not os.path.exists(fits_path_2)


def test_exposure_timeout(camera, tmpdir, caplog):
    """
    Tests response to an exposure timeout
    """
    fits_path = str(tmpdir.join('test_exposure_timeout.fits'))
    # Make timeout extremely short to force a timeout error
    # This should result in a timeout error in the poll thread, but the exception won't
    # be seen in the main thread. Can check for logged error though.
    readout_thread = camera.take_exposure(seconds=2.0, filename=fits_path, timeout=0.01)

    # Wait for it all to be over.
    time.sleep(4)

    # Should be an ERROR message in the log from the exposure timeout
    assert caplog.records[-1].levelname == "ERROR"
    # Should be no data file, camera should not be exposing, and exposure event should be set
    assert not os.path.exists(fits_path)
    assert not camera.is_exposing
    assert not readout_thread.is_alive()
    assert not camera._is_exposing_event.is_set()


def test_observation(camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')
    observation = Observation(field, exptime=1.5 * u.second)
    observation.seq_time = '19991231T235959'
    observation_event = camera.take_observation(observation)
    while not observation_event.is_set():
        camera.logger.trace(f'Waiting for observation event from inside test.')
        time.sleep(1)
    observation_pattern = os.path.join(images_dir, 'TestObservation',
                                       camera.uid, observation.seq_time, '*.fits*')
    assert len(glob.glob(observation_pattern)) == 1


def test_observation_headers_and_blocking(camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')
    observation = Observation(field, exptime=1.5 * u.second)
    observation.seq_time = '19991231T235559'
    camera.take_observation(observation, headers={'field_name': 'TESTVALUE'}, blocking=True)
    observation_pattern = os.path.join(images_dir, 'TestObservation',
                                       camera.uid, observation.seq_time, '*.fits*')
    image_files = glob.glob(observation_pattern)
    assert len(image_files) == 1
    headers = fits_utils.getheader(image_files[0])
    assert fits_utils.getval(image_files[0], 'FIELD') == 'TESTVALUE'


def test_observation_nofilter(camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')
    observation = Observation(field, exptime=1.5 * u.second, filter_name=None)
    observation.seq_time = '19991231T235159'
    camera.take_observation(observation, blocking=True)
    observation_pattern = os.path.join(images_dir, 'TestObservation',
                                       camera.uid, observation.seq_time, '*.fits*')
    assert len(glob.glob(observation_pattern)) == 1


def test_observation_dark(camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    position = '20h00m43.7135s +22d42m39.0645s'
    observation = DarkObservation(position, exptimes=[1])
    assert observation.dark

    observation.seq_time = '19991231T235959'
    observation_event = camera.take_observation(observation)
    while not observation_event.is_set():
        camera.logger.trace(f'Waiting for observation event from inside test.')
        time.sleep(1)
    observation_pattern = os.path.join(images_dir, 'dark',
                                       camera.uid, observation.seq_time, '*.fits*')
    assert len(glob.glob(observation_pattern)) == 1


def test_observation_bias(camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    position = '20h00m43.7135s +22d42m39.0645s'
    observation = BiasObservation(position)
    assert observation.dark

    observation.seq_time = '19991231T235959'
    observation_event = camera.take_observation(observation)
    while not observation_event.is_set():
        camera.logger.trace(f'Waiting for observation event from inside test.')
        time.sleep(1)
    observation_pattern = os.path.join(images_dir, 'bias',
                                       camera.uid, observation.seq_time, '*.fits*')
    assert len(glob.glob(observation_pattern)) == 1


def test_autofocus_coarse(camera, patterns, counter):
    if not camera.has_focuser:
        pytest.skip("Camera does not have a focuser")

    if camera.has_filterwheel:
        camera.filterwheel.move_to("one", blocking=True)

    autofocus_event = camera.autofocus(coarse=True, filter_name="deux")
    autofocus_event.wait()

    if camera.has_filterwheel:
        assert camera.filterwheel.current_filter == "deux"

    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_fine(camera, patterns, counter):
    if camera.focuser is None:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus()
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_fine_blocking(camera, patterns, counter):
    if camera.focuser is None:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(blocking=True)
    assert autofocus_event.is_set()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_with_plots(camera, patterns, counter):
    if camera.focuser is None:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(make_plots=True)
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']
    assert len(glob.glob(patterns['fine_plot'])) == 1


def test_autofocus_coarse_with_plots(camera, patterns, counter):
    if camera.focuser is None:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(coarse=True, make_plots=True)
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']
    assert len(glob.glob(patterns['coarse_plot'])) == 1


def test_autofocus_keep_files(camera, patterns, counter):
    if camera.focuser is None:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(keep_files=True)
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_no_darks(camera, patterns, counter):
    if camera.focuser is None:
        pytest.skip("Camera does not have a focuser")
    autofocus_event = camera.autofocus(keep_files=True, take_dark=False)
    autofocus_event.wait()
    counter['value'] += 1
    assert len(glob.glob(patterns['final'])) == counter['value']


def test_autofocus_no_size(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
    initial_focus = camera.focuser.position
    cutout_size = camera.focuser.autofocus_size
    camera.focuser.autofocus_size = None
    with pytest.raises(ValueError):
        camera.autofocus()
    camera.focuser.autofocus_size = cutout_size
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


def test_move_filterwheel_focus_offset(camera):
    if not camera.has_filterwheel:
        pytest.skip("Camera does not have a filterwheel.")
    if not camera.has_focuser:
        pytest.skip("Camera does not have a focuser.")

    if camera.filterwheel.focus_offsets is None:
        offsets = {}
    else:
        offsets = camera.filterwheel.focus_offsets

    camera.filterwheel.move_to("one", blocking=True)

    for filter_name in camera.filterwheel.filter_names:

        offset = offsets.get(filter_name, 0) - offsets.get(camera.filterwheel.current_filter, 0)
        initial_position = camera.focuser.position
        camera.filterwheel.move_to(filter_name, blocking=True)
        new_position = camera.focuser.position

        if filter_name in offsets.keys():
            assert new_position == initial_position + offset
        else:
            assert new_position == initial_position
