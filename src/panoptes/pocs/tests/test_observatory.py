import os
import time

import pytest
from astropy.time import Time

from panoptes.pocs import __version__
from panoptes.utils import error
from panoptes.utils.config.client import set_config

from panoptes.pocs import hardware
from panoptes.pocs.mount import AbstractMount
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.scheduler.dispatch import Scheduler
from panoptes.pocs.scheduler.observation import Observation

from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.mount import create_mount_simulator
from panoptes.pocs.dome import create_dome_simulator
from panoptes.pocs.camera import create_camera_simulator
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.utils.location import create_location_from_config


@pytest.fixture(scope='function')
def cameras(dynamic_config_server, config_port):
    return create_camera_simulator(config_port=config_port)


@pytest.fixture(scope='function')
def mount(dynamic_config_server, config_port):
    return create_mount_simulator()


@pytest.fixture
def observatory(dynamic_config_server, config_port, mount, cameras, images_dir):
    """Return a valid Observatory instance with a specific config."""

    site_details = create_location_from_config(config_port=config_port)
    scheduler = create_scheduler_from_config(config_port=config_port,
                                             observer=site_details['observer'])

    obs = Observatory(scheduler=scheduler, config_port=config_port)
    obs.set_mount(mount)
    for cam_name, cam in cameras.items():
        obs.add_camera(cam_name, cam)

    return obs


def test_camera_already_exists(dynamic_config_server, config_port, observatory, cameras):
    for cam_name, cam in cameras.items():
        observatory.add_camera(cam_name, cam)


def test_remove_cameras(dynamic_config_server, config_port, observatory, cameras):
    for cam_name, cam in cameras.items():
        observatory.remove_camera(cam_name)


def test_bad_site(dynamic_config_server, config_port):
    set_config('location', {}, port=config_port)
    with pytest.raises(error.PanError):
        Observatory(config_port=config_port)


def test_cannot_observe(dynamic_config_server, config_port, caplog):
    obs = Observatory(config_port=config_port)

    site_details = create_location_from_config(config_port=config_port)
    cameras = create_camera_simulator()

    assert obs.can_observe is False
    time.sleep(0.5)  # log sink time
    log_record = caplog.records[-1]
    assert log_record.message.endswith("not present, cannot observe") and log_record.levelname == "WARNING"
    obs.scheduler = create_scheduler_from_config(observer=site_details['observer'], config_port=config_port)

    assert obs.can_observe is False
    time.sleep(0.5)  # log sink time
    log_record = caplog.records[-1]
    assert log_record.message.endswith("not present, cannot observe") and log_record.levelname == "WARNING"
    for cam_name, cam in cameras.items():
        obs.add_camera(cam_name, cam)

    assert obs.can_observe is False
    log_record = caplog.records[-1]
    time.sleep(0.5)  # log sink time
    assert log_record.message.endswith("not present, cannot observe") and log_record.levelname == "WARNING"


def test_camera_wrong_type(dynamic_config_server, config_port):
    # Remove mount simulator
    set_config('simulator', hardware.get_all_names(without='camera'), port=config_port)

    with pytest.raises(AttributeError):
        Observatory(cameras=[Time.now()],
                    config_port=config_port)

    with pytest.raises(AssertionError):
        Observatory(cameras={'Cam00': Time.now()},
                    config_port=config_port)


def test_camera(dynamic_config_server, config_port):
    cameras = create_camera_simulator(config_port=config_port)
    obs = Observatory(cameras=cameras,
                      config_port=config_port)
    assert obs.has_cameras


def test_primary_camera(observatory):
    assert observatory.primary_camera is not None


def test_primary_camera_no_primary_camera(observatory):
    observatory._primary_camera = None
    assert observatory.primary_camera is not None


def test_set_scheduler(dynamic_config_server, config_port, observatory, caplog):
    site_details = create_location_from_config(config_port=config_port)
    scheduler = create_scheduler_from_config(
        observer=site_details['observer'], config_port=config_port)
    observatory.set_scheduler(scheduler=None)
    assert observatory.scheduler is None
    observatory.set_scheduler(scheduler=scheduler)
    assert observatory.scheduler is not None
    err_msg = 'Scheduler is not instance of BaseScheduler class, cannot add.'
    with pytest.raises(TypeError, match=err_msg):
        observatory.set_scheduler('scheduler')
    err_msg = ".*missing 1 required positional argument.*"
    with pytest.raises(TypeError, match=err_msg):
        observatory.set_scheduler()


