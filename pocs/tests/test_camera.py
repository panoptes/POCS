import pytest

from pocs.camera.simulator import Camera as SimCamera
from pocs.camera.pyro import Camera as PyroCamera
from pocs.camera.sbig import Camera as SBIGCamera
from pocs.camera.sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE
from pocs.camera.fli import Camera as FLICamera
from pocs.focuser.simulator import Focuser
from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation
from pocs.utils.config import load_config
from pocs.utils.error import NotFound

import os
import glob
import time
import subprocess
import signal
from ctypes.util import find_library

import astropy.units as u
import astropy.io.fits as fits
import Pyro4

params = [SimCamera, PyroCamera, SBIGCamera, FLICamera]
ids = ['simulator', 'pyro', 'sbig', 'fli']


@pytest.fixture(scope='module')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    return str(directory)


def end_process(proc):
    proc.send_signal(signal.SIGINT)
    return_code = proc.wait()


@pytest.fixture(scope='module')
def name_server(request):
    ns_cmds = [os.path.expandvars('$POCS/pocs/utils/pyro/pyro_name_server.py'),
               '--host', 'localhost']
    ns_proc = subprocess.Popen(ns_cmds)
    request.addfinalizer(lambda: end_process(ns_proc))
    # Give name server time to start up
    time.sleep(5)
    return ns_proc


@pytest.fixture(scope='module')
def camera_server(name_server, request):
    cs_cmds = [os.path.expandvars('$POCS/pocs/utils/pyro/pyro_camera_server.py'),
               '--ignore_local']
    cs_proc = subprocess.Popen(cs_cmds)
    request.addfinalizer(lambda: end_process(cs_proc))
    # Give camera server time to start up
    time.sleep(3)
    return cs_proc


# Ugly hack to access id inside fixture
@pytest.fixture(scope='module', params=zip(params, ids), ids=ids)
def camera(request, images_dir, camera_server):
    if request.param[0] == SimCamera:
        camera = SimCamera(focuser={'model': 'simulator',
                                    'focus_port': '/dev/ttyFAKE',
                                    'initial_position': 20000,
                                    'autofocus_range': (40, 80),
                                    'autofocus_step': (10, 20),
                                    'autofocus_seconds': 0.1,
                                    'autofocus_size': 500,
                                    'autofocus_keep_files': False})
    elif request.param[0] == PyroCamera:
        ns = Pyro4.locateNS(host='localhost')
        cameras = ns.list(metadata_all={'POCS', 'Camera'})
        cam_name, cam_uri = cameras.popitem()
        camera = PyroCamera(name=cam_name, uri=cam_uri)
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


@pytest.fixture(scope='module')
def counter():
    return {'value': 0}

# Hardware independent tests using simulator:


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


# Hardware independent tests for distributed cameras

def test_name_server(name_server):
    # Check that it's running.
    assert name_server.poll() is None


def test_locate_name_server(name_server):
    # Check that we can connect to the name server
    Pyro4.locateNS(host='localhost')


def test_camera_server(camera_server):
    # Check that it's running.
    assert camera_server.poll() is None


def test_camera_detection(camera_server):
    ns = Pyro4.locateNS(host='localhost')
    cameras = ns.list(metadata_all={'POCS', 'Camera'})
    # Should be one distributed camera, a simulator with simulated focuser
    assert len(cameras) == 1

# Hardware independent tests for SBIG camera.


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
        temperature = camera.ccd_temp
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature info".format(camera.name))
    else:
        assert temperature is not None


def test_set_set_point(camera):
    try:
        camera.ccd_set_point = 10 * u.Celsius
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement temperature control".format(camera.name))
    else:
        assert abs(camera.ccd_set_point - 10 * u.Celsius) < 0.5 * u.Celsius


def test_enable_cooling(camera):
    try:
        camera.ccd_cooling_enabled = True
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement control of cooling status".format(camera.name))
    else:
        assert camera.ccd_cooling_enabled is True


def test_get_cooling_power(camera):
    try:
        power = camera.ccd_cooling_power
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement cooling power readout".format(camera.name))
    else:
        assert power is not None


