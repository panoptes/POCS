import os
from contextlib import suppress

import pytest
from astropy.coordinates import EarthLocation
from panoptes.utils.config.client import get_config

from panoptes.pocs.mount.ioptron.cem40 import Mount
from panoptes.pocs.utils.location import create_location_from_config


@pytest.fixture
def location():
    loc = get_config("location")
    return EarthLocation(lon=loc["longitude"], lat=loc["latitude"], height=loc["elevation"])


@pytest.fixture(scope="function")
def mount(location):
    with suppress(KeyError):
        del os.environ["POCSTIME"]

    return Mount(location=location)


@pytest.mark.with_mount
def test_loading_without_config():
    """Tests the basic loading of a mount"""
    with pytest.raises(TypeError):
        mount = Mount()
        assert isinstance(mount, Mount)


@pytest.mark.with_mount
class TestMount:
    """Test the mount"""

    @pytest.fixture(autouse=True)
    def setup(self):
        location = create_location_from_config()

        # Can't supply full location, need earth_location
        with pytest.raises(AssertionError):
            mount = Mount(location)

        mount = Mount(location.earth_location)
        assert mount is not None

        self.mount = mount

        with pytest.raises(AssertionError):
            assert self.mount.query("version") == "V1.00"
        assert self.mount.is_initialized is False
        assert self.mount.initialize() is True

    def test_version(self):
        assert self.mount.query("version") == "V1.00"

    def test_unpark_park(self):
        assert self.mount.is_parked is True
        self.mount.initialize()
        self.mount.unpark()
        assert self.mount.is_parked is False
        self.mount.home_and_park()
        assert self.mount.is_parked is True
