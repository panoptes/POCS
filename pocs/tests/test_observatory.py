import os
import pytest

from astropy import units as u
from astropy.time import Time

from pocs import hardware
import pocs.version
from pocs.observatory import Observatory
from pocs.scheduler.dispatch import Scheduler
from pocs.scheduler.observation import Observation
from pocs.utils import error


@pytest.fixture
def simulator():
    """ We assume everything runs on a simulator

    Tests that require real hardware should be marked with the appropriate
    fixtue (see `conftest.py`)
    """
    return hardware.get_all_names(without=['night'])


@pytest.fixture
def observatory(config, simulator):
    """Return a valid Observatory instance with a specific config."""
    obs = Observatory(config=config, simulator=simulator, ignore_local_config=True)
    return obs


@pytest.fixture(scope='module')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    return str(directory)


def test_error_exit(config):
    with pytest.raises(SystemExit):
        Observatory(ignore_local_config=True, simulator=['none'])


def test_bad_site(simulator, config):
    conf = config.copy()
    conf['location'] = {}
    with pytest.raises(error.PanError):
        Observatory(simulator=simulator, config=conf, ignore_local_config=True)


def test_bad_mount_port(config):
    conf = config.copy()
    simulator = hardware.get_all_names(without=['mount'])
    conf['mount']['serial']['port'] = '/dev/'
    with pytest.raises(SystemExit):
        Observatory(simulator=simulator, config=conf, ignore_local_config=True)


def test_bad_mount_driver(config):
    conf = config.copy()
    simulator = hardware.get_all_names(without=['mount'])
    conf['mount']['driver'] = 'foobar'
    with pytest.raises(SystemExit):
        Observatory(simulator=simulator, config=conf, ignore_local_config=True)


def test_bad_scheduler(config):
    conf = config.copy()
    simulator = ['all']
    conf['scheduler']['type'] = 'foobar'
    with pytest.raises(error.NotFound):
        Observatory(simulator=simulator, config=conf, ignore_local_config=True)


def test_bad_scheduler_fields_file(config):
    conf = config.copy()
    simulator = ['all']
    conf['scheduler']['fields_file'] = 'foobar'
    with pytest.raises(error.NotFound):
        Observatory(simulator=simulator, config=conf, ignore_local_config=True)


def test_bad_camera(config):
    conf = config.copy()
    simulator = hardware.get_all_names(without=['camera'])
    with pytest.raises(error.PanError):
        Observatory(simulator=simulator, config=conf, auto_detect=True, ignore_local_config=True)


def test_camera_not_found(config):
    conf = config.copy()
    simulator = hardware.get_all_names(without=['camera'])
    with pytest.raises(error.PanError):
        Observatory(simulator=simulator, config=conf, ignore_local_config=True)


def test_camera_port_error(config):
    conf = config.copy()
    conf['cameras']['devices'][0]['model'] = 'foobar'
    simulator = hardware.get_all_names(without=['camera'])
    with pytest.raises(error.CameraNotFound):
        Observatory(simulator=simulator, config=conf, auto_detect=False, ignore_local_config=True)


def test_camera_import_error(config):
    conf = config.copy()
    conf['cameras']['devices'][0]['model'] = 'foobar'
    conf['cameras']['devices'][0]['port'] = 'usb:001,002'
    simulator = hardware.get_all_names(without=['camera'])
    with pytest.raises(error.NotFound):
        Observatory(simulator=simulator, config=conf, auto_detect=False, ignore_local_config=True)


def test_status(observatory):
    os.environ['POCSTIME'] = '2016-08-13 10:00:00'
    status = observatory.status()
    assert 'mount' not in status
    assert 'observation' not in status
    assert 'observer' in status

    observatory.mount.initialize(unpark=True)
    status2 = observatory.status()
    assert status != status2
    assert 'mount' in status2

    observatory.get_observation()
    status3 = observatory.status()
    assert status3 != status
    assert status3 != status2

    assert 'mount' in status3
    assert 'observation' in status3


