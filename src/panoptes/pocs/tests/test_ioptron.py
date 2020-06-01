import os
import pytest
from contextlib import suppress

from astropy.coordinates import EarthLocation
from astropy import units as u

from panoptes.pocs.images import OffsetError
from panoptes.pocs.mount.ioptron import Mount
from panoptes.pocs.utils.location import create_location_from_config
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config


@pytest.fixture
def location(dynamic_config_server, config_port):
    loc = get_config('location', port=config_port)
    return EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])


@pytest.fixture(scope="function")
def mount(dynamic_config_server, config_port, location):
    with suppress(KeyError):
        del os.environ['POCSTIME']

    set_config('mount',
               {
                   'brand': 'bisque',
                   'template_dir': 'resources/bisque',
               }, port=config_port)

    return Mount(location=location, config_port=config_port)


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
    def setup(self):

        # Don't use config_port because we use real live config_server
        location = create_location_from_config()

        # Can't supply full location, need earth_location
        with pytest.raises(AssertionError):
            mount = Mount(location)

        earth_location = location['earth_location']

        mount = Mount(earth_location)
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

        # These are the empirically determined coordinates for PAN001
        assert self.mount._park_coordinates.dec.value == -10.0
        assert self.mount._park_coordinates.ra.value - 322.98 <= 1.0

    def test_unpark_park(self):
        assert self.mount.is_parked is True
        self.mount.initialize()
        self.mount.unpark()
        assert self.mount.is_parked is False
        self.mount.home_and_park()
        assert self.mount.is_parked is True


def test_get_tracking_correction(mount):

    offsets = [
        # HA, ΔRA, ΔDec, Magnitude
        (2, -13.0881456, 1.4009, 12.154),
        (2, -13.0881456, -1.4009, 12.154),
        (2, 13.0881456, 1.4009, 12.154),
        (14, -13.0881456, 1.4009, 12.154),
        (14, 13.0881456, 1.4009, 12.154),
        # Too small
        (2, -13.0881456, 0.4009, 2.154),
        (2, 0.0881456, 1.4009, 2.154),
        # Too big
        (2, -13.0881456, 99999.4009, 2.154),
        (2, -99999.0881456, 1.4009, 2.154),
    ]

    corrections = [
        (103.49, 'south', 966.84, 'east'),
        (103.49, 'north', 966.84, 'east'),
        (103.49, 'south', 966.84, 'west'),
        (103.49, 'north', 966.84, 'east'),
        (103.49, 'north', 966.84, 'west'),
        # Too small
        (None, 'south', 966.84, 'east'),
        (103.49, 'south', None, 'east'),
        # Too big
        (99999.0, 'south', 966.84, 'east'),
        (103.49, 'south', 99999.0, 'east'),
    ]

    for offset, correction in zip(offsets, corrections):
        pointing_ha = offset[0]
        offset_info = OffsetError(
            offset[1] * u.arcsec,
            offset[2] * u.arcsec,
            offset[3] * u.arcsec
        )
        correction_info = mount.get_tracking_correction(offset_info, pointing_ha)

        dec_info = correction_info['dec']
        expected_correction = correction[0]
        if expected_correction is not None:
            assert dec_info[1] == pytest.approx(expected_correction, abs=1e-2)
            assert dec_info[2] == correction[1]
        else:
            assert dec_info == expected_correction

        ra_info = correction_info['ra']
        expected_correction = correction[2]
        if expected_correction is not None:
            assert ra_info[1] == pytest.approx(expected_correction, abs=1e-2)
            assert ra_info[2] == correction[3]
        else:
            assert ra_info == expected_correction


def test_get_tracking_correction_custom(mount):

    min_tracking = 105
    max_tracking = 950

    offsets = [
        # HA, ΔRA, ΔDec, Magnitude
        (2, -13.0881456, 1.4009, 12.154),
        (2, -13.0881456, -1.4009, 12.154),
    ]

    corrections = [
        (None, 'south', 950.0, 'east'),
        (None, 'north', 950.0, 'east'),
    ]

    for offset, correction in zip(offsets, corrections):
        pointing_ha = offset[0]
        offset_info = OffsetError(
            offset[1] * u.arcsec,
            offset[2] * u.arcsec,
            offset[3] * u.arcsec
        )
        correction_info = mount.get_tracking_correction(offset_info,
                                                        pointing_ha,
                                                        min_tracking_threshold=min_tracking,
                                                        max_tracking_threshold=max_tracking)

        dec_info = correction_info['dec']
        expected_correction = correction[0]
        if expected_correction is not None:
            assert dec_info[1] == pytest.approx(expected_correction, abs=1e-2)
            assert dec_info[2] == correction[1]
        else:
            assert dec_info == expected_correction

        ra_info = correction_info['ra']
        expected_correction = correction[2]
        if expected_correction is not None:
            assert ra_info[1] == pytest.approx(expected_correction, abs=1e-2)
            assert ra_info[2] == correction[3]
        else:
            assert ra_info == expected_correction