def test_set_dome(dynamic_config_server, config_port):
    set_config('dome', {
        'brand': 'Simulacrum',
        'driver': 'simulator',
    }, port=config_port)
    dome = create_dome_simulator(config_port=config_port)

    obs = Observatory(dome=dome, config_port=config_port)
    assert obs.has_dome is True
    obs.set_dome(dome=None)
    assert obs.has_dome is False
    obs.set_dome(dome=dome)
    assert obs.has_dome is True
    err_msg = 'Dome is not instance of AbstractDome class, cannot add.'
    with pytest.raises(TypeError, match=err_msg):
        obs.set_dome('dome')
    err_msg = ".*missing 1 required positional argument.*"
    with pytest.raises(TypeError, match=err_msg):
        obs.set_dome()


def test_set_mount(dynamic_config_server, config_port):
    obs = Observatory(config_port=config_port)
    assert obs.mount is None

    obs.set_mount(mount=None)
    assert obs.mount is None

    set_config('mount', {
        'brand': 'Simulacrum',
        'driver': 'simulator',
        'model': 'simulator',
    }, port=config_port)
    mount = create_mount_from_config(config_port=config_port)
    obs.set_mount(mount=mount)
    assert isinstance(obs.mount, AbstractMount) is True

    err_msg = 'Mount is not instance of AbstractMount class, cannot add.'
    with pytest.raises(TypeError, match=err_msg):
        obs.set_mount(mount='mount')
    err_msg = ".*missing 1 required positional argument.*"
    with pytest.raises(TypeError, match=err_msg):
        obs.set_mount()


def test_status(observatory):
    os.environ['POCSTIME'] = '2016-08-13 15:00:00'
    status = observatory.status
    assert 'mount' not in status
    assert 'observation' not in status
    assert 'observer' in status

    observatory.mount.initialize(unpark=True)
    status2 = observatory.status
    assert status != status2
    assert 'mount' in status2

    observatory.get_observation()
    status3 = observatory.status
    assert status3 != status
    assert status3 != status2

    assert 'mount' in status3
    assert 'observation' in status3


def test_default_config(observatory):
    """ Creates a default Observatory and tests some of the basic parameters """

    assert observatory.location is not None
    assert observatory.location.get('elevation').value == pytest.approx(
        observatory.get_config('location.elevation').value, rel=1)
    assert observatory.location.get('horizon') == observatory.get_config('location.horizon')
    assert hasattr(observatory, 'scheduler')
    assert isinstance(observatory.scheduler, Scheduler)


def test_is_dark(observatory):
    os.environ['POCSTIME'] = '2016-08-13 10:00:00'
    assert observatory.is_dark() is True

    os.environ['POCSTIME'] = '2016-08-13 22:00:00'
    assert observatory.is_dark() is False
    assert observatory.is_dark() is False
    assert observatory.is_dark(at_time=Time('2016-08-13 10:00:00')) is True
    os.environ['POCSTIME'] = '2016-09-09 04:00:00'
    assert observatory.is_dark(horizon='flat') is False
    os.environ['POCSTIME'] = '2016-09-09 05:00:00'
    assert observatory.is_dark(horizon='flat') is True
    assert observatory.is_dark(horizon='observe') is False
    assert observatory.is_dark(horizon='invalid-defaults-to-observe') is False
    os.environ['POCSTIME'] = '2016-09-09 09:00:00'
    assert observatory.is_dark(horizon='observe') is True
    assert observatory.is_dark(horizon='invalid-defaults-to-observe') is True


def test_standard_headers(observatory):
    os.environ['POCSTIME'] = '2016-08-13 22:00:00'

    observatory.scheduler.fields_file = None
    observatory.scheduler.fields_list = [
        {'name': 'HAT-P-20',
         'priority': '100',
         'position': '07h27m39.89s +24d20m14.7s',
         },
    ]

    observatory.get_observation()
    headers = observatory.get_standard_headers()

    test_headers = {
        'airmass': 1.091778,
        'creator': 'POCSv{}'.format(__version__),
        'elevation': 3400.0,
        'ha_mnt': 1.6844671878927793,
        'latitude': 19.54,
        'longitude': -155.58,
        'moon_fraction': 0.7880103086091879,
        'moon_separation': 148.34401,
        'observer': 'Generic PANOPTES Unit',
        'origin': 'Project PANOPTES'}

    assert headers['airmass'] == pytest.approx(test_headers['airmass'], rel=1e-2)
    assert headers['ha_mnt'] == pytest.approx(test_headers['ha_mnt'], rel=1e-2)
    assert headers['moon_fraction'] == pytest.approx(test_headers['moon_fraction'], rel=1e-2)
    assert headers['moon_separation'] == pytest.approx(test_headers['moon_separation'], rel=1e-2)
    assert headers['creator'] == test_headers['creator']
    assert headers['elevation'] == test_headers['elevation']
    assert headers['latitude'] == test_headers['latitude']
    assert headers['longitude'] == test_headers['longitude']


