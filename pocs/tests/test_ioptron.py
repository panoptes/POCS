import pytest

from astropy.coordinates import EarthLocation

from pocs.mount.ioptron import Mount
from pocs.utils.config import load_config


def test_loading_without_config():
    """ Tests the basic loading of a mount """
    with pytest.raises(TypeError):
        mount = Mount()
        assert isinstance(mount, Mount)


class TestMount(object):
    """ Test the mount """

    @pytest.fixture(autouse=True)
    def setup(self):

        self.config = load_config(ignore_local=True)

        location = self.config['location']

        with pytest.raises(AssertionError):
            mount = Mount(location)

        loc = EarthLocation(
            lon=location['longitude'],
            lat=location['latitude'],
            height=location['elevation'])

        mount = Mount(loc)
        assert mount is not None
