import os
import pytest

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord

from pocs.mount.bisque import Mount
from pocs.utils.theskyx import TheSkyX

pytestmark = pytest.mark.skipif(TheSkyX().is_connected is False,
                                reason="TheSkyX is not connected")


@pytest.fixture(scope="function")
def mount(config):
    loc = config['location']
    location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])

    config['mount'] = {
        'brand': 'bisque',
        'template_dir': 'resources/bisque',
    }
    return Mount(location=location, config=config)


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

    os.environ['POCSTIME'] = '2016-08-13 23:03:01'
    mount.set_park_coordinates()
    assert mount._park_coordinates is not None

    assert mount._park_coordinates.dec.value == -10.0
    assert mount._park_coordinates.ra.value - 322.98 <= 1.0

    os.environ['POCSTIME'] = '2016-08-13 13:03:01'
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


def test_status(mount):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

    mount.initialize()
    status1 = mount.status()
    assert 'mount_target_ra' not in status1

    c = SkyCoord('22h00m43.7135s +02d42m39.0645s')

    mount.set_target_coordinates(c)

    assert mount.get_target_coordinates().to_string() == '330.182 2.71085'

    status2 = mount.status()
    assert 'mount_target_ra' in status2


def test_update_location(mount, config):
    loc = config['location']

    mount.initialize()

    location1 = mount.location
    location2 = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'] - 1000 * u.meter)
    mount.location = location2

    assert location1 != location2
    assert mount.location == location2


def test_target_coords_below_horizon(mount):
    os.environ['POCSTIME'] = '2016-08-13 23:03:01'

    mount.initialize()
    c = SkyCoord('10h00m43.7135s +02d42m39.0645s')

    assert mount.set_target_coordinates(c) is False
    assert mount.get_target_coordinates() is None


def test_target_coords(mount):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

    mount.initialize()
    c = SkyCoord('22h00m43.7135s +02d42m39.0645s')

    assert mount.set_target_coordinates(c) is True
    assert mount.get_target_coordinates().to_string() == '330.182 2.71085'


def test_no_slew_without_unpark(mount):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

    mount.initialize(unpark=False)

    assert mount.is_parked is True
    assert mount.slew_to_target() is False


def test_no_slew_without_target(mount):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

    mount.initialize()

    assert mount.is_parked is False
    assert mount.slew_to_target() is False


def test_slew_to_target(mount):
    os.environ['POCSTIME'] = '2016-08-13 20:03:01'

    assert mount.is_parked is True

    mount.initialize()
    parked_coords = mount.get_current_coordinates()

    c = SkyCoord('22h00m43.7135s +02d42m39.0645s')

    assert mount.set_target_coordinates(c) is True
    assert parked_coords != c
    assert mount.slew_to_target() is True
    current_coord = mount.get_current_coordinates()

    assert (current_coord.ra.value - c.ra.value) < 0.5
    assert (current_coord.dec.value - c.dec.value) < 0.5

    mount.park()
    assert mount.is_parked is True
    mount.get_current_coordinates() == parked_coords
