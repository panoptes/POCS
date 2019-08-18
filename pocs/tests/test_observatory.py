import os
import time

import pytest
from astropy import units as u
from astropy.time import Time

import pocs.version
from pocs.camera import create_cameras_from_config
from pocs.dome import create_dome_from_config
from pocs.mount import create_mount_from_config, AbstractMount
from pocs.observatory import Observatory
from pocs.scheduler import create_scheduler_from_config
from pocs.scheduler.dispatch import Scheduler
from pocs.scheduler.observation import Observation
from pocs.utils import error
from pocs.utils.location import create_location_from_config


@pytest.fixture
def observatory(config, images_dir):
    """Return a valid Observatory instance with a specific config."""
    site_details = create_location_from_config(config)
    scheduler = create_scheduler_from_config(config, observer=site_details['observer'])
    dome = create_dome_from_config(config)
    mount = create_mount_from_config(config)
    obs = Observatory(config=config,
                      scheduler=scheduler,
                      dome=dome,
                      mount=mount,
                      ignore_local_config=True)
    cameras = create_cameras_from_config(config)
    for cam_name, cam in cameras.items():
        obs.add_camera(cam_name, cam)

    return obs


def test_camera_already_exists(observatory, config):
    cameras = create_cameras_from_config(config)
    for cam_name, cam in cameras.items():
        observatory.add_camera(cam_name, cam)


def test_remove_cameras(observatory, config):
    cameras = create_cameras_from_config(config)
    for cam_name, cam in cameras.items():
        observatory.remove_camera(cam_name)


def test_bad_site(config):
    conf = config.copy()
    conf['location'] = {}
    with pytest.raises(error.PanError):
        Observatory(config=conf, ignore_local_config=True)


def test_cannot_observe(config, caplog):
    conf = config.copy()
    obs = Observatory(config=conf)
    assert obs.can_observe is False
    assert caplog.records[-1].levelname == "INFO" and caplog.records[
        -1].message == "Scheduler not present, cannot observe."
    site_details = create_location_from_config(conf)
    obs.scheduler = create_scheduler_from_config(conf, site_details['observer'])
    assert obs.can_observe is False
    assert caplog.records[-1].levelname == "INFO" and caplog.records[
        -1].message == "Cameras not present, cannot observe."
    cameras = create_cameras_from_config(conf)
    for cam_name, cam in cameras.items():
        obs.add_camera(cam_name, cam)
    assert obs.can_observe is False
    assert caplog.records[-1].levelname == "INFO" and caplog.records[
        -1].message == "Mount not present, cannot observe."


def test_camera_wrong_type(config):
    conf = config.copy()

    with pytest.raises(AttributeError):
        Observatory(cameras=[Time.now()],
                    config=conf,
                    auto_detect=False,
                    ignore_local_config=True
                    )

    with pytest.raises(AssertionError):
        Observatory(cameras={'Cam00': Time.now()},
                    config=conf,
                    auto_detect=False,
                    ignore_local_config=True
                    )


def test_camera(config):
    conf = config.copy()
    cameras = create_cameras_from_config(conf)
    obs = Observatory(
        cameras=cameras,
        config=conf,
        auto_detect=False,
        ignore_local_config=True
    )
    assert obs.has_cameras


def test_primary_camera(observatory):
    assert observatory.primary_camera is not None


def test_primary_camera_no_primary_camera(observatory):
    observatory._primary_camera = None
    assert observatory.primary_camera is not None


def test_set_scheduler(config, observatory):
    conf = config.copy()
    site_details = create_location_from_config(conf)
    scheduler = create_scheduler_from_config(conf, site_details['observer'])
    assert observatory.scheduler is not None
    observatory.set_scheduler(scheduler=None)
    assert observatory.scheduler is None
    observatory.set_scheduler(scheduler=scheduler)
    assert observatory.scheduler is not None
    err_msg = 'Scheduler is not instance of BaseScheduler class, cannot add.'
    with pytest.raises(TypeError, message=err_msg):
        observatory.set_scheduler('scheduler')
    with pytest.raises(TypeError, message=err_msg):
        observatory.set_scheduler()


def test_set_dome(config_with_simulated_dome):
    conf = config_with_simulated_dome.copy()
    dome = create_dome_from_config(conf)
    obs = Observatory(config=conf, dome=dome)
    assert obs.has_dome is True
    obs.set_dome(dome=None)
    assert obs.has_dome is False
    obs.set_dome(dome=dome)
    assert obs.has_dome is True
    err_msg = 'Dome is not instance of AbstractDome class, cannot add.'
    with pytest.raises(TypeError, message=err_msg):
        obs.set_dome('dome')
    with pytest.raises(TypeError, message=err_msg):
        obs.set_dome()


def test_set_mount(config_with_simulated_mount):
    conf = config_with_simulated_mount.copy()
    mount = create_mount_from_config(conf)
    obs = Observatory(config=conf, mount=mount)
    assert obs.mount is not None
    obs.set_mount(mount=None)
    assert obs.mount is None
    obs.set_mount(mount=mount)
    assert isinstance(obs.mount, AbstractMount) is True
    err_msg = 'Mount is not instance of AbstractMount class, cannot add.'
    with pytest.raises(TypeError, message=err_msg):
        obs.set_mount(mount='mount')
    with pytest.raises(TypeError, message=err_msg):
        obs.set_mount()


def test_status(observatory):
    os.environ['POCSTIME'] = '2016-08-13 15:00:00'
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
    assert observatory.location.get('elevation').value == pytest.approx(
        observatory.config['location']['elevation'].value, rel=1 * u.meter)
    assert observatory.location.get('horizon') == observatory.config['location']['horizon']
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
        'creator': 'POCSv{}'.format(pocs.version.__version__),
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


def test_cleanup_missing_config_keys(observatory):
    os.environ['POCSTIME'] = '2016-08-13 15:00:00'

    observatory.get_observation()
    camera_events = observatory.observe()

    while not all([event.is_set() for name, event in camera_events.items()]):
        time.sleep(1)

    observatory.cleanup_observations()
    del observatory.config['panoptes_network']
    observatory.cleanup_observations()

    observatory.get_observation()

    observatory.cleanup_observations()
    del observatory.config['observations']['make_timelapse']
    observatory.cleanup_observations()

    observatory.get_observation()

    observatory.cleanup_observations()
    del observatory.config['observations']['keep_jpgs']
    observatory.cleanup_observations()

    observatory.get_observation()

    observatory.cleanup_observations()
    observatory.config['pan_id'] = 'PAN99999999'
    observatory.cleanup_observations()

    observatory.get_observation()

    observatory.cleanup_observations()
    del observatory.config['pan_id']
    observatory.cleanup_observations()

    observatory.get_observation()

    # Now use parameters
    observatory.cleanup_observations(
        upload_images=False,
        make_timelapse=False,
        keep_jpgs=True
    )


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


def test_operate_dome(config_with_simulated_dome, config):
    conf = config.copy()
    dome = create_dome_from_config(conf, logger=None)
    observatory = Observatory(config=config_with_simulated_dome, dome=dome,
                              ignore_local_config=True)
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
