# pytest will load this file, adding the fixtures in it, if some of the tests
# in the same directory are selected, or if the current working directory when
# running pytest is the directory containing this file.
# Note that there are other fixtures defined in the conftest.py in the root
# of this project.

import copy
import os
import pytest

from pocs import base
from pocs.core import POCS
from pocs.utils.config import load_config
from pocs.camera import create_cameras_from_config
from pocs.observatory import Observatory


# Global variable with the default config; we read it once, copy it each time it is needed.
_one_time_config = None


@pytest.fixture(scope='function')
def config():
    base.reset_global_config()

    global _one_time_config
    if not _one_time_config:
        _one_time_config = load_config(ignore_local=True, simulator=['all'])
        _one_time_config['db']['name'] = 'panoptes_testing'

    return copy.deepcopy(_one_time_config)


@pytest.fixture
def config_with_simulated_dome(config):
    config.update({
        'dome': {
            'brand': 'Simulacrum',
            'driver': 'simulator',
        },
    })
    return config


@pytest.fixture
def data_dir():
    return '{}/pocs/tests/data'.format(os.getenv('POCS'))


@pytest.fixture(scope='function')
def cameras(config):
    """Get the default cameras from the config."""
    return create_cameras_from_config(config)


@pytest.fixture(scope='function')
def observatory(config, db_type, cameras):
    observatory = Observatory(
        config=config,
        cameras=cameras,
        simulator=['all'],
        ignore_local_config=True,
        db_type=db_type
    )
    return observatory


@pytest.fixture(scope='function')
def pocs(config, observatory):
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'

    p = POCS(observatory,
             run_once=True,
             config=config,
             ignore_local_config=True)

    p.observatory.scheduler.fields_file = None
    p.observatory.scheduler.fields_list = [
        {'name': 'Wasp 33',
         'position': '02h26m51.0582s +37d33m01.733s',
         'priority': '100',
         'exp_time': 2,
         'min_nexp': 2,
         'exp_set_size': 2,
         },
    ]

    yield p

    p.power_down()
