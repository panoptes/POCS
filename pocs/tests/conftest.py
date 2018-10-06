# pytest will load this file, adding the fixtures in it, if some of the tests
# in the same directory are selected, or if the current working directory when
# running pytest is the directory containing this file.
# Note that there are other fixtures defined in the conftest.py in the root
# of this project.

import copy
import os
import pytest

import pocs.base
from pocs.utils.config import load_config

# Global variable with the default config; we read it once, copy it each time it is needed.
_one_time_config = None


@pytest.fixture(scope='module')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    return str(directory)


@pytest.fixture(scope='function')
def config(images_dir):
    pocs.base.reset_global_config()

    global _one_time_config
    if not _one_time_config:
        _one_time_config = load_config(ignore_local=True, simulator=['all'])
        _one_time_config['db']['name'] = 'panoptes_testing'

    _one_time_config['directories']['images'] = images_dir
    _one_time_config['scheduler']['fields_file'] = 'simulator.yaml'

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
