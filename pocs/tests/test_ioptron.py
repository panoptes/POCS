import os
import time
import pytest
from contextlib import suppress
from multiprocessing import Process

from astropy.coordinates import EarthLocation
from astropy import units as u

from pocs import hardware
from pocs.images import OffsetError
from pocs.mount.ioptron import Mount
from panoptes.utils.logger import get_root_logger
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config
from panoptes.utils.config.server import app


@pytest.fixture(scope='module')
def config_port():
    return '4861'


# Override default config_server and use function scope so we can change some values cleanly.
@pytest.fixture(scope='module')
def config_server(config_host, config_port, config_server_args, images_dir, db_name):

    logger = get_root_logger()
    logger.critical(f'Starting config_server for testing function')

    def start_config_server():
        # Load the config items into the app config.
        for k, v in config_server_args.items():
            app.config[k] = v

        # Start the actual flask server.
        app.run(host=config_host, port=config_port)

    proc = Process(target=start_config_server)
    proc.start()

    logger.info(f'config_server started with PID={proc.pid}')

    # Give server time to start
    time.sleep(1)

    # Adjust various config items for testing
    unit_name = 'Generic PANOPTES Unit'
    unit_id = 'PAN000'
    logger.info(f'Setting testing name and unit_id to {unit_id}')
    set_config('name', unit_name, port=config_port)
    set_config('pan_id', unit_id, port=config_port)

    logger.info(f'Setting testing database to {db_name}')
    set_config('db.name', db_name, port=config_port)

    fields_file = 'simulator.yaml'
    logger.info(f'Setting testing scheduler fields_file to {fields_file}')
    set_config('scheduler.fields_file', fields_file, port=config_port)

    # TODO(wtgee): determine if we need separate directories for each module.
    logger.info(f'Setting temporary image directory for testing')
    set_config('directories.images', images_dir, port=config_port)

    # Make everything a simulator
    set_config('simulator', hardware.get_simulator_names(simulator=['all']), port=config_port)

    yield
    logger.critical(f'Killing config_server started with PID={proc.pid}')
    proc.terminate()


@pytest.fixture
def location(config_port):
    loc = get_config('location', port=config_port)
    return EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])


@pytest.fixture(scope="function")
def mount(config_server, config_port, location):
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
    ]

    corrections = [
        (103.49, 'south', 966.84, 'east'),
        (103.49, 'north', 966.84, 'east'),
        (103.49, 'south', 966.84, 'west'),
        (103.49, 'north', 966.84, 'east'),
        (103.49, 'north', 966.84, 'west'),
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
        ra_info = correction_info['ra']

        assert dec_info[1] == pytest.approx(correction[0], rel=1e-2)
        assert dec_info[2] == correction[1]

        assert ra_info[1] == pytest.approx(correction[2], rel=1e-2)
        assert ra_info[2] == correction[3]
