import os
import pytest

from astropy import units as u
from astropy.coordinates import EarthLocation

from panoptes.pocs.mount.bisque import Mount
from panoptes.utils.config.client import get_config
from panoptes.utils import altaz_to_radec
from panoptes.utils import current_time
from panoptes.utils.theskyx import TheSkyX

pytestmark = pytest.mark.skipif(TheSkyX().is_connected is False, reason="TheSkyX is not connected")


@pytest.fixture
def location(dynamic_config_server, config_port):
    config = get_config(port=config_port)
    loc = config['location']
    return EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])


@pytest.fixture(scope="function")
def mount(config, location):
    try:
        del os.environ['POCSTIME']
    except KeyError:
        pass

    config['mount'] = {
        'brand': 'bisque',
        'template_dir': 'resources/bisque',
    }
    return Mount(location=location, config=config)


@pytest.fixture
def target(location):
    return altaz_to_radec(obstime=current_time(), location=location, alt=45, az=90)


@pytest.fixture
def target_down(location):
    return altaz_to_radec(obstime=current_time(), location=location, alt=5, az=90)


def test_no_location():
    with pytest.raises(TypeError):
        Mount()


def test_connect(mount):
    assert mount.connect() is True


def test_initialize(mount):
    assert mount.initialize() is True


def test_set_park_coords(mount):
    mount.initialize()
    assert mount._park_coordinates is None

    mount.set_park_coordinates()
    assert mount._park_coordinates is not None

    assert mount._park_coordinates.dec.value == -10.0
    assert mount._park_coordinates.ra.value - 322.98 <= 1.0

    mount.set_park_coordinates()

    assert mount._park_coordinates.dec.value == -10.0
    assert mount._park_coordinates.ra.value - 172.57 <= 1.0


def test_unpark_park(mount):
    assert mount.is_parked is True
    mount.initialize()
    mount.unpark()
    assert mount.is_parked is False
    mount.park()
    assert mount.is_parked is True


def test_status(mount, target):
    mount.initialize(unpark=True)
    status1 = mount.status
    assert 'mount_target_ra' not in status1

    mount.set_target_coordinates(target)
    assert mount.has_target is True

    assert mount.get_target_coordinates() == target

    status2 = mount.status
    assert 'mount_target_ra' in status2


def test_update_location(mount, config):
    loc = config['location']

    mount.initialize(unpark=True)

    location1 = mount.location
    location2 = EarthLocation(
        lon=loc['longitude'],
        lat=loc['latitude'],
        height=loc['elevation'] -
               1000 *
               u.meter)
    mount.location = location2

    assert location1 != location2
    assert mount.location == location2


def test_target_coords(mount, target):
    mount.initialize(unpark=True)

    assert mount.set_target_coordinates(target) is True
    assert mount.get_target_coordinates() == target


def test_no_slew_without_unpark(mount):
    mount.initialize()

    assert mount.is_parked is True
    assert mount.slew_to_target() is False


def test_no_slew_without_target(mount):
    mount.initialize(unpark=True)

    assert mount.slew_to_target() is False


def test_slew_to_target(mount, target):
    assert mount.is_parked is True

    mount.initialize(unpark=True)
    parked_coords = mount.get_current_coordinates()

    assert mount.set_target_coordinates(target) is True
    assert parked_coords != target
    assert mount.slew_to_target() is True
    current_coord = mount.get_current_coordinates()

    assert (current_coord.ra.value - target.ra.value) < 0.5
    assert (current_coord.dec.value - target.dec.value) < 0.5

    mount.park()
    assert mount.is_parked is True
    mount.get_current_coordinates() == parked_coords