def test_disable_cooling(camera):
    try:
        camera.ccd_cooling_enabled = False
    except NotImplementedError:
        pytest.skip("Camera {} doesn't implement control of cooling status".format(camera.name))
    else:
        assert camera.ccd_cooling_enabled is False


def test_exposure(camera, tmpdir):
    """
    Tests basic take_exposure functionality
    """
    fits_path = str(tmpdir.join('test_exposure.fits'))
    # A one second normal exposure.
    camera.take_exposure(filename=fits_path)
    # By default take_exposure is non-blocking, need to give it some time to complete.
    if isinstance(camera, FLICamera):
        time.sleep(10)
    else:
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


@pytest.mark.filterwarnings('ignore:Attempt to start exposure')
def test_exposure_collision(camera, tmpdir):
    """
    Tests attempting to take an exposure while one is already in progress.
    With the SBIG cameras this will generate warning but still should work. Don't do this though!
    """
    fits_path_1 = str(tmpdir.join('test_exposure_collision1.fits'))
    fits_path_2 = str(tmpdir.join('test_exposure_collision2.fits'))
    camera.take_exposure(2 * u.second, filename=fits_path_1)
    camera.take_exposure(1 * u.second, filename=fits_path_2)
    if isinstance(camera, FLICamera):
        time.sleep(10)
    else:
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


def test_observation(camera, images_dir):
    """
    Tests functionality of take_observation()
    """
    field = Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')
    observation = Observation(field, exp_time=1.5 * u.second)
    observation.seq_time = 'seq_time'
    camera.take_observation(observation, headers={})
    time.sleep(7)
    observation_pattern = os.path.join(images_dir, 'fields', 'TestObservation',
                                       camera.uid, 'seq_time', '*.fits*')
    assert len(glob.glob(observation_pattern)) == 1


def test_autofocus_coarse(camera, images_dir, counter):
    autofocus_event = camera.autofocus(coarse=True)
    autofocus_event.wait()
    coarse_plot_pattern = os.path.join(images_dir, 'focus', camera.uid, '*_coarse.png')
    fine_plot_pattern = os.path.join(images_dir, 'focus', camera.uid, '*_fine.png')
    counter['value'] = 1
    assert len(glob.glob(coarse_plot_pattern)) == 1
    assert len(glob.glob(fine_plot_pattern)) == counter['value']


def test_autofocus_fine(camera, images_dir, counter):
    autofocus_event = camera.autofocus()
    autofocus_event.wait()
    counter['value'] += 1
    fine_plot_pattern = os.path.join(images_dir, 'focus', camera.uid, '*_fine.png')
    assert len(glob.glob(fine_plot_pattern)) == counter['value']


def test_autofocus_fine_blocking(camera, images_dir, counter):
    autofocus_event = camera.autofocus(blocking=True)
    assert autofocus_event.is_set()
    counter['value'] += 1
    fine_plot_pattern = os.path.join(images_dir, 'focus', camera.uid, '*_fine.png')
    assert len(glob.glob(fine_plot_pattern)) == counter['value']


def test_autofocus_no_plots(camera, images_dir, counter):
    autofocus_event = camera.autofocus(plots=False)
    autofocus_event.wait()
    fine_plot_pattern = os.path.join(images_dir, 'focus', camera.uid, '*_fine.png')
    assert len(glob.glob(fine_plot_pattern)) == counter['value']


def test_autofocus_keep_files(camera, images_dir, counter):
    autofocus_event = camera.autofocus(keep_files=True)
    autofocus_event.wait()
    counter['value'] += 1
    fine_plot_pattern = os.path.join(images_dir, 'focus', camera.uid, '*_fine.png')
    assert len(glob.glob(fine_plot_pattern)) == counter['value']


def test_autofocus_no_size(camera):
    try:
        initial_focus = camera.focuser.position
    except AttributeError:
        pytest.skip("Camera does not have an exposed focuser attribute")
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
    focuser = camera.focuser
    camera.focuser = None
    with pytest.raises(AttributeError):
        camera.autofocus()
    camera.focuser = focuser
    assert camera.focuser.position == initial_focus
