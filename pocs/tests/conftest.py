import os
import pytest

from pocs.utils.config import parse_config

from astroplan import download_IERS_A

download_IERS_A()


def pytest_addoption(parser):
    parser.addoption("--camera", action="store_true", default=False, help="If a real camera attached")
    parser.addoption("--mount", action="store_true", default=False, help="If a real mount attached")
    parser.addoption("--weather", action="store_true", default=False, help="If a real weather station attached")
    parser.addoption("--solve", action="store_true", default=False, help="If tests that require solving should be run")


@pytest.fixture
def config():
    config = {'cameras': {'auto_detect': True,
                          'devices': [{'model': 'canon_gphoto2',
                                       'port': 'usb:001,006',
                                       'primary': True}]},
              'directories': {'base': os.getenv('POCS', '/var/panoptes'),
                              'data': 'data',
                              'images': 'images',
                              'mounts': 'POCS/resources/conf_files/mounts',
                              'resources': 'POCS/resources/',
                              'targets': 'POCS/resources/conf_files/targets',
                              'webcam': 'webcams'},
              'location': {'elevation': 3400.0,
                           'horizon': 30.0,
                           'latitude': 19.54,
                           'longitude': -155.58,
                           'name': 'Mauna Loa Observatory',
                           'timezone': 'US/Hawaii',
                           'twilight_horizon': -18.0,
                           'utc_offset': -10.0},
              'messaging': {'cmd_port': 6500, 'msg_port': 6510},
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

    return parse_config(config)


@pytest.fixture
def data_dir():
    return '{}/pocs/tests/data'.format(os.getenv('POCS'))