def test_sidereal_time(observatory):
    os.environ['POCSTIME'] = '2016-08-13 10:00:00'
    st = observatory.sidereal_time
    assert abs(st.value - 21.11269263733713) < 1e-4

    os.environ['POCSTIME'] = '2016-08-13 22:00:00'
    st = observatory.sidereal_time
    assert abs(st.value - 9.145547849536634) < 1e-4


def test_get_observation(observatory):
    os.environ['POCSTIME'] = '2016-08-13 15:00:00'
    observation = observatory.get_observation()
    assert isinstance(observation, Observation)

    assert observatory.current_observation == observation


def test_get_observation_no_scheduler(observatory):
    observatory.scheduler = None
    assert observatory.get_observation() is None


def test_cleanup_observations_no_scheduler(observatory):
    observatory.scheduler = None
    assert observatory.cleanup_observations() is None


@pytest.mark.with_camera
def test_observe(observatory):
    assert observatory.current_observation is None
    assert len(observatory.scheduler.observed_list) == 0

    t0 = '2016-08-13 15:00:00'

    observatory.get_observation(time=t0)
    assert observatory.current_observation is not None

    assert len(observatory.scheduler.observed_list) == 1

    assert observatory.current_observation.current_exp_num == 0
    observatory.observe()
    assert observatory.current_observation.current_exp_num == 1

    observatory.cleanup_observations()
    assert len(observatory.scheduler.observed_list) == 0


def test_autofocus_disconnected(observatory):
    # 'Disconnect' simulated cameras which will cause
    # autofocus to fail with errors and no events returned.
    for camera in observatory.cameras.values():
        camera._connected = False
    events = observatory.autofocus_cameras()
    assert events == {}


def test_autofocus_all(observatory):
    events = observatory.autofocus_cameras()
    # Two simulated cameras
    assert len(events) == 2
    # Wait for autofocus to finish
    for event in events.values():
        event.wait()


def test_autofocus_coarse(observatory):
    events = observatory.autofocus_cameras(coarse=True)
    assert len(events) == 2
    for event in events.values():
        event.wait()


def test_autofocus_named(observatory):
    cam_names = [name for name in observatory.cameras.keys()]
    # Call autofocus on just one camera.
    events = observatory.autofocus_cameras(camera_list=[cam_names[0]])
    assert len(events) == 1
    assert [name for name in events.keys()] == [cam_names[0]]
    for event in events.values():
        event.wait()


def test_autofocus_bad_name(observatory):
    events = observatory.autofocus_cameras(camera_list=['NOTAREALCAMERA', 'ALSONOTACAMERA'])
    # Will get a warning and a empty dictionary.
    assert events == {}


def test_autofocus_focusers_disconnected(observatory):
    for camera in observatory.cameras.values():
        camera.focuser._connected = False
    events = observatory.autofocus_cameras()
    assert events == {}


def test_autofocus_no_focusers(observatory):
    for camera in observatory.cameras.values():
        camera.focuser = None
    events = observatory.autofocus_cameras()
    assert events == {}


def test_no_dome(observatory):
    # Doesn't have a dome, and dome operations always report success.
    assert not observatory.has_dome
    assert observatory.open_dome()
    assert observatory.close_dome()


def test_operate_dome(dynamic_config_server, config_port):
    # Remove dome and night simulator
    set_config('simulator', hardware.get_all_names(without=['dome', 'night']), port=config_port)

    set_config('dome', {
        'brand': 'Simulacrum',
        'driver': 'simulator',
    }, port=config_port)

    set_config('dome', {
        'brand': 'Simulacrum',
        'driver': 'simulator',
    }, port=config_port)
    dome = create_dome_simulator(config_port=config_port)
    observatory = Observatory(dome=dome, config_port=config_port)

    assert observatory.has_dome
    assert observatory.open_dome()
    assert observatory.dome.is_open
    assert not observatory.dome.is_closed
    assert observatory.open_dome()
    assert observatory.dome.is_open
    assert not observatory.dome.is_closed
    assert observatory.close_dome()
    assert observatory.dome.is_closed
    assert not observatory.dome.is_open
    assert observatory.close_dome()
    assert observatory.dome.is_closed
    assert not observatory.dome.is_open
    assert observatory.open_dome()
    assert observatory.dome.is_open
    assert not observatory.dome.is_closed
