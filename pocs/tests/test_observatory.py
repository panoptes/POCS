import os
import pytest

import astropy.units as u

from pocs.observatory import Observatory
from pocs.scheduler.dispatch import Scheduler
from pocs.scheduler.observation import Observation


@pytest.fixture
def simulator(request):
    sim = list()

    if not request.config.getoption("--camera"):
        sim.append('camera')

    if not request.config.getoption("--mount"):
        sim.append('mount')

    if not request.config.getoption("--weather"):
        sim.append('weather')

    return sim

noobserve = pytest.mark.skipif(
    not pytest.config.getoption("--camera"),
    reason="need --camera to observe"
)


@pytest.fixture
def observatory(simulator):
    """ Return a valid Observatory instance with a specific config """
    config = {'cameras': {'auto_detect': True,
                          'devices': [{'model': 'canon_gphoto2',
                                       'port': 'usb:001,006',
                                       'primary': True}]},
              'directories': {'base': '/var/panoptes',
                              'data': '/var/panoptes/data',
                              'images': '/var/panoptes/images',
                              'mounts': '/var/panoptes/POCS/resources/conf_files/mounts',
                              'resources': '/var/panoptes/POCS/resources/',
                              'targets': '/var/panoptes/POCS/resources/conf_files/targets',
                              'webcam': '/var/panoptes/webcams'},
              'location': {'elevation': 3400.0 * u.meter,
                           'horizon': 30.0 * u.degree,
                           'latitude': 19.54 * u.degree,
                           'longitude': -155.58 * u.degree,
                           'name': 'Mauna Loa Observatory',
                           'timezone': 'US/Hawaii',
                           'twilight_horizon': -18.0 * u.degree,
                           'utc_offset': -10.0},
              'messaging': {'port': 6500},
              'mount': {'PEC_available': False,
                        'brand': 'ioptron',
                        'driver': 'ioptron',
                        'model': 30,
                        'non_sidereal_available': True,
                        'port': '/dev/ttyUSB0',
                        'simulator': True},
              'name': 'Generic PANOPTES Unit',
              'pointing': {'exptime': 30, 'max_iterations': 3, 'threshold': 0.05},
              'scheduler': {'targets_file': 'default_targets.yaml', 'type': 'dispatch'},
              'simulator': ['camera', 'mount', 'weather', 'night'],
              'state_machine': 'simple_state_table'}

    obs = Observatory(simulator=simulator, config=config)
    return obs


def test_default_config(observatory):
    """ Creates a default Observatory and tests some of the basic parameters """

    assert observatory.location is not None
    assert observatory.location.get('elevation') - observatory.config['location']['elevation'] < 1. * u.meter
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
    observatory.get_observation()
    headers = observatory.get_standard_headers()

    test_headers = {
        'airmass': 1.0063823275133195,
        'creator': 'POCSv0.1.1',
        'elevation': 3400.0,
        'ha_mnt': 0.47221438988158937,
        'latitude': 19.54,
        'longitude': -155.58,
        'moon_fraction': 0.7880103086091879,
        'moon_separation': 139.41866400474228,
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
    start_of_night = observatory.observer.tonight()[0]
    observation = observatory.get_observation(time=start_of_night)
    assert isinstance(observation, Observation)

    assert observatory.current_observation == observation


@noobserve
def test_observe(observatory):
    assert observatory.current_observation is None
    observatory.get_observation()
    assert observatory.current_observation is not None

    assert observatory.current_observation.current_exp == 0
    observatory.observe()
    assert observatory.current_observation.current_exp == 1