def test_default_config(observatory):
    """ Creates a default Observatory and tests some of the basic parameters """

    assert observatory.location is not None
    assert observatory.location.get('elevation') - \
        observatory.config['location']['elevation'] < 1. * u.meter
    assert observatory.location.get('horizon') == observatory.config['location']['horizon']
    assert hasattr(observatory, 'scheduler')
    assert isinstance(observatory.scheduler, Scheduler)


def test_is_dark(observatory):
    os.environ['POCSTIME'] = '2016-08-13 10:00:00'
    assert observatory.is_dark is True

    os.environ['POCSTIME'] = '2016-08-13 22:00:00'
    assert observatory.is_dark is False


def test_standard_headers(observatory):
    os.environ['POCSTIME'] = '2016-08-13 22:00:00'

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
        'creator': 'POCSv{}'.format(pocs.version.__version__),
        'elevation': 3400.0,
        'ha_mnt': 1.6844671878927793,
        'latitude': 19.54,
        'longitude': -155.58,
        'moon_fraction': 0.7880103086091879,
        'moon_separation': 156.1607340087774,
        'observer': 'Generic PANOPTES Unit',
        'origin': 'Project PANOPTES'}

    assert (headers['airmass'] - test_headers['airmass']) < 1e-4
    assert (headers['ha_mnt'] - test_headers['ha_mnt']) < 1e-4
    assert (headers['moon_fraction'] - test_headers['moon_fraction']) < 1e-4
    assert (headers['moon_separation'] - test_headers['moon_separation']) < 1e-4
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


def test_primary_camera(observatory):
    assert observatory.primary_camera is not None


def test_get_observation(observatory):
    observation = observatory.get_observation()
    assert isinstance(observation, Observation)

    assert observatory.current_observation == observation


@pytest.mark.with_camera
def test_observe(observatory):
    assert observatory.current_observation is None
    assert len(observatory.scheduler.observed_list) == 0

    time = Time('2016-08-13 10:00:00')
    observatory.scheduler.fields_list = [
        {'name': 'Kepler 1100',
         'priority': '100',
         'position': '19h27m29.10s +44d05m15.00s',
         'exp_time': 10,
         },
    ]
    observatory.get_observation(time=time)
    assert observatory.current_observation is not None

    assert len(observatory.scheduler.observed_list) == 1

    assert observatory.current_observation.current_exp == 0
    observatory.observe()
    assert observatory.current_observation.current_exp == 1

    observatory.cleanup_observations()
    assert len(observatory.scheduler.observed_list) == 0


def test_autofocus_disconnected(observatory):
    # 'Disconnect' simulated cameras which will cause
    # autofocus to fail with errors and no events returned.
    for camera in observatory.cameras.values():
        camera._connected = False
    events = observatory.autofocus_cameras()
    assert events == {}


def test_autofocus_all(observatory, images_dir):
    observatory.config['directories']['images'] = images_dir
    events = observatory.autofocus_cameras()
    # Two simulated cameras
    assert len(events) == 2
    # Wait for autofocus to finish
    for event in events.values():
        event.wait()


def test_autofocus_coarse(observatory, images_dir):
    observatory.config['directories']['images'] = images_dir
    events = observatory.autofocus_cameras(coarse=True)
    assert len(events) == 2
    for event in events.values():
        event.wait()


def test_autofocus_named(observatory, images_dir):
    observatory.config['directories']['images'] = images_dir
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


def test_operate_dome(config_with_simulated_dome):
    simulator = hardware.get_all_names(without=['dome', 'night'])
    observatory = Observatory(config=config_with_simulated_dome, simulator=simulator,
                              ignore_local_config=True)
    assert observatory.has_dome
    assert observatory.open_dome()
    assert observatory.dome.is_open
    assert observatory.close_dome()
    assert observatory.dome.is_closed
