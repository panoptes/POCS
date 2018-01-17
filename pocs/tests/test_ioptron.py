import pytest

from astropy.coordinates import EarthLocation

from pocs.mount.ioptron import Mount


@pytest.mark.with_mount
def test_loading_without_config():
    """ Tests the basic loading of a mount """
    with pytest.raises(TypeError):
        mount = Mount()
        assert isinstance(mount, Mount)


@pytest.mark.with_mount
class TestMount(object):

    """ Test the mount """

    @pytest.fixture(autouse=True)
    def setup(self, config):

        self.config = config

        location = self.config['location']

        with pytest.raises(AssertionError):
            mount = Mount(location)

        loc = EarthLocation(
            lon=location['longitude'],
            lat=location['latitude'],
            height=location['elevation'])

        mount = Mount(loc)
        assert mount is not None

        self.mount = mount

        with pytest.raises(AssertionError):
            assert self.mount.query('version') == 'V1.00'
        assert self.mount.is_initialized is False
        assert self.mount.initialize() is True

    def test_version(self):
        assert self.mount.query('version') == 'V1.00'

    def test_set_park_coords(self):
        self.mount.initialize()
        assert self.mount._park_coordinates is None

        self.mount.set_park_coordinates()
        assert self.mount._park_coordinates is not None

        assert self.mount._park_coordinates.dec.value == -10.0
        assert self.mount._park_coordinates.ra.value - 322.98 <= 1.0

    def test_unpark_park(self):
        assert self.mount.is_parked is True
        self.mount.initialize()
        self.mount.unpark()
        assert self.mount.is_parked is False
        self.mount.home_and_park()
        assert self.mount.is_parked is True
