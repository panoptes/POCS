import os
import pytest

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord

from panoptes.pocs.mount.simulator import Mount
from panoptes.utils.config.client import get_config
from panoptes.utils import error
from panoptes.utils import altaz_to_radec


@pytest.fixture
def location(dynamic_config_server, config_port):
    loc = get_config('location', port=config_port)
    return EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])


@pytest.fixture
def target(location):
    return altaz_to_radec(obstime='2016-08-13 21:03:01', location=location, alt=45, az=90)


def test_no_location(dynamic_config_server, config_port):
    with pytest.raises(TypeError):
        Mount(config_port=config_port)


@pytest.fixture(scope='function')
def mount(dynamic_config_server, config_port, location):
    return Mount(location=location, config_port=config_port)


def test_connect(mount):
    assert mount.connect() is True


def test_disconnect(mount):
    assert mount.connect() is True
    assert mount.disconnect() is True
    assert mount.is_connected is False


def test_initialize(mount):
    assert mount.initialize() is True


def test_target_coords(mount):
    c = SkyCoord('20h00m43.7135s +22d42m39.0645s')

    mount.set_target_coordinates(c)

    assert mount.get_target_coordinates().to_string() == '300.182 22.7109'


def test_set_park_coords(mount):
    os.environ['POCSTIME'] = '2016-08-13 23:03:01'
    mount.set_park_coordinates()
    assert mount._park_coordinates is not None

    assert mount._park_coordinates.dec.value == -10.0
    assert mount._park_coordinates.ra.value - 322.98 <= 1.0

    os.environ['POCSTIME'] = '2016-08-13 13:03:01'
    mount.set_park_coordinates()

    assert mount._park_coordinates.dec.value == -10.0
    assert mount._park_coordinates.ra.value - 172.57 <= 1.0


def test_status(mount):
    status1 = mount.status
    assert 'mount_target_ra' not in status1

    c = SkyCoord('20h00m43.7135s +22d42m39.0645s')

    mount.set_target_coordinates(c)

    assert mount.get_target_coordinates().to_string() == '300.182 22.7109'

    status2 = mount.status
    assert 'mount_target_ra' in status2


def test_update_location_no_init(dynamic_config_server, config_port, mount):
    loc = get_config('location', port=config_port)

    location2 = EarthLocation(
        lon=loc['longitude'],
        lat=loc['latitude'],
        height=loc['elevation'] -
        1000 *
        u.meter)

    with pytest.raises(AssertionError):
        mount.location = location2


def test_update_location(dynamic_config_server, config_port, mount):
    loc = get_config('location', port=config_port)

    mount.initialize()

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


def test_set_tracking_rate(mount):
    mount.initialize()

    assert mount.tracking_rate == 1.0

    mount.set_tracking_rate(delta=.005)

    assert mount.tracking_rate == 1.005

    mount.set_tracking_rate()

    assert mount.tracking_rate == 1.0


def test_no_slew_without_unpark(mount):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

    mount.initialize()

    assert mount.is_parked is True
    assert mount.slew_to_target() is False


def test_no_slew_without_target(mount):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

    mount.initialize(unpark=True)

    assert mount.slew_to_target() is False


def test_slew_to_target(mount, target):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

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


def test_slew_to_target_timeout(mount, target):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

    mount.initialize(unpark=True)

    assert mount.set_target_coordinates(target) is True
    with pytest.raises(error.Timeout):
        assert mount.slew_to_target(blocking=True, timeout=3, slew_delay=30)


def test_slew_to_home(mount):
    mount.initialize()

    assert mount.is_parked is True
    assert mount.is_home is False
    mount.slew_to_home()
    assert mount.is_parked is False
    assert mount.is_home is True
