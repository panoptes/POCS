import os
import pytest

from astropy import units as u
from astropy.time import Time

from pocs.observatory import Observatory
from pocs.scheduler.dispatch import Scheduler
from pocs.scheduler.observation import Observation
from pocs.utils import error

has_camera = pytest.mark.skipif(
    not pytest.config.getoption("--camera"),
    reason="need --camera to observe"
)


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


@pytest.fixture
def observatory(simulator, config):
    """ Return a valid Observatory instance with a specific config """

    obs = Observatory(simulator=simulator, config=config)
    return obs


def test_error_exit():
    with pytest.raises(SystemExit):
        Observatory()


def test_bad_site(simulator, config):
    conf = config.copy()
    del conf['location']
    with pytest.raises(error.PanError):
        Observatory(simulator=simulator, config=conf)


def test_bad_mount(config):
    conf = config.copy()
    simulator = ['weather', 'camera', 'night']
    conf['mount']['port'] = '/dev/'
    conf['mount']['driver'] = 'foobar'
    with pytest.raises(error.NotFound):
        Observatory(simulator=simulator, config=conf)


def test_bad_scheduler(config):
    conf = config.copy()
    simulator = ['all']
    conf['scheduler']['type'] = 'foobar'
    with pytest.raises(error.NotFound):
        Observatory(simulator=simulator, config=conf)


def test_bad_scheduler_fields_file(config):
    conf = config.copy()
    simulator = ['all']
    conf['scheduler']['fields_file'] = 'foobar'
    with pytest.raises(error.NotFound):
        Observatory(simulator=simulator, config=conf)


def test_bad_camera(config):
    conf = config.copy()
    simulator = ['weather', 'mount', 'night']
    with pytest.raises(SystemExit):
        Observatory(simulator=simulator, config=conf, auto_detect=True)


def test_camera_not_found(config):
    conf = config.copy()
    simulator = ['weather', 'mount', 'night']
    with pytest.raises(SystemExit):
        Observatory(simulator=simulator, config=conf)


def test_camera_import_error(config):
    conf = config.copy()
    conf['cameras']['devices'][0]['model'] = 'foobar'
    simulator = ['weather', 'mount', 'night']
    with pytest.raises(error.NotFound):
        Observatory(simulator=simulator, config=conf, auto_detect=False)


def test_status(observatory):
    os.environ['POCSTIME'] = '2016-08-13 10:00:00'
    status = observatory.status()
    assert 'mount' not in status
    assert 'observation' not in status
    assert 'observer' in status

    observatory.mount.initialize()
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
    observation = observatory.get_observation()
    assert isinstance(observation, Observation)

    assert observatory.current_observation == observation


@has_camera
def test_observe(observatory):
    assert observatory.current_observation is None

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

    assert observatory.current_observation.current_exp == 0
    observatory.observe()
    assert observatory.current_observation.current_exp == 1
